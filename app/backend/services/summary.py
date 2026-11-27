"""Deterministic doctor summary builder."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from services.rules import evaluate

RESOURCES_DIR = Path(__file__).resolve().parent.parent / "resources"


def load_questions() -> list[dict[str, Any]]:
    return json.loads((RESOURCES_DIR / "questions.json").read_text(encoding="utf-8"))


def build_summary(
    patient: dict[str, Any],
    observations: list[dict[str, Any]],
    medications: list[dict[str, Any]],
    answers: list[dict[str, Any]],
    doctor_note: str,
    today: date,
) -> dict[str, Any]:
    rules = evaluate(
        {"observations": observations, "medications": medications, "answers": answers},
        today=today,
    )

    latest_by_test: dict[str, dict[str, Any]] = {}
    for obs in observations:
        t = obs["test"]
        prev = latest_by_test.get(t)
        if prev is None or ((obs.get("obs_date") or date.min) >= (prev.get("obs_date") or date.min)):
            latest_by_test[t] = obs

    intake_generics = {
        (m.get("generic_name") or m.get("name_as_written") or "").strip().lower()
        for m in medications
        if m.get("source") == "intake"
    }

    med_summary: list[dict[str, Any]] = []
    for m in medications:
        gen = (m.get("generic_name") or m.get("name_as_written") or "").strip().lower()
        if m.get("uncertain") and not m.get("verified_by_clinician"):
            status = "dose unclear"
        elif m.get("source") == "intake" or gen in intake_generics:
            status = "confirmed today"
        else:
            status = "not mentioned today"
        med_summary.append({**m, "intake_status": status})

    answered_ids = {a["question_id"] for a in answers if a.get("confirmed")}
    questions = load_questions()
    unanswered = [q["id"] for q in questions if q["id"] not in answered_ids]

    return {
        "disclaimer": "Documentation aid only. Not a diagnosis or treatment advice.",
        "patient": patient,
        "latest_results": list(latest_by_test.values()),
        "medications": med_summary,
        "rules": [r.__dict__ for r in rules],
        "answers": answers,
        "unanswered_questions": unanswered,
        "doctor_note": doctor_note,
    }
