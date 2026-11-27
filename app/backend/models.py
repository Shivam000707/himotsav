"""SQLModel tables for MediKiosk-DM (synthetic data only)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Patient(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    display_name: str
    age: int
    language: str = "hi"
    created_at: datetime = Field(default_factory=utc_now)


class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    kind: str = "unknown"  # lab | rx | unknown
    source_org: Optional[str] = None
    doc_date: Optional[date] = None
    file_path: str
    page_count: int = 1
    status: str = "pending"  # pending | done | failed
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class Page(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="document.id", index=True)
    page_no: int
    image_path: str
    width_px: int
    height_px: int


class Block(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    page_id: int = Field(foreign_key="page.id", index=True)
    block_key: str  # e.g. b0, b1
    text: str
    block_type: str = "Text"
    xmin: float
    ymin: float
    xmax: float
    ymax: float


class Observation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    document_id: int = Field(foreign_key="document.id", index=True)
    page_id: int = Field(foreign_key="page.id")
    block_id: Optional[int] = Field(default=None, foreign_key="block.id")
    test: str
    label_as_written: str
    value_raw: str
    unit_raw: Optional[str] = None
    value_num: Optional[float] = None
    unit_std: Optional[str] = None
    value_std: Optional[float] = None
    converted: bool = False
    obs_date: Optional[date] = None
    uncertain: bool = False
    unverified: bool = False
    note: Optional[str] = None
    verified_by_clinician: bool = False
    edited_value: Optional[str] = None


class Medication(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    source: str = "rx"  # rx | intake
    document_id: Optional[int] = Field(default=None, foreign_key="document.id")
    page_id: Optional[int] = Field(default=None, foreign_key="page.id")
    block_id: Optional[int] = Field(default=None, foreign_key="block.id")
    name_as_written: str
    generic_name: Optional[str] = None
    strength: Optional[str] = None
    frequency: Optional[str] = None
    rx_date: Optional[date] = None
    uncertain: bool = False
    unverified: bool = False
    note: Optional[str] = None
    verified_by_clinician: bool = False
    edited_value: Optional[str] = None


class IntakeAnswer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    question_id: str
    value_json: str
    raw_text: Optional[str] = None
    confirmed: bool = False
    answered_at: datetime = Field(default_factory=utc_now)


class DoctorNote(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", unique=True, index=True)
    text: str = ""
    updated_at: datetime = Field(default_factory=utc_now)
