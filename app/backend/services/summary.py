"""Deterministic doctor summary builder (no AI)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Optional

from services.rules import evaluate
from services.trends import schedule_rows

RESOURCES_DIR = Path(__file__).resolve().parent.parent / "resources"
DISCLAIMER = "Documentation aid only. Not a diagnosis or treatment advice."
TEST_ORDER = [
    "hba1c",
    "fasting_glucose",
    "postprandial_glucose",
    "random_glucose",
    "creatinine",
    "egfr",
    "uacr",
    "total_cholesterol",
    "ldl",
    "hdl",
    "triglycerides",
]


def load_questions() -> list[dict[str, Any]]:
    return json.loads((RESOURCES_DIR / "questions.json").read_text(encoding="utf-8"))


def _parse_value(value_json: Optional[str]) -> Any:
    if value_json is None:
        return None
    try:
        return json.loads(value_json)
    except (TypeError, json.JSONDecodeError):
        return value_json


def format_answer(question: Optional[dict[str, Any]], value: Any) -> str:
    """Turn a stored answer into plain English for the doctor, using the question's option labels."""
    labels = {o["value"]: o.get("label_en", o["value"]) for o in (question or {}).get("options") or []}

    def label(v: Any) -> str:
        return labels.get(v, str(v))

    if isinstance(value, dict):
        # Older clients stored {"choice": ..., "details": ...} or {"selected": [...]}.
        if "selected" in value:
            value = value["selected"]
        elif "choice" in value:
            value = value["choice"]
    if value is None or value == "" or value == []:
        return "No answer"
    qtype = (question or {}).get("type")
    if qtype == "meds_multi" and isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                name = str(item.get("name") or "")
                freq = item.get("frequency")
                parts.append(f"{label(name)}{f' ({freq})' if freq else ''}")
            else:
                parts.append(label(item))
        return ", ".join(p for p in parts if p) or "No answer"
    if isinstance(value, list):
        return ", ".join(label(v) for v in value)
    if qtype == "number" and question and question.get("unit_en"):
        return f"{value} {question['unit_en']}"
    return label(value)


def build_summary(
    patient: dict[str, Any],
    observations: list[dict[str, Any]],
    medications: list[dict[str, Any]],
    answers: list[dict[str, Any]],
    doctor_note: str,
    today: date,
    documents: Optional[list[dict[str, Any]]] = None,
    plan: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    plan = plan or []
    rules = evaluate(
        {"observations": observations, "medications": medications, "answers": answers, "plan": plan},
        today=today,
    )

    latest_by_test: dict[str, dict[str, Any]] = {}
    for obs in observations:
        # Unrecognised tests are kept apart by their printed label, not merged into one "other".
        t = obs["test"] if obs["test"] != "other" else f"other:{obs['label_as_written'].strip().lower()}"
        prev = latest_by_test.get(t)
        if prev is None or ((obs.get("obs_date") or date.min) >= (prev.get("obs_date") or date.min)):
            latest_by_test[t] = obs

    intake_keys = {
        (m.get("generic_name") or m.get("name_as_written") or "").strip().lower()
        for m in medications
        if m.get("source") == "intake"
    }

    med_summary: list[dict[str, Any]] = []
    for m in medications:
        key = (m.get("generic_name") or m.get("name_as_written") or "").strip().lower()
        if m.get("source") == "intake":
            status = "named by patient today"
        elif m.get("uncertain") and not m.get("verified_by_clinician"):
            status = "dose unclear" if key in intake_keys else "not mentioned today · dose unclear"
        elif key in intake_keys:
            status = "confirmed today"
        else:
            status = "not mentioned today"
        med_summary.append({**m, "intake_status": status})

    questions = load_questions()
    q_by_id = {q["id"]: q for q in questions}
    confirmed = [a for a in answers if a.get("confirmed")]
    answered_ids = {a["question_id"] for a in confirmed}
    unanswered = [q["id"] for q in questions if q["id"] not in answered_ids]

    answers_display = []
    for q in questions:  # keep the script's order
        a = next((x for x in confirmed if x["question_id"] == q["id"]), None)
        if not a:
            continue
        answers_display.append(
            {
                "question_id": q["id"],
                "topic": q.get("topic", q["id"]),
                "answer": format_answer(q, _parse_value(a.get("value_json"))),
                "patient_words": a.get("raw_text"),
            }
        )

    return {
        "disclaimer": DISCLAIMER,
        "today": today.isoformat(),
        "patient": patient,
        "latest_results": sorted(
            latest_by_test.values(),
            key=lambda o: (TEST_ORDER.index(o["test"]) if o["test"] in TEST_ORDER else len(TEST_ORDER), o["label_as_written"]),
        ),
        "medications": med_summary,
        "rules": [r.__dict__ for r in rules],
        "answers": answers,
        "answers_display": answers_display,
        "unanswered_questions": unanswered,
        "unanswered_topics": [q_by_id[qid].get("topic", qid) for qid in unanswered],
        "documents": documents or [],
        "doctor_note": doctor_note,
        "plan": plan,
        "schedule": schedule_rows(observations, plan, today),
    }
