"""NVIDIA build.nvidia.com HTTP client with disk caching, retry, and image compression."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import time
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageOps

from config import CACHE_DIR, settings


def compress_image_for_api(image_path: Path, max_side: int = 1600, max_bytes: int = 170_000) -> tuple[bytes, int, int]:
    """Fix EXIF orientation, resize long side <= max_side, and JPEG-compress under max_bytes."""
    with Image.open(image_path) as raw:
        img = ImageOps.exif_transpose(raw).convert("RGB")
        orig_w, orig_h = img.size
        long_side = max(orig_w, orig_h)
        if long_side > max_side:
            scale = max_side / float(long_side)
            img = img.resize((int(orig_w * scale), int(orig_h * scale)), Image.Resampling.LANCZOS)

        for quality in (88, 78, 68, 58, 48, 38, 28):
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            data = buf.getvalue()
            if len(data) <= max_bytes:
                return data, orig_w, orig_h

        # Final shrink if still over max_bytes
        w, h = img.size
        img = img.resize((int(w * 0.75), int(h * 0.75)), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=45, optimize=True)
        return buf.getvalue(), orig_w, orig_h


def image_to_data_url(image_bytes: bytes) -> str:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def _cache_path(payload: dict[str, Any]) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{digest}.json"


def chat_completion(payload: dict[str, Any], use_cache: bool = True, allow_network: bool = True) -> dict[str, Any]:
    """POST to NVIDIA chat/completions with SHA-256 disk cache and 3x exponential backoff."""
    cache_file = _cache_path(payload)
    if use_cache and cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    if not allow_network:
        raise RuntimeError(f"Cache miss for {cache_file.name} and offline/cached mode is active.")

    if not settings.nvidia_key_present:
        raise RuntimeError("NVIDIA_API_KEY is not configured in app/backend/.env")

    headers = {
        "Authorization": f"Bearer {settings.nvidia_api_key}",
        "Content-Type": "application/json",
    }
    url = f"{settings.nvidia_base_url}/chat/completions"

    last_err: Exception | None = None
    delay = 2.0
    for attempt in range(3):
        try:
            with httpx.Client(timeout=90.0) as client:
                resp = client.post(url, headers=headers, json=payload)
            if resp.status_code in {429, 500, 502, 503, 504}:
                last_err = RuntimeError(f"NVIDIA API {resp.status_code}: {resp.text[:300]}")
                if attempt < 2:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise last_err
            resp.raise_for_status()
            data = resp.json()
            if use_cache:
                cache_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return data
        except httpx.HTTPError as exc:
            last_err = exc
            if attempt < 2:
                time.sleep(delay)
                delay *= 2
                continue
            raise RuntimeError(f"NVIDIA API request failed: {exc}") from exc

    raise RuntimeError(f"NVIDIA API failed after retries: {last_err}")
