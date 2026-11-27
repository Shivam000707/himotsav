"""Kiosk -> upload -> doctor flow through the HTTP API, with NVIDIA responses from fixtures."""
from __future__ import annotations

import io
import json
from pathlib import Path

from PIL import Image

from services import parse, structure

FIXTURES = Path(__file__).resolve().parent / "fixtures"
P3_IMAGE = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "images" / "p3.png"


def _fake_nvidia(monkeypatch):
    parse_raw = json.loads((FIXTURES / "p3_parse_fixture.json").read_text(encoding="utf-8"))
    struct_raw = json.loads((FIXTURES / "p3_structure_fixture.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(parse, "chat_completion", lambda payload, **kw: parse_raw)
    monkeypatch.setattr(structure, "chat_completion", lambda payload, **kw: struct_raw)


def _new_patient(client, language="en"):
    res = client.post("/api/patients", json={"display_name": "Test patient", "age": 50, "language": language})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def test_full_flow(client, monkeypatch):
    _fake_nvidia(monkeypatch)
    pid = _new_patient(client)

    qs = client.get("/api/intake/questions?lang=hi").json()
    assert qs[0]["text"].startswith("नमस्ते")
    assert [q["id"] for q in qs][:2] == ["diabetes_years", "current_meds"]

    answers = [
        ("diabetes_years", "10", None),
        ("current_meds", [{"name": "Glycomet", "frequency": "1-0-1"}, {"name": "Januvia", "frequency": "1-0-0"}], None),
        ("missed_doses", "never", None),
        ("shaky_sweaty", "no", "शाम को पसीना आता है"),  # tapped "no" but the words mention sweating
        ("urgent_symptoms", ["none"], None),
        ("feet", ["none"], None),
        ("eyes", "fine", None),
        ("anything_else", "", None),
    ]
    for qid, value, raw in answers:
        r = client.post(f"/api/patients/{pid}/answers", json={"question_id": qid, "value": value, "raw_text": raw, "confirmed": True})
        assert r.status_code == 200, r.text

    up = client.post(
        f"/api/patients/{pid}/documents",
        files={"file": ("report.png", P3_IMAGE.read_bytes(), "image/png")},
    )
    assert up.status_code == 200, up.text
    body = up.json()
    assert body["document"]["status"] == "done"
    assert body["document"]["kind"] == "lab"
    assert body["document"]["source_org"] == "Valley Diagnostics"
    assert body["document"]["doc_date"] == "2023-09-09"
    assert len(body["observations"]) == 2

    summary = client.get(f"/api/patients/{pid}/summary").json()
    latest = {o["test"]: o for o in summary["latest_results"]}
    fbs = latest["fasting_glucose"]
    assert fbs["converted"] is True and fbs["value_std"] == 160 and fbs["value_raw"] == "8.9"
    assert fbs["bbox"] is not None and fbs["unverified"] is False
    assert fbs["block_text"] == "Fasting glucose 8.9 mmol/L"

    rules = {r["rule_id"]: r for r in client.get(f"/api/patients/{pid}/rules").json()}
    # The free-text words trigger the low-sugar rule even though "no" was tapped.
    assert rules["low_sugar_symptoms"]["status"] == "flag"
    assert rules["hba1c_recent"]["status"] == "missing"  # 2023 result, today is 2026-10-14
    # Both intake medicines appear on no prescription.
    assert rules["med_match"]["status"] == "check"
    assert "Januvia named by the patient but not found on any prescription" in rules["med_match"]["evidence_text"]

    # Doctor edits and verifies a value.
    hba1c_id = latest["hba1c"]["id"]
    r = client.patch(f"/api/observations/{hba1c_id}", json={"edited_value": "7.6 %", "verified_by_clinician": True})
    assert r.status_code == 200
    assert r.json()["edited_value"] == "7.6 %" and r.json()["verified_by_clinician"] is True

    r = client.put(f"/api/patients/{pid}/note", json={"text": "Discussed evening symptoms."})
    assert r.status_code == 200
    assert client.get(f"/api/patients/{pid}/summary").json()["doctor_note"] == "Discussed evening symptoms."

    # Changing the medicine answer replaces the intake medicines.
    client.post(f"/api/patients/{pid}/answers", json={"question_id": "current_meds", "value": [{"name": "dont_know"}], "confirmed": True})
    meds = client.get(f"/api/patients/{pid}/summary").json()["medications"]
    assert [m for m in meds if m["source"] == "intake"] == []


def test_failed_extraction_keeps_the_upload(client, monkeypatch):
    def boom(payload, **kw):
        raise RuntimeError("NVIDIA API 503: busy")

    monkeypatch.setattr(parse, "chat_completion", boom)
    pid = _new_patient(client)
    up = client.post(f"/api/patients/{pid}/documents", files={"file": ("report.png", P3_IMAGE.read_bytes(), "image/png")})
    assert up.status_code == 200
    body = up.json()
    assert body["document"]["status"] == "failed"
    assert "503" in body["document"]["error"]
    assert body["observations"] == [] and body["medications"] == []
    # The page image is still available for staff to look at.
    assert client.get(f"/api/documents/{body['document']['id']}/pages/1/image").status_code == 200


def test_upload_validation(client):
    pid = _new_patient(client)
    r = client.post(f"/api/patients/{pid}/documents", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 400
    r = client.post(f"/api/patients/{pid}/documents", files={"file": ("broken.png", b"not an image", "image/png")})
    assert r.status_code == 400
    r = client.post("/api/patients/9999/documents", files={"file": ("a.png", b"x", "image/png")})
    assert r.status_code == 404


def test_large_photo_is_downscaled(client, monkeypatch):
    _fake_nvidia(monkeypatch)
    pid = _new_patient(client)
    buf = io.BytesIO()
    Image.new("RGB", (4000, 3000), (255, 255, 255)).save(buf, format="JPEG")
    up = client.post(f"/api/patients/{pid}/documents", files={"file": ("photo.jpg", buf.getvalue(), "image/jpeg")})
    assert up.status_code == 200
    doc_id = up.json()["document"]["id"]
    img = Image.open(io.BytesIO(client.get(f"/api/documents/{doc_id}/pages/1/image").content))
    assert max(img.size) == 2200


def test_validation_errors(client):
    assert client.post("/api/patients", json={"display_name": "", "age": 50}).status_code == 422
    assert client.post("/api/patients", json={"display_name": "A", "age": 500}).status_code == 422
    pid = _new_patient(client)
    r = client.post(f"/api/patients/{pid}/answers", json={"question_id": "nope", "value": 1, "confirmed": True})
    assert r.status_code == 400


def test_health(client):
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert body["nvidia_key_present"] is False
    assert body["asr_configured"] is False
    assert body["today"] == "2026-10-14"
