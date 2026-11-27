from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db import init_db
from routers import asr, demo, doctor, documents, intake, patients


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="MediKiosk-DM API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patients.router)
app.include_router(intake.router)
app.include_router(documents.router)
app.include_router(doctor.router)
app.include_router(demo.router)
app.include_router(asr.router)


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {
        "ok": True,
        "nvidia_key_present": settings.nvidia_key_present,
    }
