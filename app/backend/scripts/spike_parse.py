"""Check the NVIDIA setup before anything else: run this first after adding your API key.

    cd app/backend
    .venv/Scripts/python scripts/spike_parse.py

It runs the real pipeline steps on synthetic report p3 (Valley Diagnostics: HbA1c 7.6 %, fasting glucose
8.9 mmol/L) with the models in .env, bypassing the cache, so every run makes real calls (about 3 requests).
If a model has been retired (HTTP 410) it lists the models your key can use right now.
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from config import REPO_ROOT, settings  # noqa: E402
from services.parse import parse_page_image  # noqa: E402
from services.structure import structure_from_blocks, structure_from_image_fallback  # noqa: E402

TEST_IMAGE = REPO_ROOT / "data" / "synthetic" / "images" / "p3.png"


def hint_for(message: str) -> None:
    if " 410" in message or "end of life" in message:
        print("    This model has been retired by NVIDIA. Models your key can use right now:")
        try:
            r = httpx.get(
                f"{settings.nvidia_base_url}/models",
                headers={"Authorization": f"Bearer {settings.nvidia_api_key}"},
                timeout=30,
            )
            for m in sorted(x["id"] for x in r.json().get("data", [])):
                print(f"      {m}")
            print("    Pick a vision-language model for NVIDIA_PARSE_MODEL and NVIDIA_VISION_MODEL, and a text model")
            print("    for NVIDIA_TEXT_MODEL, in app/backend/.env. Then run this script again.")
        except Exception as exc:  # noqa: BLE001
            print(f"    (could not list models: {exc})")
    elif " 401" in message or " 403" in message:
        print("    The key was refused. Check NVIDIA_API_KEY in app/backend/.env (it starts with nvapi-).")
    elif " 404" in message:
        print("    Model not found for this key. Check the model id in app/backend/.env.")
    elif " 429" in message:
        print("    Rate limited (free tier is about 40 requests a minute). Wait a minute and retry.")


def main() -> int:
    if not settings.nvidia_key_present:
        print("ERROR: set NVIDIA_API_KEY in app/backend/.env first (copy .env.example to .env).")
        return 1
    print(f"Test image: {TEST_IMAGE.name}")
    ok = True

    print(f"\n--- reading the page: model {settings.nvidia_parse_model}")
    blocks = []
    try:
        blocks = parse_page_image(TEST_IMAGE, use_cache=False)
        print(f"    {len(blocks)} lines with boxes:")
        for b in blocks:
            print(f"      {b.block_id} [{b.xmin:.2f},{b.ymin:.2f},{b.xmax:.2f},{b.ymax:.2f}] {b.text[:70]!r}")
        if not blocks:
            ok = False
            print("    WARNING: the model returned no usable lines. Check the model id and try again.")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"    FAILED: {exc}")
        hint_for(str(exc))

    if blocks:
        print(f"\n--- structuring: model {settings.nvidia_text_model}")
        try:
            page = structure_from_blocks(blocks, use_cache=False)
            print(f"    kind={page.kind} org={page.source_org!r} date={page.doc_date!r}")
            for o in page.observations:
                print(f"      {o.label}: {o.value} {o.unit} (line {o.block_id}, uncertain={o.uncertain})")
            if not page.observations:
                ok = False
                print("    WARNING: no test values found.")
        except Exception as exc:  # noqa: BLE001
            ok = False
            print(f"    FAILED: {exc}")
            hint_for(str(exc))

    print(f"\n--- fallback that reads the image directly: model {settings.nvidia_vision_model}")
    try:
        page = structure_from_image_fallback(TEST_IMAGE, use_cache=False)
        print(f"    found {len(page.observations)} test values")
    except Exception as exc:  # noqa: BLE001
        print(f"    FAILED: {exc}")
        hint_for(str(exc))
        print("    (This is only a fallback; the app still works without it.)")

    print("\nRESULT:", "Reading and structuring work. You can run the app." if ok else "Something needs fixing: see the messages above.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
