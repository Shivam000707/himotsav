"""Document extraction orchestrator: save -> compress -> parse -> structure -> verify -> normalize."""
from __future__ import annotations

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


def prepare_document_pages(src_path: Path, out_dir: Path) -> list[tuple[int, Path, int, int]]:
    """Convert PDF (150 dpi) or image (EXIF-fixed) into page PNGs. Returns (page_no, path, w, h)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = src_path.suffix.lower()
    pages: list[tuple[int, Path, int, int]] = []

    if suffix == ".pdf":
        pdf = pdfium.PdfDocument(str(src_path))
        scale = 150.0 / 72.0
        for idx in range(len(pdf)):
            page = pdf[idx]
            pil_img = page.render(scale=scale).to_pil().convert("RGB")
            page_path = out_dir / f"page_{idx + 1}.png"
            pil_img.save(page_path, format="PNG")
            pages.append((idx + 1, page_path, pil_img.width, pil_img.height))
        return pages

    with Image.open(src_path) as raw:
        img = ImageOps.exif_transpose(raw).convert("RGB")
        page_path = out_dir / "page_1.png"
        img.save(page_path, format="PNG")
        pages.append((1, page_path, img.width, img.height))
    return pages


def verify_grounding(needle: str, block_id: Optional[str], blocks: list[ParsedBlock]) -> tuple[Optional[str], bool]:
    """Verify needle appears in block_id (partial_ratio >= 90); else search all blocks.

    Returns (resolved_block_id, unverified).
    """
    if not needle or not blocks:
        return None, True

    by_id = {b.block_id: b for b in blocks}
    needle_l = needle.strip().lower()

    if block_id and block_id in by_id:
        score = fuzz.partial_ratio(needle_l, by_id[block_id].text.lower())
        if score >= 90:
            return block_id, False

    best_id: Optional[str] = None
    best_score = 0.0
    for b in blocks:
        score = fuzz.partial_ratio(needle_l, b.text.lower())
        if score > best_score:
            best_score = score
            best_id = b.block_id

    if best_score >= 90 and best_id is not None:
        return best_id, False
    return None, True


def extract_page_items(
    page_image_path: Path,
    use_cache: bool = True,
    allow_network: bool = True,
) -> tuple[list[ParsedBlock], StructuredPage, list[dict], list[dict]]:
    """Run parse -> structure -> verify grounding -> normalize on a single page image."""
    blocks = parse_page_image(page_image_path, use_cache=use_cache, allow_network=allow_network)

    if len(blocks) < 3:
        structured = structure_from_image_fallback(page_image_path, use_cache=use_cache, allow_network=allow_network)
    else:
        structured = structure_from_blocks(blocks, use_cache=use_cache, allow_network=allow_network)
        if structured.kind == "rx" and not structured.medications:
            structured = structure_from_image_fallback(page_image_path, use_cache=use_cache, allow_network=allow_network)

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
