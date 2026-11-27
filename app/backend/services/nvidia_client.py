"""NVIDIA build.nvidia.com HTTP client with disk caching, retry, and image compression."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, ImageOps

from config import CACHE_DIR, DEMO_CACHE_DIR, settings

log = logging.getLogger("medikiosk.nvidia")


def compress_image_for_api(image_path: Path, max_side: int = 1600, max_bytes: int = 170_000) -> tuple[bytes, int, int]:
    """Fix EXIF orientation, resize long side <= max_side, and JPEG-compress under max_bytes.

    Returns (jpeg_bytes, sent_width, sent_height): the size of the image actually sent to the
    API, so pixel coordinates in a response can be normalised against the right dimensions.
    """
    with Image.open(image_path) as raw:
        img = ImageOps.exif_transpose(raw).convert("RGB")
        orig_w, orig_h = img.size
        long_side = max(orig_w, orig_h)
        if long_side > max_side:
            scale = max_side / float(long_side)
            img = img.resize((max(1, int(orig_w * scale)), max(1, int(orig_h * scale))), Image.Resampling.LANCZOS)

        # Shrink step by step until a quality setting fits under max_bytes.
        for _ in range(6):
            for quality in (88, 78, 68, 58, 48, 38):
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality, optimize=True)
                data = buf.getvalue()
                if len(data) <= max_bytes:
                    return data, img.width, img.height
            img = img.resize((max(1, int(img.width * 0.8)), max(1, int(img.height * 0.8))), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=38, optimize=True)
        return buf.getvalue(), img.width, img.height


def image_to_data_url(image_bytes: bytes) -> str:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _cache_key(payload: dict[str, Any], image_key: str | None) -> str:
    """SHA-256 of the request. With `image_key`, the inline image is replaced by the hash of the source
    file, so the key does not change when another machine re-encodes the same page to a slightly
    different JPEG. That is what lets the saved demo replies work inside a Linux container."""
    body = payload
    if image_key:
        body = json.loads(json.dumps(payload))
        for message in body.get("messages", []):
            content = message.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and isinstance(part.get("image_url"), dict):
                        part["image_url"]["url"] = f"sha256:{image_key}"
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _cache_path(payload: dict[str, Any], image_key: str | None = None) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{_cache_key(payload, image_key)}.json"


def chat_completion(
    payload: dict[str, Any],
    use_cache: bool = True,
    allow_network: bool = True,
    image_key: str | None = None,
) -> dict[str, Any]:
    """POST to NVIDIA chat/completions with SHA-256 disk cache and 3x exponential backoff.

    Replies are looked up in the local cache first, then in the read-only replies shipped with the repo
    (data/demo_cache), so a fresh deployment can show real AI-read results without an API key.
    """
    cache_file = _cache_path(payload, image_key)
    if use_cache and cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    shipped = DEMO_CACHE_DIR / cache_file.name
    if use_cache and shipped.exists():
        return json.loads(shipped.read_text(encoding="utf-8"))

    if not allow_network:
        raise RuntimeError(
            f"No saved NVIDIA response for this page (cache file {cache_file.name}). "
            "Run it once in live mode with the API key first, then cached mode works offline."
        )

    if not settings.nvidia_key_present:
        raise RuntimeError("NVIDIA_API_KEY is not configured in app/backend/.env")

    headers = {
        "Authorization": f"Bearer {settings.nvidia_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    url = f"{settings.nvidia_base_url}/chat/completions"

    last_err: Exception | None = None
    delay = 2.0
    for attempt in range(3):
        try:
            started = time.monotonic()
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(url, headers=headers, json=payload)
            log.info(
                "NVIDIA %s -> %s in %.1fs (request %d bytes)",
                payload.get("model"),
                resp.status_code,
                time.monotonic() - started,
                len(json.dumps(payload)),
            )
            if resp.status_code in {429, 500, 502, 503, 504}:
                last_err = RuntimeError(f"NVIDIA API {resp.status_code}: {resp.text[:300]}")
                if attempt < 2:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise last_err
            if resp.status_code >= 400:
                # 4xx other than 429 will not succeed on retry: report the server's message.
                raise RuntimeError(
                    f"NVIDIA API {resp.status_code} for model {payload.get('model')}: {resp.text[:500]}"
                )
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
