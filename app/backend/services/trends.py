"""Per-patient trends, medicine events, baseline shifts and test schedules. Plain code, no AI.

Everything here describes what is in the records. Nothing is diagnosed or advised, and no number is chosen
by the software: targets, review margins and test intervals come from the doctor (see models.PlanItem).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

TEST_NAMES = {
    "hba1c": "HbA1c",
    "fasting_glucose": "Fasting glucose",
    "postprandial_glucose": "Post-meal glucose",
    "random_glucose": "Random glucose",
    "creatinine": "Creatinine",
    "egfr": "eGFR",
    "uacr": "Urine albumin / creatinine",
    "total_cholesterol": "Total cholesterol",
    "ldl": "LDL cholesterol",
    "hdl": "HDL cholesterol",
    "triglycerides": "Triglycerides",
}
PLAN_TESTS = list(TEST_NAMES)

# The three checks the rules make by default, with the tests each one looks at.
SCHEDULE_GROUPS = [
    ("hba1c", "HbA1c", ["hba1c"]),
    ("kidney", "Kidney tests", ["creatinine", "egfr", "uacr"]),
    ("lipids", "Cholesterol tests", ["ldl", "total_cholesterol", "hdl", "triglycerides"]),
]

DUE_SOON_DAYS = 14
BASELINE_WINDOW_DAYS = 365
MIN_BASELINE_POINTS = 2
MIN_SLOPE_SPAN_DAYS = 60


def value_of(obs: dict[str, Any]) -> Optional[float]:
    v = obs.get("value_std")
    if v is not None:
        return float(v)
    return float(obs["value_num"]) if obs.get("value_num") is not None else None


def dated_points(observations: list[dict[str, Any]], test: str) -> list[tuple[date, float, int]]:
    """(date, value, observation id) for one test, oldest first. Undated or non-numeric rows are left out."""
    pts = []
    for o in observations:
        v = value_of(o)
        if o.get("test") == test and o.get("obs_date") is not None and v is not None:
            pts.append((o["obs_date"], v, o["id"]))
    return sorted(pts, key=lambda p: (p[0], p[2]))


def trend_stats(points: list[tuple[date, float, int]]) -> dict[str, Any]:
    """Counts, the change since the previous result, and a straight-line rate of change per year."""
    n = len(points)
    out: dict[str, Any] = {
        "n": n,
        "first_date": None,
        "last_date": None,
        "change_since_previous": None,
        "slope_per_year": None,
        "span_days": 0,
    }
    if n == 0:
        return out
    out["first_date"], out["last_date"] = points[0][0], points[-1][0]
    out["span_days"] = (points[-1][0] - points[0][0]).days
    if n >= 2:
        out["change_since_previous"] = round(points[-1][1] - points[-2][1], 2)
    if n >= 2 and out["span_days"] >= MIN_SLOPE_SPAN_DAYS:
        xs = [(d - points[0][0]).days / 365.25 for d, _, _ in points]
        ys = [v for _, v, _ in points]
        mx, my = sum(xs) / n, sum(ys) / n
        denom = sum((x - mx) ** 2 for x in xs)
        if denom > 0:
            out["slope_per_year"] = round(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom, 2)
    return out


def _med_key(m: dict[str, Any]) -> str:
    return (m.get("generic_name") or m.get("name_as_written") or "").strip().lower()


def _med_label(m: dict[str, Any]) -> str:
    name = m.get("generic_name") or m.get("name_as_written") or "medicine"
    return name.strip().title()


def _dose_text(m: dict[str, Any]) -> str:
    return " ".join(str(x).strip().lower() for x in (m.get("strength"), m.get("frequency")) if x)


def medicine_events(medications: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What the dated prescriptions show, in order: first seen, dose or timing different from the previous
    prescription, or absent from a later prescription. This is a timeline of records and says nothing about
    why anything changed or what effect it had."""
    rx = [m for m in medications if m.get("source") == "rx" and m.get("rx_date") and _med_key(m)]
    if not rx:
        return []
    by_date: dict[date, list[dict[str, Any]]] = {}
    for m in rx:
        by_date.setdefault(m["rx_date"], []).append(m)
    dates = sorted(by_date)
    keys = sorted({_med_key(m) for m in rx})

    events: list[dict[str, Any]] = []
    for key in keys:
        previous: Optional[dict[str, Any]] = None
        for d in dates:
            here = next((m for m in by_date[d] if _med_key(m) == key), None)
            if here is not None:
                if previous is None:
                    events.append(
                        {
                            "date": d,
                            "medicine": _med_label(here),
                            "kind": "first_seen",
                            "detail": f"First prescription seen in the papers ({_dose_text(here) or 'dose not stated'})",
                            "medication_id": here["id"],
                        }
                    )
                elif _dose_text(here) != _dose_text(previous) and not here.get("uncertain") and not previous.get("uncertain"):
                    events.append(
                        {
                            "date": d,
                            "medicine": _med_label(here),
                            "kind": "changed",
                            "detail": (
                                "Dose or timing differs from the previous prescription: "
                                f"{_dose_text(previous) or 'not stated'}, then {_dose_text(here) or 'not stated'}"
                            ),
                            "medication_id": here["id"],
                        }
                    )
                previous = here
            elif previous is not None:
                events.append(
                    {
                        "date": d,
                        "medicine": _med_label(previous),
                        "kind": "not_on_later",
                        "detail": "Not on this later prescription",
                        "medication_id": previous["id"],
                    }
                )
                previous = None
    return sorted(events, key=lambda e: (e["date"], e["medicine"]))


