"""Trends, medicine events, baseline shifts, schedules and the doctor's monitoring plan."""
from datetime import date

from services import trends
from services.rules import evaluate


def obs(id, test, d, v):
    return {"id": id, "test": test, "obs_date": d, "value_std": v, "value_num": v, "uncertain": False,
            "unverified": False, "label_as_written": test, "value_raw": str(v)}


def med(id, name, d, strength="500 mg", freq="1-0-1", uncertain=False):
    return {"id": id, "source": "rx", "name_as_written": name, "generic_name": name.lower(), "rx_date": d,
            "strength": strength, "frequency": freq, "uncertain": uncertain}


HBA = [
    obs(1, "hba1c", date(2023, 2, 1), 7.2),
    obs(2, "hba1c", date(2023, 9, 1), 7.6),
    obs(3, "hba1c", date(2024, 6, 1), 8.3),
    obs(4, "hba1c", date(2026, 8, 12), 8.9),
]


def test_trend_stats_and_slope():
    s = trends.trend_stats(trends.dated_points(HBA, "hba1c"))
    assert s["n"] == 4 and s["change_since_previous"] == 0.6
    assert 0.4 < s["slope_per_year"] < 0.6  # about +0.5 a year over 3.5 years
    assert trends.trend_stats(trends.dated_points(HBA[:1], "hba1c"))["slope_per_year"] is None  # one result: no rate
    assert trends.trend_stats([])["n"] == 0


def test_medicine_events_follow_the_prescriptions():
    meds = [
        med(1, "Metformin", date(2023, 2, 20)),
        med(2, "Metformin", date(2024, 7, 2), "1000 mg"),
        med(3, "Glimepiride", date(2024, 7, 2), "1 mg", "1-0-0"),
        med(4, "Metformin", date(2025, 8, 1), "1000 mg"),  # same as before: no event
    ]
    kinds = [(e["medicine"], e["kind"], e["date"].isoformat()) for e in trends.medicine_events(meds)]
    assert ("Metformin", "first_seen", "2023-02-20") in kinds
    assert ("Metformin", "changed", "2024-07-02") in kinds
    assert ("Glimepiride", "first_seen", "2024-07-02") in kinds
    assert ("Glimepiride", "not_on_later", "2025-08-01") in kinds
    assert not any(k[0] == "Metformin" and k[2] == "2025-08-01" for k in kinds)


def test_unsure_doses_do_not_create_change_events():
    meds = [med(1, "Amaryl", date(2024, 1, 1), "1 mg"), med(2, "Amaryl", date(2024, 7, 1), "? mg", uncertain=True)]
    assert [e["kind"] for e in trends.medicine_events(meds)] == ["first_seen"]


def test_baseline_shift_needs_history_and_a_margin():
    pts = trends.dated_points(HBA, "hba1c")
    assert trends.baseline_shift(pts, None) is None
    assert trends.baseline_shift(pts, 1.0) is None  # only one result in the 12 months before the latest
    stable = [obs(i, "hba1c", date(2026, m, 1), v) for i, (m, v) in enumerate([(1, 7.0), (3, 7.2), (5, 7.1)], 1)]
    stable.append(obs(9, "hba1c", date(2026, 8, 1), 8.6))
    shift = trends.baseline_shift(trends.dated_points(stable, "hba1c"), 1.0)
    assert shift and shift["difference"] == 1.5 and shift["baseline"] == 7.1
    assert trends.baseline_shift(trends.dated_points(stable, "hba1c"), 2.0) is None  # inside the doctor's margin


def test_schedule_statuses():
    today = date(2026, 10, 14)
    plan = [
        {"test": "hba1c", "interval_days": 90},
        {"test": "creatinine", "interval_days": 365},
        {"test": "ldl", "interval_days": 365},
        {"test": "egfr", "interval_days": 365},
    ]
    o = [obs(1, "hba1c", date(2026, 8, 12), 8.9), obs(2, "creatinine", date(2025, 10, 20), 1.2), obs(3, "egfr", date(2024, 1, 1), 80)]
    rows = {r["key"]: r for r in trends.schedule_rows(o, plan, today)}
    assert rows["hba1c"]["status"] == "Completed"  # last 12 Aug, due 10 Nov: 27 days away
    assert rows["creatinine"]["status"] == "Due"  # due 20 Oct 2026, 6 days away
    assert rows["ldl"]["status"] == "No record"
    assert rows["egfr"]["status"] == "Overdue"
    nothing = trends.schedule_rows(o, [], today)
    assert [r["status"] for r in nothing] == ["Interval not set"] * 3


def test_doctor_intervals_replace_draft_defaults_in_the_rules():
    today = date(2026, 10, 14)
    data = {"observations": [obs(1, "hba1c", date(2026, 8, 12), 8.9)], "medications": [], "answers": []}
    base = {r.rule_id: r for r in evaluate(data, today)}
    assert base["hba1c_recent"].status == "ok"  # 63 days, draft default 90
    data["plan"] = [{"test": "hba1c", "interval_days": 30}]
    planned = {r.rule_id: r for r in evaluate(data, today)}
    assert planned["hba1c_recent"].status == "missing"
    assert "interval set by the doctor: 30 days" in planned["hba1c_recent"].evidence_text


def test_baseline_rule_only_appears_when_the_doctor_set_a_margin():
    today = date(2026, 10, 14)
    o = [obs(i, "hba1c", date(2026, m, 1), v) for i, (m, v) in enumerate([(1, 7.0), (3, 7.2), (5, 7.1), (8, 8.6)], 1)]
    data = {"observations": o, "medications": [], "answers": []}
    assert not [r for r in evaluate(data, today) if r.rule_id.startswith("baseline_")]
    data["plan"] = [{"test": "hba1c", "review_margin": 1.0}]
    (rule,) = [r for r in evaluate(data, today) if r.rule_id.startswith("baseline_")]
    assert rule.status == "check" and "1.5 above" in rule.evidence_text and "doctor set the review margin" in rule.evidence_text


def test_plan_api_roundtrip(client):
    pid = client.post("/api/demo/seed?mode=scripted").json()["patient_id"]
    body = {"target_low": 6.5, "target_high": 7.5, "review_margin": 1.0, "interval_days": 90}
    r = client.put(f"/api/patients/{pid}/plan/hba1c", json=body)
    assert r.status_code == 200 and r.json()["interval_days"] == 90
    summary = client.get(f"/api/patients/{pid}/summary").json()
    assert summary["plan"][0]["test"] == "hba1c"
    assert any(row["key"] == "hba1c" and row["interval_set_by_doctor"] for row in summary["schedule"])
    tl = client.get(f"/api/patients/{pid}/timeline").json()
    assert tl["trends"]["hba1c"]["n"] == 4 and tl["medicine_events"]
    assert client.put(f"/api/patients/{pid}/plan/hba1c", json={}).json()["removed"] is True
    assert client.get(f"/api/patients/{pid}/summary").json()["plan"] == []


def test_plan_api_rejects_bad_input(client):
    pid = client.post("/api/demo/seed?mode=scripted").json()["patient_id"]
    assert client.put(f"/api/patients/{pid}/plan/not_a_test", json={"interval_days": 90}).status_code == 400
    assert client.put(f"/api/patients/{pid}/plan/hba1c", json={"target_low": 8, "target_high": 7}).status_code == 422
    assert client.put(f"/api/patients/{pid}/plan/hba1c", json={"interval_days": 2}).status_code == 422
    assert client.put("/api/patients/9999/plan/hba1c", json={"interval_days": 90}).status_code == 404
