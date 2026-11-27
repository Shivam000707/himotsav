"""ASR route for voice intake audio upload."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from services.asr import transcribe_audio_pcm

router = APIRouter(prefix="/api", tags=["asr"])


@router.post("/asr")
async def process_asr(
    file: UploadFile = File(...),
    lang: str = Query(default="hi-IN"),
) -> dict:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty audio file")
    text, err = transcribe_audio_pcm(content, lang=lang)
    return {"text": text, "fallback_needed": bool(err), "note": err}
