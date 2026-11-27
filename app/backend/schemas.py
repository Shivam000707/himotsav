"""Pydantic request and response schemas."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class PatientCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=0, le=120)
    language: Literal["hi", "en"] = "hi"


class AnswerUpsert(BaseModel):
    question_id: str = Field(min_length=1, max_length=64)
    value: Any
    raw_text: Optional[str] = Field(default=None, max_length=2000)
    confirmed: bool = False


class ClinicianPatch(BaseModel):
    edited_value: Optional[str] = Field(default=None, max_length=200)
    verified_by_clinician: Optional[bool] = None


class DoctorNoteUpdate(BaseModel):
    text: str = Field(max_length=10000)
