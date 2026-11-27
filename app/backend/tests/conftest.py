"""Shared test setup: an isolated database, upload folder and cache for every test.

No test touches the network, the real medikiosk.db, data/uploads or data/cache.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine

import config
import db
from services import nvidia_client


@pytest.fixture()
def engine(tmp_path, monkeypatch):
    test_engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    db.init_db(test_engine)
    monkeypatch.setattr(db, "engine", test_engine)
    return test_engine


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path, monkeypatch):
    uploads = tmp_path / "uploads"
    cache = tmp_path / "cache"
    monkeypatch.setattr(config, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(nvidia_client, "CACHE_DIR", cache)
    # The saved demo replies shipped with the repo must not leak into tests that expect a cache miss.
    monkeypatch.setattr(nvidia_client, "DEMO_CACHE_DIR", tmp_path / "no_demo_cache")
    # Modules that imported UPLOADS_DIR by name.
    from routers import demo, documents

    monkeypatch.setattr(demo, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(documents, "UPLOADS_DIR", uploads)
    # Never call NVIDIA from tests, whatever is in app/backend/.env.
    monkeypatch.setattr(config.settings, "nvidia_api_key", "")
    monkeypatch.setattr(config.settings, "nvidia_asr_function_id", "")
    monkeypatch.setattr(config.settings, "demo_today_str", "2026-10-14")
    monkeypatch.setattr(config.settings, "public_demo", False)
    monkeypatch.setattr(config.settings, "auto_seed_demo", "")
    return uploads


@pytest.fixture()
def client(engine):
    import main

    def _get_session():
        with Session(engine) as s:
            yield s

    main.app.dependency_overrides[db.get_session] = _get_session
    # The app's startup calls init_db() on db.engine, which the engine fixture has pointed at the test database.
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()
