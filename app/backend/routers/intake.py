"""Intake questions and answer upsert routes."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from db import get_session
from models import IntakeAnswer, Medication, Patient
from schemas import AnswerUpsert
from services.normalize import map_brand_to_generic
from services.summary import load_questions

router = APIRouter(prefix="/api", tags=["intake"])


@router.get("/intake/questions")
def get_questions(lang: str = Query(default="hi")) -> list[dict]:
    questions = load_questions()
    out = []
    for q in questions:
        text = q["text_hi"] if lang == "hi" else q["text_en"]
        opts = []
        for opt in q.get("options") or []:
            opts.append(
                {
                    "value": opt["value"],
                    "label": opt["label_hi"] if lang == "hi" else opt["label_en"],
                }
            )
        out.append({**q, "text": text, "options": opts})
    return out


@router.post("/patients/{patient_id}/answers")
def upsert_answer(
    patient_id: int,
    payload: AnswerUpsert,
    session: Session = Depends(get_session),
) -> IntakeAnswer:
    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    existing = session.exec(
        select(IntakeAnswer).where(
            IntakeAnswer.patient_id == patient_id,
            IntakeAnswer.question_id == payload.question_id,
        )
    ).first()

    val_json = json.dumps(payload.value, ensure_ascii=False)
    if existing:
        existing.value_json = val_json
        existing.raw_text = payload.raw_text
        existing.confirmed = payload.confirmed
        existing.answered_at = datetime.now(timezone.utc)
        ans = existing
    else:
        ans = IntakeAnswer(
            patient_id=patient_id,
            question_id=payload.question_id,
            value_json=val_json,
            raw_text=payload.raw_text,
            confirmed=payload.confirmed,
        )
        session.add(ans)

    # Sync current_meds to Medication(source='intake') when confirmed
    if payload.question_id == "current_meds" and payload.confirmed:
        old_intake_meds = session.exec(
            select(Medication).where(
                Medication.patient_id == patient_id,
                Medication.source == "intake",
            )
        ).all()
        for m in old_intake_meds:
            session.delete(m)

        meds_list = payload.value if isinstance(payload.value, list) else (
            payload.value.get("selected", []) if isinstance(payload.value, dict) else []
        )
        for item in meds_list:
            if isinstance(item, str):
                if item == "dont_know":
                    continue
                name, freq = item, None
            elif isinstance(item, dict):
                name = str(item.get("name") or "").strip()
                freq = item.get("frequency")
            else:
                continue
            if not name:
                continue
            session.add(
                Medication(
                    patient_id=patient_id,
                    source="intake",
                    name_as_written=name,
                    generic_name=map_brand_to_generic(name),
                    frequency=freq,
                )
            )

    session.commit()
    session.refresh(ans)
    return ans
