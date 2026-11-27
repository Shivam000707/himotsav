from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import db
from config import settings
from db import init_db
from routers import asr, demo, doctor, documents, intake, patients
from services.asr import asr_configured

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


log = logging.getLogger("medikiosk")


def _auto_seed() -> None:
    """On a fresh deployment the disk is empty, so load the demo patient before the first visitor."""
    mode = settings.auto_seed_demo
    if mode not in {"cached", "scripted"}:
        if mode:
            log.warning("AUTO_SEED_DEMO=%r ignored: use 'cached' or 'scripted'", mode)
        return
    from sqlmodel import Session, select

    from models import Patient
    from routers.demo import seed_demo_patient

    with Session(db.engine) as session:
        if session.exec(select(Patient)).first() is not None:
            return
        result = seed_demo_patient(session, mode)
        log.info("Auto-seeded demo patient %s (%s), %d of %d papers failed",
                 result["patient_id"], mode, len(result["documents_failed"]), result["documents_total"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _auto_seed()
    yield


app = FastAPI(title="MediKiosk-DM API", version="0.2.0", lifespan=lifespan)

# Locally the Vite dev server proxies /api, so there is no cross-origin call. When the frontend is
# hosted elsewhere (Vercel), its address goes in CORS_ORIGINS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["Content-Type"],
)

app.include_router(patients.router)
app.include_router(intake.router)
app.include_router(documents.router)
app.include_router(doctor.router)
app.include_router(demo.router)
app.include_router(asr.router)


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "nvidia_key_present": settings.nvidia_key_present,
        "asr_configured": asr_configured(),
        "asr_lang": settings.nvidia_asr_lang,
        "models": {
            "parse": settings.nvidia_parse_model,
            "text": settings.nvidia_text_model,
            "vision": settings.nvidia_vision_model,
        },
        "today": settings.today.isoformat(),
        "demo_today_set": bool(settings.demo_today_str),
        "public_demo": settings.public_demo,
    }
