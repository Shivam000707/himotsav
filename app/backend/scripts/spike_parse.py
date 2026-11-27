"""Phase 0 API spike: send one test image to Nemotron Parse and one prompt to the text LLM.

Saves raw responses to app/backend/tests/fixtures/ so offline tests and schema checks
can inspect the exact NVIDIA response shape.
"""
from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from config import settings  # noqa: E402

FIXTURES_DIR = BACKEND_DIR / "tests" / "fixtures"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)


def make_test_image_b64() -> str:
    img = Image.new("RGB", (800, 400), color=(255, 254, 250))
    draw = ImageDraw.Draw(img)
    draw.text((40, 40), "Valley Diagnostics - Lab Report", fill=(31, 41, 51))
    draw.text((40, 90), "Patient: Ramesh Kumar | Date: 09 Sep 2023", fill=(31, 41, 51))
    draw.text((40, 160), "HbA1c: 7.6 %", fill=(31, 41, 51))
    draw.text((40, 210), "Fasting glucose: 8.9 mmol/L", fill=(31, 41, 51))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def main() -> int:
    if not settings.nvidia_key_present:
        print("ERROR: Set NVIDIA_API_KEY in app/backend/.env before running the spike.")
        return 1

    headers = {
        "Authorization": f"Bearer {settings.nvidia_api_key}",
        "Content-Type": "application/json",
    }
    b64 = make_test_image_b64()
    print(f"Test image base64 size: {len(b64)} chars")

    parse_payload = {
        "model": settings.nvidia_parse_model,
        "messages": [
            {
                "role": "user",
                "content": f'<img src="data:image/jpeg;base64,{b64}"/>',
            }
        ],
        "tools": [
            {
                "type": "function",
                "function": {"name": "markdown_bbox"},
            }
        ],
        "tool_choice": {"type": "function", "function": {"name": "markdown_bbox"}},
        "max_tokens": 2048,
    }

    with httpx.Client(timeout=60.0) as client:
        r_parse = client.post(
            f"{settings.nvidia_base_url}/chat/completions",
            headers=headers,
            json=parse_payload,
        )
        print(f"Parse status: {r_parse.status_code}")
        parse_json = r_parse.json()
        (FIXTURES_DIR / "spike_parse_response.json").write_text(
            json.dumps(parse_json, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        llm_payload = {
            "model": settings.nvidia_text_model,
            "messages": [
                {"role": "system", "content": "Return ONLY valid JSON: {\"ok\": true}."},
                {"role": "user", "content": "Reply with JSON."},
            ],
            "temperature": 0,
            "max_tokens": 128,
        }
        r_llm = client.post(
            f"{settings.nvidia_base_url}/chat/completions",
            headers=headers,
            json=llm_payload,
        )
        print(f"Text LLM status: {r_llm.status_code}")
        llm_json = r_llm.json()
        (FIXTURES_DIR / "spike_llm_response.json").write_text(
            json.dumps(llm_json, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    print("Saved fixtures to", FIXTURES_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
