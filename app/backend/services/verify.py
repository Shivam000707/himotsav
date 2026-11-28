"""Second reading: a different model re-reads each value's line from a zoomed crop.

Why: the first reader can misread handwriting and still sound sure. On a real handwritten note it read
"RBS 50 mg/dl" as 10 and reported it as clear. The grounding check cannot catch that, because the wrong
number really is in the line the model wrote. Two independent readers rarely make the same mistake, so a
disagreement on a number is a good reason to ask the doctor to look. This is plain code comparing numbers;
the second reader only transcribes.

A value is never changed here. It is only marked unsure, with the second reading in the note, so the doctor
sees both readings. If the second reader is unavailable, nothing is marked: the check is skipped, not failed.
"""
from __future__ import annotations

import hashlib
import io
import logging
import re
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageOps

from config import settings
from services.nvidia_client import chat_completion, file_sha256, image_to_data_url
from services.parse import NO_THINKING, ParsedBlock, message_text

log = logging.getLogger("medikiosk.verify")

VERIFY_PROMPT = (
    "This is a crop of one line from a hospital or lab paper, possibly handwritten. "
    "Transcribe exactly what is written, including every number. "
    "Write ? for any character you cannot read. Return only the text, nothing else."
)

_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_FREQ = re.compile(r"\d\s*-\s*\d\s*-\s*\d")


def numbers_in(text: str) -> set[float]:
    return {float(n) for n in _NUMBER.findall(text or "")}


def _compact_frequency(text: str) -> Optional[str]:
    m = _FREQ.search(text or "")
    return re.sub(r"\s+", "", m.group(0)) if m else None


def crop_line(page_image: Path, block: ParsedBlock, max_side: int = 1600) -> Image.Image:
    """The line's box with a little margin, enlarged so small handwriting is easier to read."""
    with Image.open(page_image) as raw:
        img = ImageOps.exif_transpose(raw).convert("RGB")
    w, h = img.size
    pad_x = 0.012
    pad_y = max(0.006, (block.ymax - block.ymin) * 0.35)
    box = (
        int(max(0.0, block.xmin - pad_x) * w),
        int(max(0.0, block.ymin - pad_y) * h),
        int(min(1.0, block.xmax + pad_x) * w),
        int(min(1.0, block.ymax + pad_y) * h),
    )
    crop = img.crop(box)
    scale = min(3.0, max_side / max(crop.size))
    if scale > 1.0:
        crop = crop.resize((int(crop.width * scale), int(crop.height * scale)), Image.Resampling.LANCZOS)
    return crop


def read_line_again(
    page_image: Path, block: ParsedBlock, use_cache: bool = True, allow_network: bool = True
) -> Optional[str]:
    """The second reader's transcription of one line, or None if it is unavailable."""
    model = settings.nvidia_verify_model
    if not model:
        return None
    try:
        crop = crop_line(page_image, block)
        buf = io.BytesIO()
        crop.save(buf, format="JPEG", quality=90)
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VERIFY_PROMPT},
                        {"type": "image_url", "image_url": {"url": image_to_data_url(buf.getvalue())}},
                    ],
                }
            ],
            "temperature": 0,
            "max_tokens": 300,
            **NO_THINKING,
        }
        box_id = f"{block.xmin:.4f},{block.ymin:.4f},{block.xmax:.4f},{block.ymax:.4f}"
        image_key = hashlib.sha256(f"{file_sha256(page_image)}:{box_id}".encode()).hexdigest()
        reply = chat_completion(payload, use_cache=use_cache, allow_network=allow_network, image_key=image_key)
        text = message_text(reply).strip()
        return text or None
    except Exception as exc:  # noqa: BLE001  the check must never break an upload
        log.warning("Second reading skipped for %s: %s", page_image.name, exc)
        return None


def _flag(row: dict[str, Any], second_text: str, what: str) -> None:
    row["uncertain"] = True
    note = f'Second reading of this line disagrees on the {what}: it read "{second_text[:90]}"'
    row["note"] = f"{row['note']}; {note}" if row.get("note") else note


def cross_check_rows(
    page_image: Path,
    blocks: list[ParsedBlock],
    obs_rows: list[dict[str, Any]],
    med_rows: list[dict[str, Any]],
    use_cache: bool = True,
    allow_network: bool = True,
) -> int:
    """Mark rows unsure where a second reading of their line disagrees. Returns how many rows were marked."""
    by_id = {b.block_id: b for b in blocks}
    rows_by_block: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for kind, rows in (("obs", obs_rows), ("med", med_rows)):
        for row in rows:
            if row.get("block_id") in by_id:
                rows_by_block.setdefault(row["block_id"], []).append((kind, row))

    marked = 0
    for block_id, items in rows_by_block.items():
        second = read_line_again(page_image, by_id[block_id], use_cache=use_cache, allow_network=allow_network)
        if second is None:
            continue
        second_numbers = numbers_in(second)
        second_freq = _compact_frequency(second)
        # A dose must not be "confirmed" by the digits of a timing such as 1-0-0.
        second_dose_numbers = numbers_in(_FREQ.sub(" ", second))
        for kind, row in items:
            if row.get("uncertain"):
                continue  # already going to the doctor
            if kind == "obs":
                first = numbers_in(str(row.get("value_raw") or ""))
                if first and not first <= second_numbers:
                    _flag(row, second, "number")
                    marked += 1
            else:
                first_strength = numbers_in(str(row.get("strength") or ""))
                if first_strength and not first_strength <= second_dose_numbers:
                    _flag(row, second, "dose")
                    marked += 1
                    continue
                first_freq = _compact_frequency(str(row.get("frequency") or ""))
                if first_freq and second_freq and first_freq != second_freq:
                    _flag(row, second, "timing")
                    marked += 1
    return marked
