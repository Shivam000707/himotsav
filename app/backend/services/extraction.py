"""Document extraction orchestrator: save -> compress -> parse -> structure -> verify -> normalize."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import pypdfium2 as pdfium
from PIL import Image, ImageOps
from rapidfuzz import fuzz

from services.normalize import (
    canonicalize_test,
    convert_unit,
    map_brand_to_generic,
    parse_indian_date,
)
from services.parse import ParsedBlock, parse_page_image
from services.structure import (
    StructuredPage,
    structure_from_blocks,
    structure_from_image_fallback,
)

log = logging.getLogger("medikiosk.extraction")


class TooManyPagesError(ValueError):
    pass


def prepare_document_pages(src_path: Path, out_dir: Path, max_pages: int = 5) -> list[tuple[int, Path, int, int]]:
    """Convert PDF (150 dpi) or image (EXIF-fixed) into page PNGs. Returns (page_no, path, w, h)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = src_path.suffix.lower()
    pages: list[tuple[int, Path, int, int]] = []

    if suffix == ".pdf":
        pdf = pdfium.PdfDocument(str(src_path))
        try:
            if len(pdf) > max_pages:
                raise TooManyPagesError(f"Please upload at most {max_pages} pages per document (this PDF has {len(pdf)}).")
            scale = 150.0 / 72.0
            for idx in range(len(pdf)):
                page = pdf[idx]
                pil_img = page.render(scale=scale).to_pil().convert("RGB")
                page_path = out_dir / f"page_{idx + 1}.png"
                pil_img.save(page_path, format="PNG")
                pages.append((idx + 1, page_path, pil_img.width, pil_img.height))
        finally:
            pdf.close()
        return pages

    with Image.open(src_path) as raw:
        img = ImageOps.exif_transpose(raw).convert("RGB")
    # Phone photos can be 4000+ px: keep a 2200 px copy for display and extraction.
    max_side = 2200
    if max(img.size) > max_side:
        scale = max_side / float(max(img.size))
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.Resampling.LANCZOS)
    page_path = out_dir / "page_1.png"
    img.save(page_path, format="PNG")
    pages.append((1, page_path, img.width, img.height))
    return pages


_NUMBER_RE = re.compile(r"^[<>]?\s*\d+(?:[.,]\d+)?$")


def _block_contains(needle: str, text: str) -> bool:
    """True if needle appears in text.

    Numbers must appear as a whole number ("24" does not match inside "2024" or "1.24"),
    because a fuzzy match on short digit strings would link values to the wrong place.
    Words use a fuzzy partial match (>= 90) to tolerate small reading differences.
    """
    needle = needle.strip()
    if not needle:
        return False
    if _NUMBER_RE.match(needle):
        num = re.sub(r"^[<>]\s*", "", needle)
        pattern = r"(?<![\d.,])" + re.escape(num) + r"(?![\d]|[.,]\d)"
        return re.search(pattern, text) is not None
    return fuzz.partial_ratio(needle.lower(), text.lower()) >= 90


def verify_grounding(needle: str, block_id: Optional[str], blocks: list[ParsedBlock]) -> tuple[Optional[str], bool]:
    """Check that a value really appears in the block the model pointed to.

    If it does not, look for exactly one other block that contains it. Returns
    (resolved_block_id, unverified). A value that cannot be tied to a block is unverified.
    """
    if not needle or not needle.strip() or not blocks:
        return None, True

    by_id = {b.block_id: b for b in blocks}
    if block_id and block_id in by_id and _block_contains(needle, by_id[block_id].text):
        return block_id, False

    matches = [b.block_id for b in blocks if _block_contains(needle, b.text)]
    if len(matches) == 1:
        return matches[0], False
    # Zero matches: not on the page. Several matches: we cannot tell which one is meant.
    return None, True


def extract_page_items(
    page_image_path: Path,
    use_cache: bool = True,
    allow_network: bool = True,
) -> tuple[list[ParsedBlock], StructuredPage, list[dict], list[dict]]:
    """Run parse -> structure -> verify grounding -> normalize on a single page image."""
    blocks = parse_page_image(page_image_path, use_cache=use_cache, allow_network=allow_network)

    if len(blocks) < 3:
        log.info("Parse returned %d blocks for %s: using the vision fallback", len(blocks), page_image_path.name)
        structured = structure_from_image_fallback(page_image_path, use_cache=use_cache, allow_network=allow_network)
    else:
        structured = structure_from_blocks(blocks, use_cache=use_cache, allow_network=allow_network)
        if structured.kind == "rx" and not structured.medications:
            log.info("No medicines found in prescription blocks for %s: trying the vision fallback", page_image_path.name)
            try:
                fallback = structure_from_image_fallback(
                    page_image_path, use_cache=use_cache, allow_network=allow_network
                )
                if fallback.medications:
                    structured = fallback
            except Exception as exc:  # keep the block-based result if the fallback fails
                log.warning("Vision fallback failed for %s: %s", page_image_path.name, exc)

    doc_date, date_note = parse_indian_date(structured.doc_date)

    obs_rows: list[dict] = []
    for obs in structured.observations:
        resolved_block_id, unverified = verify_grounding(obs.value, obs.block_id, blocks)
        test_name = canonicalize_test(obs.label)
        conv = convert_unit(test_name, obs.value, obs.unit)
        notes = [n for n in [obs.note, conv.note, date_note] if n]
        obs_rows.append(
            {
                "test": test_name,
                "label_as_written": obs.label,
                "value_raw": obs.value,
                "unit_raw": obs.unit,
                "value_num": conv.value_num,
                "unit_std": conv.unit_std,
                "value_std": conv.value_std,
                "converted": conv.converted,
                "obs_date": doc_date,
                "block_id": resolved_block_id,
                "uncertain": bool(obs.uncertain or conv.uncertain),
                "unverified": unverified,
                "note": "; ".join(notes) if notes else None,
            }
        )

    med_rows: list[dict] = []
    for med in structured.medications:
        resolved_block_id, unverified = verify_grounding(med.name, med.block_id, blocks)
        generic = map_brand_to_generic(med.name)
        notes = [n for n in [med.note, date_note] if n]
        med_rows.append(
            {
                "name_as_written": med.name,
                "generic_name": generic,
                "strength": med.strength,
                "frequency": med.frequency,
                "rx_date": doc_date,
                "block_id": resolved_block_id,
                "uncertain": bool(med.uncertain),
                "unverified": unverified,
                "note": "; ".join(notes) if notes else None,
            }
        )

    return blocks, structured, obs_rows, med_rows
