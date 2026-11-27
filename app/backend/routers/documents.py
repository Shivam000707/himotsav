"""Document upload, extraction, and page image serving routes."""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from config import UPLOADS_DIR
from db import get_session
from models import Block, Document, Medication, Observation, Page, Patient
from services.extraction import extract_page_items, prepare_document_pages
from services.normalize import parse_indian_date

router = APIRouter(prefix="/api", tags=["documents"])

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
MAX_BYTES = 10 * 1024 * 1024


@router.post("/patients/{patient_id}/documents")
async def upload_document(
    patient_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict:
    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    ext = Path(file.filename or "upload.png").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds 10 MB limit")

    doc_folder = UPLOADS_DIR / str(patient_id) / uuid.uuid4().hex[:12]
    doc_folder.mkdir(parents=True, exist_ok=True)
    raw_path = doc_folder / f"original{ext}"
    raw_path.write_bytes(content)

    doc = Document(
        patient_id=patient_id,
        file_path=str(raw_path),
        status="pending",
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)

    created_obs: list[Observation] = []
    created_meds: list[Medication] = []

    try:
        pages_meta = prepare_document_pages(raw_path, doc_folder / "pages")
        doc.page_count = len(pages_meta)

        for page_no, page_path, w_px, h_px in pages_meta:
            page = Page(
                document_id=doc.id,
                page_no=page_no,
                image_path=str(page_path),
                width_px=w_px,
                height_px=h_px,
            )
            session.add(page)
            session.commit()
            session.refresh(page)

            blocks, structured, obs_rows, med_rows = extract_page_items(page_path)

            if page_no == 1:
                doc.kind = structured.kind
                doc.source_org = structured.source_org
                parsed_doc_date, _ = parse_indian_date(structured.doc_date)
                doc.doc_date = parsed_doc_date

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
                session.commit()
                session.refresh(db_block)
                block_key_to_id[b.block_id] = db_block.id

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

        doc.status = "done"
        session.commit()
    except Exception as exc:
        doc.status = "failed"
        doc.error = str(exc)
        session.commit()

    session.refresh(doc)
    for o in created_obs:
        session.refresh(o)
    for m in created_meds:
        session.refresh(m)

    return {
        "document": doc,
        "observations": created_obs,
        "medications": created_meds,
    }


@router.get("/documents/{doc_id}/pages/{page_no}/image")
def get_page_image(
    doc_id: int,
    page_no: int,
    session: Session = Depends(get_session),
) -> FileResponse:
    page = session.exec(
        select(Page).where(Page.document_id == doc_id, Page.page_no == page_no)
    ).first()
    if not page or not Path(page.image_path).exists():
        raise HTTPException(status_code=404, detail="Page image not found")
    return FileResponse(page.image_path, media_type="image/png")
