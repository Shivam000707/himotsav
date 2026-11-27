import io
import wave

from services.asr import read_wav, transcribe_audio_pcm


def _wav(seconds: float = 0.5, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * int(seconds * rate))
    return buf.getvalue()


def test_read_wav():
    pcm, rate, channels = read_wav(_wav(0.5))
    assert rate == 16000 and channels == 1 and len(pcm) == 16000


def test_asr_not_configured_asks_for_fallback(client):
    text, err = transcribe_audio_pcm(_wav())
    assert text == "" and "not configured" in err
    res = client.post("/api/asr", files={"file": ("a.wav", _wav(), "audio/wav")})
    assert res.status_code == 200
    assert res.json()["fallback_needed"] is True


def test_asr_rejects_empty_upload(client):
    assert client.post("/api/asr", files={"file": ("a.wav", b"", "audio/wav")}).status_code == 400
