"""Save one extracted page (blocks, observations, medications) to the database.

Shared by the upload route and the demo seeding route, so both go through exactly the
same pipeline: Nemotron Parse -> LLM structuring -> grounding check -> normalisation.
"""
from __future__ import annotations

from pathlib import Path

from sqlmodel import Session

from models import Block, Document, Medication, Observation, Page
from services.extraction import extract_page_items
from services.normalize import parse_indian_date


def ingest_page(
    session: Session,
    *,
    patient_id: int,
    doc: Document,
    page: Page,
    use_cache: bool = True,
    allow_network: bool = True,
) -> tuple[list[Observation], list[Medication]]:
    """Extract one page with the AI pipeline and store everything it found.

    On page 1 the document's kind, lab or doctor name and date are filled from the extraction.
    Raises if extraction fails; the caller decides how to mark the document.
    """
    blocks, structured, obs_rows, med_rows = extract_page_items(
        Path(page.image_path), use_cache=use_cache, allow_network=allow_network
    )

    if page.page_no == 1:
        doc.kind = structured.kind
        doc.source_org = structured.source_org
        doc.doc_date, _ = parse_indian_date(structured.doc_date)
        session.add(doc)

    block_key_to_id: dict[str, int] = {}
    for b in blocks:
        db_block = Block(
            page_id=page.id,
            block_key=b.block_id,
            text=b.text,
            block_type=b.block_type,
            xmin=b.xmin,
            ymin=b.ymin,
            xmax=b.xmax,
            ymax=b.ymax,
        )
        session.add(db_block)
        session.flush()
        block_key_to_id[b.block_id] = db_block.id

    created_obs: list[Observation] = []
    for o in obs_rows:
        db_obs = Observation(
            patient_id=patient_id,
            document_id=doc.id,
            page_id=page.id,
            block_id=block_key_to_id.get(o["block_id"]) if o["block_id"] else None,
            test=o["test"],
            label_as_written=o["label_as_written"],
            value_raw=o["value_raw"],
            unit_raw=o["unit_raw"],
            value_num=o["value_num"],
            unit_std=o["unit_std"],
            value_std=o["value_std"],
            converted=o["converted"],
            obs_date=o["obs_date"] or doc.doc_date,
            uncertain=o["uncertain"],
            unverified=o["unverified"],
            note=o["note"],
        )
        session.add(db_obs)
        created_obs.append(db_obs)

    created_meds: list[Medication] = []
    for m in med_rows:
        db_med = Medication(
            patient_id=patient_id,
            source="rx",
            document_id=doc.id,
            page_id=page.id,
            block_id=block_key_to_id.get(m["block_id"]) if m["block_id"] else None,
            name_as_written=m["name_as_written"],
            generic_name=m["generic_name"],
            strength=m["strength"],
            frequency=m["frequency"],
            rx_date=m["rx_date"] or doc.doc_date,
            uncertain=m["uncertain"],
            unverified=m["unverified"],
            note=m["note"],
        )
        session.add(db_med)
        created_meds.append(db_med)

    session.flush()
    return created_obs, created_meds
