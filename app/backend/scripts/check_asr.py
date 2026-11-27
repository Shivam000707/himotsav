"""Check the optional NVIDIA speech-to-text setup.

    cd app/backend
    .venv/Scripts/python scripts/check_asr.py              # sends 1 s of silence: checks key, function id, language
    .venv/Scripts/python scripts/check_asr.py my_voice.wav # transcribes a 16-bit PCM WAV you recorded

Silence should come back as an empty transcript with no error. An error means the function id,
the language code or the key is wrong; the kiosk then uses the browser's speech recognition.
"""
from __future__ import annotations

import io
import sys
import wave
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from config import settings  # noqa: E402
from services.asr import asr_configured, transcribe_audio_pcm  # noqa: E402


def silence_wav(seconds: float = 1.0, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * int(seconds * rate))
    return buf.getvalue()


def main() -> int:
    if not asr_configured():
        print("Not configured: set NVIDIA_API_KEY and NVIDIA_ASR_FUNCTION_ID in app/backend/.env.")
        return 1
    audio = Path(sys.argv[1]).read_bytes() if len(sys.argv) > 1 else silence_wav()
    print(f"Function id {settings.nvidia_asr_function_id}, language {settings.nvidia_asr_lang}")
    text, err = transcribe_audio_pcm(audio)
    if err:
        print(f"ERROR: {err}")
        return 1
    print(f"OK. Transcript: {text!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
