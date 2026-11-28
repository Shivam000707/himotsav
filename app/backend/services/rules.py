"""Deterministic rule engine: plain Python only, no AI."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

import yaml

from services.trends import TEST_NAMES, baseline_shift, dated_points

RESOURCES_DIR = Path(__file__).resolve().parent.parent / "resources"


def _load_rules_config() -> dict[str, Any]:
    path = RESOURCES_DIR / "rules.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


RULES_CONFIG = _load_rules_config()

MISSED_DOSE_LABELS = {
    "never": "Never",
    "less_than_weekly": "Less than once a week",
    "1_2_weekly": "1-2 times a week",
    "3_plus_weekly": "3 or more times a week",
}


def _med_key(m: dict[str, Any]) -> str:
    return (m.get("generic_name") or m.get("name_as_written") or "").strip().lower()


@dataclass
class RuleResult:
    rule_id: str
    name: str
    question: str
    status: str  # ok | flag | missing | check | note
    evidence_text: str
    evidence_refs: list[str] = field(default_factory=list)


def _days_ago_text(d: date, today: date) -> str:
    days = (today - d).days
    if days < 30:
        return f"{days} days ago"
    months = round(days / 30.4)
    return f"{months} months ago"


def _parse_answer_val(ans: dict[str, Any]) -> Any:
    raw = ans.get("value_json")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


def _collect_free_texts(answers_by_q: dict[str, dict[str, Any]]) -> list[tuple[str, str]]:
    texts: list[tuple[str, str]] = []
    for qid, ans in answers_by_q.items():
        if ans.get("raw_text"):
            texts.append((qid, str(ans["raw_text"])))
        val = _parse_answer_val(ans)
        if isinstance(val, str) and qid == "anything_else":
            texts.append((qid, val))
        elif isinstance(val, dict) and val.get("details"):
            texts.append((qid, str(val["details"])))
    return texts


def _match_keywords(texts: list[tuple[str, str]], keywords: list[str]) -> Optional[tuple[str, str]]:
    for qid, txt in texts:
        low = txt.lower()
        for kw in keywords:
            if kw.lower() in low:
                return qid, txt
    return None


def evaluate(patient_data: dict[str, Any], today: date) -> list[RuleResult]:
    """Evaluate the 9 deterministic clinical-documentation rules."""
    thresholds = RULES_CONFIG.get("thresholds", {})
    hba1c_max_days = int(thresholds.get("hba1c_max_days", 90))
    kidney_max_days = int(thresholds.get("kidney_max_days", 365))
    lipid_max_days = int(thresholds.get("lipid_max_days", 365))
    rx_med_max_months = int(thresholds.get("rx_med_max_months", 24))

    # Intervals the doctor set for this patient replace the draft defaults above. Nothing is set by default.
    plan = {p["test"]: p for p in patient_data.get("plan", [])}

    def planned(tests: list[str], default: int) -> tuple[int, bool]:
        days = [plan[t]["interval_days"] for t in tests if t in plan and plan[t].get("interval_days")]
        return (min(days), True) if days else (default, False)

    hba1c_max_days, hba1c_set = planned(["hba1c"], hba1c_max_days)
    kidney_max_days, kidney_set = planned(["creatinine", "egfr", "uacr"], kidney_max_days)
    lipid_max_days, lipid_set = planned(["ldl", "total_cholesterol", "hdl", "triglycerides"], lipid_max_days)

    urgent_keywords = [str(k) for k in RULES_CONFIG.get("urgent_keywords", [])]
    low_sugar_keywords = [str(k) for k in RULES_CONFIG.get("low_sugar_keywords", [])]
    missed_flag_vals = set(RULES_CONFIG.get("missed_dose_flag_values", ["1_2_weekly", "3_plus_weekly"]))

    answers = patient_data.get("answers", [])
    answers_by_q = {a["question_id"]: a for a in answers if a.get("confirmed", True)}
    free_texts = _collect_free_texts(answers_by_q)

    observations = patient_data.get("observations", [])
    medications = patient_data.get("medications", [])

    results: list[RuleResult] = []

    # 1. urgent_symptoms
    urgent_ans = answers_by_q.get("urgent_symptoms")
    urgent_vals = _parse_answer_val(urgent_ans) if urgent_ans else []
    if isinstance(urgent_vals, dict):
        urgent_vals = urgent_vals.get("selected", [])
    urgent_selected = [v for v in (urgent_vals or []) if v != "none"]
    eyes_ans = answers_by_q.get("eyes")
    eyes_val = _parse_answer_val(eyes_ans) if eyes_ans else None
    if isinstance(eyes_val, dict):
        eyes_val = eyes_val.get("choice")
    urgent_kw_hit = _match_keywords(free_texts, urgent_keywords)

    if urgent_selected or eyes_val == "sudden_vision_loss" or urgent_kw_hit:
        ev = ", ".join(urgent_selected) if urgent_selected else (
            "Sudden vision loss reported" if eyes_val == "sudden_vision_loss" else f'"{urgent_kw_hit[1]}"'
        )
        results.append(RuleResult("urgent_symptoms", "Urgent symptoms", "Chest pain, fainting or severe breathlessness reported?", "flag", ev, ["intake:urgent_symptoms"]))
    else:
        results.append(RuleResult("urgent_symptoms", "Urgent symptoms", "Chest pain, fainting or severe breathlessness reported?", "ok", "Not reported", []))

    # 2. low_sugar_symptoms
    shaky_ans = answers_by_q.get("shaky_sweaty")
    shaky_val = _parse_answer_val(shaky_ans) if shaky_ans else None
    shaky_choice = shaky_val.get("choice") if isinstance(shaky_val, dict) else shaky_val
    low_kw_hit = _match_keywords(free_texts, low_sugar_keywords)
    if str(shaky_choice).lower() == "yes" or low_kw_hit:
        ev = (shaky_ans.get("raw_text") if shaky_ans and shaky_ans.get("raw_text") else None) or (
            low_kw_hit[1] if low_kw_hit else "Patient reported shaky/sweaty spells"
        )
        results.append(RuleResult("low_sugar_symptoms", "Possible low-sugar symptoms", "Shaky or sweaty spells reported?", "flag", ev, ["intake:shaky_sweaty"]))
    else:
        results.append(RuleResult("low_sugar_symptoms", "Possible low-sugar symptoms", "Shaky or sweaty spells reported?", "ok", "Not reported", []))

    # 3. missed_doses
    missed_ans = answers_by_q.get("missed_doses")
    missed_val = _parse_answer_val(missed_ans) if missed_ans else None
    if isinstance(missed_val, dict):
        missed_val = missed_val.get("choice")
    if missed_val in missed_flag_vals:
        label = MISSED_DOSE_LABELS.get(str(missed_val), str(missed_val))
        raw = missed_ans.get("raw_text") if missed_ans else None
        ev = f"{label}: \"{raw}\"" if raw else label
        results.append(RuleResult("missed_doses", "Missed doses", "Forgets medicine at least once a week?", "note", ev, ["intake:missed_doses"]))
    else:
        results.append(RuleResult("missed_doses", "Missed doses", "Forgets medicine at least once a week?", "ok", "Never or less than weekly", []))

    # 4. feet_eyes
    feet_ans = answers_by_q.get("feet")
    feet_vals = _parse_answer_val(feet_ans) if feet_ans else []
    if isinstance(feet_vals, dict):
        feet_vals = feet_vals.get("selected", [])
    feet_selected = [v for v in (feet_vals or []) if v != "none"]
    if "non_healing_wound" in feet_selected or eyes_val == "sudden_vision_loss":
        ev = f"Feet: {', '.join(feet_selected) or 'none'}; Eyes: {eyes_val or 'fine'}"
        results.append(RuleResult("feet_eyes", "Feet and eyes", "Wound, numbness or tingling in feet? Blurry vision?", "flag", ev, ["intake:feet", "intake:eyes"]))
    elif feet_selected or eyes_val == "blurry":
        ev = f"Feet: {', '.join(feet_selected) or 'none'}; Eyes: {eyes_val or 'fine'}"
        results.append(RuleResult("feet_eyes", "Feet and eyes", "Wound, numbness or tingling in feet? Blurry vision?", "note", ev, ["intake:feet", "intake:eyes"]))
    else:
        results.append(RuleResult("feet_eyes", "Feet and eyes", "Wound, numbness or tingling in feet? Blurry vision?", "ok", "No foot or eye issues reported", []))

    # Helper for recency rules
    def latest_obs_for(test_names: set[str]) -> Optional[dict[str, Any]]:
        dated = [o for o in observations if o.get("test") in test_names and o.get("obs_date") is not None]
        if not dated:
            return None
        return max(dated, key=lambda o: o["obs_date"])

    # 5. hba1c_recent
    latest_hba1c = latest_obs_for({"hba1c"})
    if latest_hba1c and (today - latest_hba1c["obs_date"]).days <= hba1c_max_days:
        d = latest_hba1c["obs_date"]
        results.append(RuleResult("hba1c_recent", "HbA1c up to date", "HbA1c done in the last 3 months?", "ok", f"Last: {d.strftime('%d %b %Y')}, {_days_ago_text(d, today)}", [f"obs:{latest_hba1c['id']}"]))
    else:
        ev = f"Last: {latest_hba1c['obs_date'].strftime('%d %b %Y')}, {_days_ago_text(latest_hba1c['obs_date'], today)}" if latest_hba1c else "No HbA1c found"
        results.append(RuleResult("hba1c_recent", "HbA1c up to date", "HbA1c done in the last 3 months?", "missing", ev, [f"obs:{latest_hba1c['id']}"] if latest_hba1c else []))

    # 6. kidney_recent
    latest_kidney = latest_obs_for({"creatinine", "egfr", "uacr"})
    if latest_kidney and (today - latest_kidney["obs_date"]).days <= kidney_max_days:
        d = latest_kidney["obs_date"]
        results.append(RuleResult("kidney_recent", "Kidney test up to date", "Creatinine or urine albumin in the last 12 months?", "ok", f"Last: {d.strftime('%d %b %Y')}, {_days_ago_text(d, today)}", [f"obs:{latest_kidney['id']}"]))
    else:
        ev = f"Last: {latest_kidney['obs_date'].strftime('%d %b %Y')}, {_days_ago_text(latest_kidney['obs_date'], today)}" if latest_kidney else "No kidney test found"
        results.append(RuleResult("kidney_recent", "Kidney test up to date", "Creatinine or urine albumin in the last 12 months?", "missing", ev, [f"obs:{latest_kidney['id']}"] if latest_kidney else []))

    # 7. lipid_recent
    latest_lipid = latest_obs_for({"ldl", "total_cholesterol", "hdl", "triglycerides"})
    if latest_lipid and (today - latest_lipid["obs_date"]).days <= lipid_max_days:
        d = latest_lipid["obs_date"]
        results.append(RuleResult("lipid_recent", "Cholesterol test up to date", "Lipid profile in the last 12 months?", "ok", f"Last: {d.strftime('%d %b %Y')}, {_days_ago_text(d, today)}", [f"obs:{latest_lipid['id']}"]))
    else:
        ev = f"Last: {latest_lipid['obs_date'].strftime('%d %b %Y')}, {_days_ago_text(latest_lipid['obs_date'], today)}" if latest_lipid else "No lipid test found"
        results.append(RuleResult("lipid_recent", "Cholesterol test up to date", "Lipid profile in the last 12 months?", "missing", ev, [f"obs:{latest_lipid['id']}"] if latest_lipid else []))

    # 8. med_match: recent prescriptions vs medicines the patient named at intake, both ways.
    cutoff = today - timedelta(days=round(rx_med_max_months * 30.44))
    intake_meds = [m for m in medications if m.get("source") == "intake" and _med_key(m)]
    intake_keys = {_med_key(m) for m in intake_meds}
    all_rx_keys = {_med_key(m) for m in medications if m.get("source") == "rx" and _med_key(m)}

    # Latest prescription of each medicine within the window that the patient did not mention.
    missing_rx: dict[str, dict[str, Any]] = {}
    for m in medications:
        if m.get("source") != "rx":
            continue
        rx_d = m.get("rx_date")
        if rx_d is not None and rx_d < cutoff:
            continue
        key = _med_key(m)
        if not key or key in intake_keys:
            continue
        prev = missing_rx.get(key)
        if prev is None or (rx_d or date.min) > (prev.get("rx_date") or date.min):
            missing_rx[key] = m

    not_on_rx = [m for m in intake_meds if _med_key(m) not in all_rx_keys]

    if missing_rx or not_on_rx:
        parts = []
        for m in missing_rx.values():
            when = f" ({m['rx_date'].strftime('%b %Y')})" if m.get("rx_date") else ""
            parts.append(f"{m['name_as_written']}{when} not mentioned today")
        for m in not_on_rx:
            parts.append(f"{m['name_as_written']} named by the patient but not found on any prescription")
        refs = [f"med:{m['id']}" for m in missing_rx.values()] + [f"med:{m['id']}" for m in not_on_rx]
        results.append(RuleResult("med_match", "Medicine match", "Is every prescribed medicine mentioned by the patient?", "check", "; ".join(parts), refs))
    else:
        results.append(RuleResult("med_match", "Medicine match", "Is every prescribed medicine mentioned by the patient?", "ok", "All recent prescribed medicines matched", []))

    # 9. unclear_readings
    unclear_obs = [o for o in observations if (o.get("uncertain") or o.get("unverified")) and not o.get("verified_by_clinician")]
    unclear_meds = [m for m in medications if (m.get("uncertain") or m.get("unverified")) and not m.get("verified_by_clinician")]
    if unclear_obs or unclear_meds:
        parts = [f"{o['label_as_written']} ({o['value_raw']})" for o in unclear_obs] + [
            f"{m['name_as_written']} ({m.get('strength') or '?'})" for m in unclear_meds
        ]
        refs = [f"obs:{o['id']}" for o in unclear_obs] + [f"med:{m['id']}" for m in unclear_meds]
        results.append(RuleResult("unclear_readings", "Unclear readings", "Did the AI mark anything as unsure?", "check", "; ".join(parts), refs))
    else:
        results.append(RuleResult("unclear_readings", "Unclear readings", "Did the AI mark anything as unsure?", "ok", "All readings clear and source-linked", []))

    for rule_id, days, was_set in (
        ("hba1c_recent", hba1c_max_days, hba1c_set),
        ("kidney_recent", kidney_max_days, kidney_set),
        ("lipid_recent", lipid_max_days, lipid_set),
    ):
        if was_set:
            for r in results:
                if r.rule_id == rule_id:
                    r.question = f"Done within the interval the doctor set ({days} days)?"
                    r.evidence_text += f" (interval set by the doctor: {days} days)"

    # 10+. Change from the patient's own baseline: only for tests where the doctor set a review margin.
    for item in patient_data.get("plan", []):
        margin = item.get("review_margin")
        if not margin:
            continue
        shift = baseline_shift(dated_points(observations, item["test"]), margin)
        if shift:
            name = TEST_NAMES.get(item["test"], item["test"])
            direction = "above" if shift["difference"] > 0 else "below"
            results.append(
                RuleResult(
                    f"baseline_{item['test']}",
                    f"{name}: change from own baseline",
                    "Is the latest result far from this patient's own recent average?",
                    "check",
                    f"{name} is {abs(shift['difference']):g} {direction} this patient's own average of {shift['baseline']:g} "
                    f"over the 12 months before it ({shift['n_prior']} results). The doctor set the review margin at {margin:g}.",
                    [f"obs:{shift['observation_id']}"],
                )
            )

    return results
