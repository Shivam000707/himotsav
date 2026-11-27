"""Behaviour of the public demo deployment: no live AI, no uploads, saved replies, auto-seeded patient."""
import json

from sqlmodel import Session, select

import config
import main
from models import Patient
from services import nvidia_client


def test_public_demo_blocks_live_seed_and_uploads(client, monkeypatch):
    monkeypatch.setattr(config.settings, "public_demo", True)
    assert client.get("/api/health").json()["public_demo"] is True

    live = client.post("/api/demo/seed?mode=live")
    assert live.status_code == 403
    assert "public demo" in live.json()["detail"]

    patient = client.post("/api/patients", json={"display_name": "T", "age": 50, "language": "en"}).json()
    upload = client.post(
        f"/api/patients/{patient['id']}/documents", files={"file": ("a.png", b"not an image", "image/png")}
    )
    assert upload.status_code == 403

    # The offline demo and the kiosk questions still work.
    assert client.post("/api/demo/seed?mode=scripted").status_code == 200


def test_health_says_not_public_by_default(client):
    assert client.get("/api/health").json()["public_demo"] is False


def test_cache_key_ignores_how_the_jpeg_was_encoded():
    def payload(url: str) -> dict:
        return {
            "model": "m",
            "messages": [{"role": "user", "content": [{"type": "text", "text": "read"}, {"type": "image_url", "image_url": {"url": url}}]}],
        }

    a = nvidia_client._cache_key(payload("data:image/jpeg;base64,AAAA"), "abc123")
    b = nvidia_client._cache_key(payload("data:image/jpeg;base64,BBBB"), "abc123")
    c = nvidia_client._cache_key(payload("data:image/jpeg;base64,AAAA"), "other")
    assert a == b  # same source page, different encoder output
    assert a != c  # a different page is a different key
    # Without an image key the old behaviour holds: the image bytes are part of the key.
    assert nvidia_client._cache_key(payload("x"), None) != nvidia_client._cache_key(payload("y"), None)


def test_shipped_demo_cache_is_used_offline(tmp_path, monkeypatch):
    shipped = tmp_path / "demo_cache"
    shipped.mkdir()
    monkeypatch.setattr(nvidia_client, "DEMO_CACHE_DIR", shipped)
    payload = {"model": "m", "messages": [{"role": "user", "content": "hello"}]}
    reply = {"choices": [{"message": {"content": "saved reply"}}]}
    (shipped / f"{nvidia_client._cache_key(payload, None)}.json").write_text(json.dumps(reply), encoding="utf-8")

    assert nvidia_client.chat_completion(payload, allow_network=False) == reply


def test_auto_seed_loads_the_demo_patient_once(engine, monkeypatch):
    monkeypatch.setattr(config.settings, "auto_seed_demo", "scripted")
    main._auto_seed()
    main._auto_seed()  # a second start must not add a second patient
    with Session(engine) as s:
        assert len(s.exec(select(Patient)).all()) == 1


def test_auto_seed_ignores_unknown_modes(engine, monkeypatch):
    monkeypatch.setattr(config.settings, "auto_seed_demo", "live")
    main._auto_seed()
    with Session(engine) as s:
        assert s.exec(select(Patient)).first() is None


def test_public_demo_seed_is_idempotent(client, monkeypatch):
    monkeypatch.setattr(config.settings, "public_demo", True)
    first = client.post("/api/demo/seed?mode=scripted").json()
    second = client.post("/api/demo/seed?mode=scripted").json()
    assert second["patient_id"] == first["patient_id"]
    assert len(client.get("/api/patients").json()) == 1
