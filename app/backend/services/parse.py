"""Nemotron Parse wrapper and response block parser.

Expected response shape:
choices[0].message.tool_calls[0].function.arguments -> JSON string containing
a list (or nested lists) of blocks with {bbox: {xmin, ymin, xmax, ymax}, text, type}.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import settings
from services.nvidia_client import chat_completion, compress_image_for_api, image_to_data_url


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


def parse_nemotron_response(response_json: dict[str, Any], img_w: int = 1, img_h: int = 1) -> list[ParsedBlock]:
    """Extract normalised ParsedBlock list from Nemotron Parse raw JSON response."""
    choices = response_json.get("choices") or []
    if not choices:
        return []

    message = choices[0].get("message") or {}
    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        content = message.get("content")
        if not content:
            return []
        try:
            raw_parsed = json.loads(content)
        except json.JSONDecodeError:
            return []
    else:
        args = (tool_calls[0].get("function") or {}).get("arguments", "[]")
        raw_parsed = json.loads(args) if isinstance(args, str) else args

    raw_blocks = _flatten_blocks(raw_parsed)
    blocks: list[ParsedBlock] = []
    for idx, item in enumerate(raw_blocks):
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        bbox = item.get("bbox") or {}
        xmin = float(bbox.get("xmin", 0.0))
        ymin = float(bbox.get("ymin", 0.0))
        xmax = float(bbox.get("xmax", 1.0))
        ymax = float(bbox.get("ymax", 1.0))

        # If coordinates appear to be pixel coordinates (> 1.0), normalise by image dimensions.
        if max(abs(xmin), abs(ymin), abs(xmax), abs(ymax)) > 1.5 and img_w > 0 and img_h > 0:
            xmin /= img_w
            xmax /= img_w
            ymin /= img_h
            ymax /= img_h

        blocks.append(
            ParsedBlock(
                block_id=f"b{len(blocks)}",
                text=text,
                block_type=str(item.get("type") or "Text"),
                xmin=_clamp01(xmin),
                ymin=_clamp01(ymin),
                xmax=_clamp01(xmax),
                ymax=_clamp01(ymax),
            )
        )
    return blocks


def parse_page_image(image_path: Path, use_cache: bool = True, allow_network: bool = True) -> list[ParsedBlock]:
    """Compress image and call Nemotron Parse."""
    compressed, orig_w, orig_h = compress_image_for_api(image_path)
    data_url = image_to_data_url(compressed)
    payload = {
        "model": settings.nvidia_parse_model,
        "messages": [{"role": "user", "content": f'<img src="{data_url}"/>'}],
        "tools": [{"type": "function", "function": {"name": "markdown_bbox"}}],
        "tool_choice": {"type": "function", "function": {"name": "markdown_bbox"}},
        "max_tokens": 4096,
    }
    raw = chat_completion(payload, use_cache=use_cache, allow_network=allow_network)
    return parse_nemotron_response(raw, img_w=orig_w, img_h=orig_h)
