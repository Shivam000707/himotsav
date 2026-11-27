"""ASR route for voice intake audio upload."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from services.asr import transcribe_audio_pcm

router = APIRouter(prefix="/api", tags=["asr"])

MAX_AUDIO_BYTES = 5 * 1024 * 1024  # about 2.5 minutes of 16 kHz mono audio


# Plain `def` so the blocking gRPC call runs in a worker thread.
@router.post("/asr")
def process_asr(
    file: UploadFile = File(...),
    lang: Optional[str] = Query(default=None, max_length=16),
) -> dict:
    content = file.file.read(MAX_AUDIO_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=400, detail="Recording is too long")
    text, err = transcribe_audio_pcm(content, lang=lang)
    return {"text": text, "fallback_needed": bool(err), "note": err}
