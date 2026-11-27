"""Speech-to-text integration via Web Speech API in frontend, with NVIDIA Riva gRPC client backend."""
from __future__ import annotations

import io
from typing import Optional

from config import settings


def transcribe_audio_pcm(pcm_bytes: bytes, lang: str = "hi-IN") -> tuple[str, Optional[str]]:
    """Transcribe 16 kHz mono 16-bit PCM WAV.

    Returns (text, error). If Riva is not configured or fails, returns empty string and error.
    """
    if not settings.nvidia_key_present or not settings.nvidia_asr_function_id:
        return "", "Riva ASR function id not configured; use browser Web Speech API fallback"

    try:
        import grpc
        import riva.client as rcli  # type: ignore

        auth = rcli.Auth(
            custom_headers=[
                ("authorization", f"Bearer {settings.nvidia_api_key}"),
                ("function-id", settings.nvidia_asr_function_id),
            ]
        )
        asr_service = rcli.ASRService(auth)
        config = rcli.RecognitionConfig(
            language_code=lang or settings.nvidia_asr_lang,
            max_alternatives=1,
            enable_automatic_punctuation=True,
        )
        response = asr_service.offline_recognize(pcm_bytes, config)
        if response.results and response.results[0].alternatives:
            return response.results[0].alternatives[0].transcript, None
        return "", None
    except Exception as exc:
        return "", str(exc)
