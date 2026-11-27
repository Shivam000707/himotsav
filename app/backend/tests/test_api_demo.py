"""Demo seeding: scripted backup, cached mode without a cache, live mode without a key."""
from __future__ import annotations

EXPECTED_RULES = {
    "urgent_symptoms": "ok",
    "low_sugar_symptoms": "flag",
    "missed_doses": "note",
    "feet_eyes": "note",
    "hba1c_recent": "ok",
    "kidney_recent": "missing",
    "lipid_recent": "missing",
    "med_match": "check",
    "unclear_readings": "check",
}


def test_scripted_seed_reproduces_the_simulation(client):
    res = client.post("/api/demo/seed?mode=scripted")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["documents_failed"] == []
    pid = body["patient_id"]

    rules = {r["rule_id"]: r["status"] for r in client.get(f"/api/patients/{pid}/rules").json()}
    assert rules == EXPECTED_RULES

    summary = client.get(f"/api/patients/{pid}/summary").json()
    assert summary["disclaimer"] == "Documentation aid only. Not a diagnosis or treatment advice."
    assert summary["today"] == "2026-10-14"
    assert len(summary["documents"]) == 7
    assert all(d["source_mode"] == "scripted" and d["status"] == "done" for d in summary["documents"])

    latest = {o["test"]: o for o in summary["latest_results"]}
    assert latest["hba1c"]["value_std"] == 8.9 and latest["hba1c"]["obs_date"] == "2026-08-12"
    assert latest["fasting_glucose"]["value_std"] == 176
    assert latest["creatinine"]["value_std"] == 1.2
    assert latest["uacr"]["value_std"] == 24
    assert latest["ldl"]["value_std"] == 128
    assert all(o["bbox"] is not None for o in summary["latest_results"])

    timeline = client.get(f"/api/patients/{pid}/timeline").json()
    hba1c = [o["value_std"] for o in timeline["observations_by_test"]["hba1c"]]
    assert hba1c == [7.2, 7.6, 8.3, 8.9]
    fbs = timeline["observations_by_test"]["fasting_glucose"]
    assert [o["value_std"] for o in fbs] == [142, 160, 176]
    assert [o["converted"] for o in fbs] == [False, True, False]

    meds = summary["medications"]
    amaryl = next(m for m in meds if m["source"] == "rx" and m["generic_name"] == "glimepiride")
    assert amaryl["uncertain"] is True
    assert amaryl["strength"] == "? mg"
    assert amaryl["intake_status"] == "not mentioned today · dose unclear"
    metformin_rx = [m for m in meds if m["source"] == "rx" and m["generic_name"] == "metformin"]
    assert len(metformin_rx) == 2 and all(m["intake_status"] == "confirmed today" for m in metformin_rx)

    answers = {a["question_id"]: a["answer"] for a in summary["answers_display"]}
    assert answers["missed_doses"] == "1–2 times a week"
    assert answers["feet"] == "Tingling"
    assert summary["unanswered_questions"] == []

    # Rule evidence points at real rows.
    med_rule = next(r for r in client.get(f"/api/patients/{pid}/rules").json() if r["rule_id"] == "med_match")
    assert "Amaryl" in med_rule["evidence_text"]
    assert med_rule["evidence_refs"] == [f"med:{amaryl['id']}"]

    # The page image for each document is served.
    doc_id = summary["documents"][0]["id"]
    img = client.get(f"/api/documents/{doc_id}/pages/1/image")
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"


def test_cached_mode_without_cache_marks_documents_failed(client):
    res = client.post("/api/demo/seed?mode=cached")
    assert res.status_code == 200
    body = res.json()
    assert len(body["documents_failed"]) == 7
    assert "live mode" in body["documents_failed"][0]["error"]
    summary = client.get(f"/api/patients/{body['patient_id']}/summary").json()
    assert all(d["status"] == "failed" for d in summary["documents"])
    assert summary["latest_results"] == []


def test_live_mode_without_key_is_refused(client):
    res = client.post("/api/demo/seed?mode=live")
    assert res.status_code == 400
    assert "NVIDIA_API_KEY" in res.json()["detail"]


def test_bad_mode_is_rejected(client):
    assert client.post("/api/demo/seed?mode=fake").status_code == 422
