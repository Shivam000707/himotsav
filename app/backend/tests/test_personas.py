"""The two extra demo patients show the tracker features: a medicine change, and a jump from a steady baseline."""
from datetime import date


def _by_name(client):
    return {p["display_name"]: p["id"] for p in client.get("/api/patients").json()}


def test_personas_are_created_once_and_labelled_as_backup_data(client):
    first = client.post("/api/demo/seed-personas").json()
    assert [p["display_name"] for p in first] == ["Mohan Lal", "Kavita Sharma"] and all(p["created"] for p in first)
    second = client.post("/api/demo/seed-personas").json()
    assert not any(p["created"] for p in second)
    assert len(client.get("/api/patients").json()) == 2
    summary = client.get(f"/api/patients/{first[0]['patient_id']}/summary").json()
    assert all(d["source_mode"] == "scripted" for d in summary["documents"])


def test_mohan_shows_a_medicine_change_and_a_rise_then_fall(client):
    pid = client.post("/api/demo/seed-personas").json()[0]["patient_id"]
    tl = client.get(f"/api/patients/{pid}/timeline").json()
    values = [o["value_std"] for o in tl["observations_by_test"]["hba1c"]]
    assert values == [7.4, 8.1, 8.9, 9.4, 8.2, 7.6, 7.2]
    events = {(e["medicine"], e["kind"], e["date"]) for e in tl["medicine_events"]}
    assert ("Metformin", "changed", "2025-10-18") in events
    assert ("Glimepiride", "first_seen", "2025-10-18") in events


def test_kavita_jump_is_flagged_only_after_the_doctor_sets_a_margin(client):
    pid = client.post("/api/demo/seed-personas").json()[1]["patient_id"]
    rules = client.get(f"/api/patients/{pid}/rules").json()
    assert not [r for r in rules if r["rule_id"].startswith("baseline_")]
    client.put(f"/api/patients/{pid}/plan/hba1c", json={"review_margin": 1.0})
    (flag,) = [r for r in client.get(f"/api/patients/{pid}/rules").json() if r["rule_id"].startswith("baseline_")]
    assert flag["status"] == "check" and "above this patient's own average" in flag["evidence_text"]
    client.put(f"/api/patients/{pid}/plan/hba1c", json={"review_margin": 2.0})
    assert not [r for r in client.get(f"/api/patients/{pid}/rules").json() if r["rule_id"].startswith("baseline_")]


def test_auto_seed_loads_ramesh_and_both_personas(engine, monkeypatch):
    import config
    import main
    from sqlmodel import Session, select

    from models import Patient

    monkeypatch.setattr(config.settings, "auto_seed_demo", "scripted")
    main._auto_seed()
    with Session(engine) as s:
        names = {p.display_name for p in s.exec(select(Patient)).all()}
    assert names == {"Ramesh Kumar", "Mohan Lal", "Kavita Sharma"}
    assert date(2026, 10, 14) == config.settings.today
