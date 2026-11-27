"""Pydantic request and response schemas."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class PatientCreate(BaseModel):
    display_name: str
    age: int
    language: str = "hi"


class AnswerUpsert(BaseModel):
    question_id: str
    value: Any
    raw_text: Optional[str] = None
    confirmed: bool = False


class ClinicianPatch(BaseModel):
    edited_value: Optional[str] = None
    verified_by_clinician: Optional[bool] = None


class DoctorNoteUpdate(BaseModel):
    text: str
