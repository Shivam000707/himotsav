"""Speech to text through NVIDIA's hosted ASR (Riva gRPC API on build.nvidia.com).

The browser records 16 kHz mono 16-bit WAV and posts it to /api/asr. If NVIDIA ASR is not
configured or fails, the route says so and the kiosk falls back to the browser's own speech
recognition, then to typing. The patient always confirms the text before it is saved.

Setup (free developer key): open the ASR model's page on build.nvidia.com (for Hindi, the
Parakeet 1.1B RNNT multilingual model), copy the function id shown in its "Get API" example
into NVIDIA_ASR_FUNCTION_ID, and set NVIDIA_ASR_LANG to the language code that page uses.
"""
from __future__ import annotations

import io
import logging
import wave
from typing import Optional

from config import settings

log = logging.getLogger("medikiosk.asr")

NVCF_GRPC_URI = "grpc.nvcf.nvidia.com:443"


def asr_configured() -> bool:
    return bool(settings.nvidia_key_present and settings.nvidia_asr_function_id)


def read_wav(audio: bytes) -> tuple[bytes, int, int]:
    """Return (pcm_frames, sample_rate, channels) from a 16-bit PCM WAV file. Raises ValueError."""
    try:
        with wave.open(io.BytesIO(audio), "rb") as wf:
            if wf.getsampwidth() != 2:
                raise ValueError("audio must be 16-bit PCM")
            return wf.readframes(wf.getnframes()), wf.getframerate(), wf.getnchannels()
    except wave.Error as exc:
        raise ValueError(f"not a valid WAV file: {exc}") from exc


def transcribe_audio_pcm(audio: bytes, lang: Optional[str] = None) -> tuple[str, Optional[str]]:
    """Transcribe a 16-bit PCM WAV. Returns (text, error); error is None on success."""
    if not asr_configured():
        return "", "NVIDIA ASR is not configured (set NVIDIA_API_KEY and NVIDIA_ASR_FUNCTION_ID)"

    try:
        pcm, sample_rate, channels = read_wav(audio)
    except ValueError as exc:
        return "", str(exc)
    if not pcm:
        return "", "the recording is empty"

    try:
        import riva.client as rcli  # nvidia-riva-client

        auth = rcli.Auth(
            uri=NVCF_GRPC_URI,
            use_ssl=True,
            metadata_args=[
                ["function-id", settings.nvidia_asr_function_id],
                ["authorization", f"Bearer {settings.nvidia_api_key}"],
            ],
        )
        asr_service = rcli.ASRService(auth)
        config = rcli.RecognitionConfig(
            encoding=rcli.AudioEncoding.LINEAR_PCM,
            sample_rate_hertz=sample_rate,
            audio_channel_count=channels,
            language_code=lang or settings.nvidia_asr_lang,
            max_alternatives=1,
            enable_automatic_punctuation=True,
        )
        response = asr_service.offline_recognize(pcm, config)
        text = " ".join(
            r.alternatives[0].transcript.strip() for r in response.results if r.alternatives
        ).strip()
        return text, None
    except Exception as exc:  # network, auth or model errors: let the kiosk fall back
        log.warning("NVIDIA ASR failed: %s", exc)
        return "", f"NVIDIA ASR failed: {exc}"
