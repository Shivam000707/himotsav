"""Pydantic request and response schemas."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


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


class PlanUpdate(BaseModel):
    """The doctor's numbers for one test. Any field left empty is cleared."""

    target_low: Optional[float] = Field(default=None, ge=0, le=100000)
    target_high: Optional[float] = Field(default=None, ge=0, le=100000)
    review_margin: Optional[float] = Field(default=None, gt=0, le=100000)
    interval_days: Optional[int] = Field(default=None, ge=7, le=1825)

    @model_validator(mode="after")
    def _low_not_above_high(self) -> "PlanUpdate":
        if self.target_low is not None and self.target_high is not None and self.target_low > self.target_high:
            raise ValueError("The lower target must not be above the upper target")
        return self


class DoctorNoteUpdate(BaseModel):
    text: str = Field(max_length=10000)