def baseline_shift(points: list[tuple[date, float, int]], margin: Optional[float]) -> Optional[dict[str, Any]]:
    """Compare the latest value with the patient's own average over the 12 months before it.
    Returns None when there is not enough history or the shift is within the doctor's margin."""
    if not points or margin is None or margin <= 0:
        return None
    last_date, last_value, last_id = points[-1]
    window_start = last_date - timedelta(days=BASELINE_WINDOW_DAYS)
    prior = [(d, v) for d, v, _ in points[:-1] if window_start <= d < last_date]
    if len(prior) < MIN_BASELINE_POINTS:
        return None
    baseline = sum(v for _, v in prior) / len(prior)
    diff = last_value - baseline
    if abs(diff) <= margin:
        return None
    return {
        "baseline": round(baseline, 2),
        "difference": round(diff, 2),
        "n_prior": len(prior),
        "latest_value": last_value,
        "latest_date": last_date,
        "observation_id": last_id,
    }


def schedule_rows(observations: list[dict[str, Any]], plan: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    """One row for each test the doctor set an interval for, plus the standard groups that have none.
    Statuses: Completed (within the interval), Due (within 14 days of the due date), Overdue, No record,
    Interval not set."""
    plan_by_test = {p["test"]: p for p in plan}

    def last_date(tests: list[str]) -> Optional[date]:
        ds = [o["obs_date"] for o in observations if o.get("test") in tests and o.get("obs_date")]
        return max(ds) if ds else None

    def row(key: str, label: str, tests: list[str], interval: Optional[int]) -> dict[str, Any]:
        last = last_date(tests)
        due = last + timedelta(days=interval) if (last and interval) else None
        if interval is None:
            status = "Interval not set"
        elif last is None:
            status = "No record"
        elif today > due:
            status = "Overdue"
        elif (due - today).days <= DUE_SOON_DAYS:
            status = "Due"
        else:
            status = "Completed"
        return {
            "key": key,
            "label": label,
            "interval_days": interval,
            "interval_set_by_doctor": interval is not None,
            "last_date": last,
            "due_date": due,
            "status": status,
        }

    rows: list[dict[str, Any]] = []
    covered: set[str] = set()
    for test in PLAN_TESTS:
        item = plan_by_test.get(test)
        if item and item.get("interval_days"):
            rows.append(row(test, TEST_NAMES[test], [test], item["interval_days"]))
            covered.add(test)
    for key, label, tests in SCHEDULE_GROUPS:
        if not any(t in covered for t in tests):
            rows.append(row(key, label, tests, None))
    return rows
