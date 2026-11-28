"""Doctor dashboard routes: timeline, rules, summary, edits, and notes."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from config import settings
from db import get_session
from models import Block, DoctorNote, Document, IntakeAnswer, Medication, Observation, Page, Patient, PlanItem
from schemas import ClinicianPatch, DoctorNoteUpdate, PlanUpdate
from services.rules import evaluate
from services.summary import build_summary
from services.trends import PLAN_TESTS, dated_points, medicine_events, trend_stats

router = APIRouter(prefix="/api", tags=["doctor"])


def _load_patient_bundle(patient_id: int, session: Session) -> dict[str, Any]:
    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    docs = {d.id: d for d in session.exec(select(Document).where(Document.patient_id == patient_id)).all()}
    pages = {
        p.id: p
        for p in session.exec(select(Page).where(Page.document_id.in_(list(docs.keys()) or [-1]))).all()
    }
    blocks = {
        b.id: b
        for b in session.exec(select(Block).where(Block.page_id.in_(list(pages.keys()) or [-1]))).all()
    }

    obs_list = session.exec(select(Observation).where(Observation.patient_id == patient_id)).all()
    med_list = session.exec(select(Medication).where(Medication.patient_id == patient_id)).all()
    ans_list = session.exec(select(IntakeAnswer).where(IntakeAnswer.patient_id == patient_id)).all()
    note = session.exec(select(DoctorNote).where(DoctorNote.patient_id == patient_id)).first()
    plan_rows = session.exec(select(PlanItem).where(PlanItem.patient_id == patient_id)).all()

    def attach_source(row_dict: dict[str, Any], doc_id: int | None, page_id: int | None, block_id: int | None) -> dict[str, Any]:
        doc = docs.get(doc_id) if doc_id else None
        page = pages.get(page_id) if page_id else None
        block = blocks.get(block_id) if block_id else None
        row_dict["source_org"] = doc.source_org if doc else None
        row_dict["source_mode"] = doc.source_mode if doc else None
        row_dict["page_no"] = page.page_no if page else 1
        row_dict["page_w"] = page.width_px if page else None
        row_dict["page_h"] = page.height_px if page else None
        row_dict["block_text"] = block.text if block else None
        row_dict["bbox"] = (
            {"xmin": block.xmin, "ymin": block.ymin, "xmax": block.xmax, "ymax": block.ymax}
            if block
            else None
        )
        return row_dict

    observations = [attach_source(o.model_dump(), o.document_id, o.page_id, o.block_id) for o in obs_list]
    medications = [attach_source(m.model_dump(), m.document_id, m.page_id, m.block_id) for m in med_list]
    answers = [a.model_dump() for a in ans_list]

    documents = []
    for d in sorted(docs.values(), key=lambda d: (d.doc_date or date.min, d.id)):
        documents.append(
            {
                "id": d.id,
                "kind": d.kind,
                "source_org": d.source_org,
                "doc_date": d.doc_date,
                "status": d.status,
                "error": d.error,
                "page_count": d.page_count,
                "source_mode": d.source_mode,
                "original_filename": d.original_filename,
                "n_observations": sum(1 for o in obs_list if o.document_id == d.id),
                "n_medications": sum(1 for m in med_list if m.document_id == d.id),
            }
        )

    return {
        "patient": patient.model_dump(),
        "observations": observations,
        "medications": medications,
        "answers": answers,
        "documents": documents,
        "doctor_note": note.text if note else "",
        "plan": [p.model_dump() for p in sorted(plan_rows, key=lambda p: p.test)],
    }


@router.get("/patients/{patient_id}/timeline")
def get_timeline(patient_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    bundle = _load_patient_bundle(patient_id, session)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for obs in bundle["observations"]:
        grouped.setdefault(obs["test"], []).append(obs)
    for test_name in grouped:
        grouped[test_name].sort(key=lambda o: (o.get("obs_date") or date.min, o["id"]))

    meds = sorted(bundle["medications"], key=lambda m: (m.get("rx_date") or date.min, m["id"]))
    trends = {t: trend_stats(dated_points(bundle["observations"], t)) for t in grouped if t in PLAN_TESTS}
    return {
        "observations_by_test": grouped,
        "medications": meds,
        "trends": trends,
        "medicine_events": medicine_events(bundle["medications"]),
        "plan": bundle["plan"],
    }


@router.get("/patients/{patient_id}/rules")
def get_rules(patient_id: int, session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    bundle = _load_patient_bundle(patient_id, session)
    results = evaluate(bundle, today=settings.today)
    return [r.__dict__ for r in results]


@router.get("/patients/{patient_id}/summary")
def get_summary(patient_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    bundle = _load_patient_bundle(patient_id, session)
    return build_summary(
        patient=bundle["patient"],
        observations=bundle["observations"],
        medications=bundle["medications"],
        answers=bundle["answers"],
        doctor_note=bundle["doctor_note"],
        today=settings.today,
        documents=bundle["documents"],
        plan=bundle["plan"],
    )


@router.patch("/observations/{obs_id}")
def patch_observation(
    obs_id: int,
    payload: ClinicianPatch,
    session: Session = Depends(get_session),
) -> Observation:
    obs = session.get(Observation, obs_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")
    if payload.edited_value is not None:
        obs.edited_value = payload.edited_value.strip() or None
    if payload.verified_by_clinician is not None:
        obs.verified_by_clinician = payload.verified_by_clinician
    session.add(obs)
    session.commit()
    session.refresh(obs)
    return obs


@router.patch("/medications/{med_id}")
def patch_medication(
    med_id: int,
    payload: ClinicianPatch,
    session: Session = Depends(get_session),
) -> Medication:
    med = session.get(Medication, med_id)
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")
    if payload.edited_value is not None:
        med.edited_value = payload.edited_value.strip() or None
    if payload.verified_by_clinician is not None:
        med.verified_by_clinician = payload.verified_by_clinician
    session.add(med)
    session.commit()
    session.refresh(med)
    return med


@router.put("/patients/{patient_id}/note")
def put_doctor_note(
    patient_id: int,
    payload: DoctorNoteUpdate,
    session: Session = Depends(get_session),
) -> DoctorNote:
    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    note = session.exec(select(DoctorNote).where(DoctorNote.patient_id == patient_id)).first()
    if note:
        note.text = payload.text
        note.updated_at = datetime.now(timezone.utc)
    else:
        note = DoctorNote(patient_id=patient_id, text=payload.text)
    session.add(note)
    session.commit()
    session.refresh(note)
    return note


@router.put("/patients/{patient_id}/plan/{test}")
def put_plan_item(
    patient_id: int,
    test: str,
    payload: PlanUpdate,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Set the doctor's target, review margin and test interval for one test. Empty fields are cleared,
    and a row with nothing left is removed."""
    if not session.get(Patient, patient_id):
        raise HTTPException(status_code=404, detail="Patient not found")
    if test not in PLAN_TESTS:
        raise HTTPException(status_code=400, detail=f"Unknown test: {test}")
    item = session.exec(select(PlanItem).where(PlanItem.patient_id == patient_id, PlanItem.test == test)).first()
    empty = all(v is None for v in (payload.target_low, payload.target_high, payload.review_margin, payload.interval_days))
    if empty:
        if item:
            session.delete(item)
            session.commit()
        return {"test": test, "removed": True}
    if item is None:
        item = PlanItem(patient_id=patient_id, test=test)
    item.target_low = payload.target_low
    item.target_high = payload.target_high
    item.review_margin = payload.review_margin
    item.interval_days = payload.interval_days
    item.updated_at = datetime.now(timezone.utc)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item.model_dump()
