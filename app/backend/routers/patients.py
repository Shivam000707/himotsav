"""Patient CRUD routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from db import get_session
from models import Patient
from schemas import PatientCreate

router = APIRouter(prefix="/api", tags=["patients"])


@router.post("/patients")
def create_patient(payload: PatientCreate, session: Session = Depends(get_session)) -> Patient:
    patient = Patient(
        display_name=payload.display_name,
        age=payload.age,
        language=payload.language,
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


@router.get("/patients")
def list_patients(session: Session = Depends(get_session)) -> list[Patient]:
    return list(session.exec(select(Patient).order_by(Patient.id.desc())).all())


@router.get("/patients/{patient_id}")
def get_patient(patient_id: int, session: Session = Depends(get_session)) -> Patient:
    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient
