"""Document upload, extraction, and page image serving routes."""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
import pypdfium2 as pdfium
from PIL import UnidentifiedImageError
from sqlmodel import Session, select

from config import UPLOADS_DIR, settings
from db import get_session
from models import Document, Page, Patient
from services.extraction import TooManyPagesError, prepare_document_pages
from services.ingest import ingest_page

router = APIRouter(prefix="/api", tags=["documents"])
log = logging.getLogger("medikiosk.documents")

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 5


# Declared with `def`, not `async def`: extraction makes slow, blocking calls to NVIDIA, and
# FastAPI runs plain `def` routes in a worker thread so the rest of the app stays responsive.
@router.post("/patients/{patient_id}/documents")
def upload_document(
    patient_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict:
    if settings.public_demo:
        raise HTTPException(
            status_code=403,
            detail="Uploads are switched off on the public demo. Run the app on your own machine to read new papers.",
        )
    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    ext = Path(file.filename or "upload.png").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext or 'none'}. Use JPG, PNG, WebP or PDF.")

    content = file.file.read(MAX_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="The file is empty")
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds 10 MB limit")

    doc_folder = UPLOADS_DIR / str(patient_id) / uuid.uuid4().hex[:12]
    doc_folder.mkdir(parents=True, exist_ok=True)
    raw_path = doc_folder / f"original{ext}"
    raw_path.write_bytes(content)

    try:
        pages_meta = prepare_document_pages(raw_path, doc_folder / "pages", max_pages=MAX_PAGES)
    except TooManyPagesError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (UnidentifiedImageError, OSError, ValueError, pdfium.PdfiumError) as exc:
        raise HTTPException(status_code=400, detail=f"Could not open the file as an image or PDF: {exc}") from exc
    if not pages_meta:
        raise HTTPException(status_code=400, detail="The PDF has no pages")

    doc = Document(
        patient_id=patient_id,
        file_path=str(raw_path),
        page_count=len(pages_meta),
        status="pending",
        source_mode="ai",
        original_filename=(file.filename or "")[:200] or None,
    )
    session.add(doc)
    session.flush()
    pages: list[Page] = []
    for page_no, page_path, w_px, h_px in pages_meta:
        page = Page(document_id=doc.id, page_no=page_no, image_path=str(page_path), width_px=w_px, height_px=h_px)
        session.add(page)
        pages.append(page)
    # Commit the document and its page images first, so a failed read can still be shown to staff.
    session.commit()

    created_obs = []
    created_meds = []
    try:
        for page in pages:
            obs, meds = ingest_page(session, patient_id=patient_id, doc=doc, page=page)
            created_obs.extend(obs)
            created_meds.extend(meds)
        doc.status = "done"
        doc.error = None
        session.add(doc)
        session.commit()
    except Exception as exc:  # extraction errors must not lose the upload
        log.exception("Extraction failed for document %s", doc.id)
        session.rollback()
        doc = session.get(Document, doc.id)
        doc.status = "failed"
        doc.error = str(exc)[:1000]
        session.add(doc)
        session.commit()
        created_obs, created_meds = [], []

    session.refresh(doc)
    for row in [*created_obs, *created_meds]:
        session.refresh(row)

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
    media_type = "image/png" if page.image_path.lower().endswith(".png") else "image/jpeg"
    return FileResponse(page.image_path, media_type=media_type)
