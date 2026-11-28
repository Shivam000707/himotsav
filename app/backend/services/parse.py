"""Page reader: a vision-language model turns a page photo into text lines with positions.

NVIDIA retired its dedicated Nemotron Parse endpoint (HTTP 410, Nov 2026), so this step now asks a hosted
vision-language model (NVIDIA_PARSE_MODEL, default nvidia/nemotron-3.5-super-vl-120b-a12b) to transcribe the
page as a JSON list of {"text", "bbox"} items. Checked against the real service on a synthetic report:
the model returns boxes as integers from 0 to 1000 (relative to image width and height), and
chat_template_kwargs {"enable_thinking": false} makes it answer directly instead of reasoning first.
The boxes are tight enough to highlight a line, but they are the model's own estimate: the grounding check in
extraction.py and the eval in eval/ are what tell us how far to trust them.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import settings
from services.nvidia_client import chat_completion, compress_image_for_api, file_sha256, image_to_data_url

BOX_SCALE = 1000.0  # the model's box coordinates run 0..1000 across the image

READ_PROMPT = (
    "You are reading a photographed or scanned medical paper: a diabetes lab report or a prescription. "
    "It may be handwritten, and may be in English or Hindi. Transcribe it exactly as written.\n"
    "Return ONLY a JSON array, in reading order. One item per printed or written line. "
    "Text that sits on the same horizontal row of the page belongs in the same item, even when it is far apart "
    "or in a separate column (for example a medicine name and a quantity at the right edge). For a table row, "
    "join the cells from left to right with single spaces into ONE item.\n"
    'Each item is {"text": the exact text, "bbox": [x_min, y_min, x_max, y_max]}. The four numbers are integers '
    "from 0 to 1000, relative to the image width and height: (0, 0) is the top-left corner and (1000, 1000) is "
    "the bottom-right corner. The box must tightly surround that line.\n"
    "If a character is unreadable, write ? in its place. Do not correct, interpret or add anything."
)

# Asks the hosted reasoning models to answer directly instead of spending the token budget on thinking.
NO_THINKING = {"chat_template_kwargs": {"enable_thinking": False}}


@dataclass
class ParsedBlock:
    block_id: str
    text: str
    block_type: str
    xmin: float
    ymin: float
    xmax: float
    ymax: float


def _flatten_blocks(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        if "blocks" in raw and isinstance(raw["blocks"], list):
            return _flatten_blocks(raw["blocks"])
        if "text" in raw or "bbox" in raw:
            return [raw]
        return []
    if isinstance(raw, list):
        out: list[dict[str, Any]] = []
        for item in raw:
            out.extend(_flatten_blocks(item))
        return out
    return []


def _clamp01(val: float) -> float:
    return max(0.0, min(1.0, float(val)))


def _bbox_coords(bbox: Any) -> tuple[float, float, float, float] | None:
    """Accept {xmin,ymin,xmax,ymax} or [xmin, ymin, xmax, ymax]; return None if unusable."""
    try:
        if isinstance(bbox, dict) and all(k in bbox for k in ("xmin", "ymin", "xmax", "ymax")):
            vals = (float(bbox["xmin"]), float(bbox["ymin"]), float(bbox["xmax"]), float(bbox["ymax"]))
        elif isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            vals = tuple(float(v) for v in bbox)  # type: ignore[assignment]
        else:
            return None
    except (TypeError, ValueError):
        return None
    xmin, ymin, xmax, ymax = vals
    if xmax < xmin:
        xmin, xmax = xmax, xmin
    if ymax < ymin:
        ymin, ymax = ymax, ymin
    return xmin, ymin, xmax, ymax


def message_text(response_json: dict[str, Any]) -> str:
    """The assistant's final answer. Reasoning models may leave `content` empty; that counts as no answer."""
    choices = response_json.get("choices") or []
    if not choices:
        return ""
    return str((choices[0].get("message") or {}).get("content") or "")


def _json_from_text(text: str) -> Any:
    """Find the JSON array in a reply that may be wrapped in ``` fences or have words around it."""
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None


def parse_page_response(response_json: dict[str, Any]) -> list[ParsedBlock]:
    """Turn the model's reply into normalised (0..1) ParsedBlocks. Unusable items are skipped, never guessed."""
    raw_blocks = _flatten_blocks(_json_from_text(message_text(response_json)))
    blocks: list[ParsedBlock] = []
    for item in raw_blocks:
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        coords = _bbox_coords(item.get("bbox"))
        if coords is None:
            # No usable box: skip the line rather than pretend it covers the whole page.
            continue
        xmin, ymin, xmax, ymax = (c / BOX_SCALE for c in coords)
        if xmax - xmin <= 0 or ymax - ymin <= 0:
            continue
        blocks.append(
            ParsedBlock(
                block_id=f"b{len(blocks)}",
                text=text,
                block_type="Text",
                xmin=_clamp01(xmin),
                ymin=_clamp01(ymin),
                xmax=_clamp01(xmax),
                ymax=_clamp01(ymax),
            )
        )
    return blocks


def parse_page_image(image_path: Path, use_cache: bool = True, allow_network: bool = True) -> list[ParsedBlock]:
    """Compress the page image and have the vision-language model transcribe it with line boxes."""
    compressed, _, _ = compress_image_for_api(image_path)
    data_url = image_to_data_url(compressed)
    payload = {
        "model": settings.nvidia_parse_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": READ_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": 6000,
        **NO_THINKING,
    }
    raw = chat_completion(payload, use_cache=use_cache, allow_network=allow_network, image_key=file_sha256(image_path))
    return parse_page_response(raw)
