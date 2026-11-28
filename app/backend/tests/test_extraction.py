import json
from pathlib import Path

import pytest
from PIL import Image

from services import extraction, parse, structure
from services.extraction import verify_grounding
from services.parse import ParsedBlock

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _blocks(*texts: str) -> list[ParsedBlock]:
    return [ParsedBlock(f"b{i}", t, "Text", 0.1, 0.1 * i, 0.9, 0.1 * i + 0.05) for i, t in enumerate(texts)]


def test_extraction_p3_offline(monkeypatch, tmp_path):
    parse_raw = json.loads((FIXTURES_DIR / "p3_parse_fixture.json").read_text(encoding="utf-8"))
    struct_raw = json.loads((FIXTURES_DIR / "p3_structure_fixture.json").read_text(encoding="utf-8"))

    img_path = tmp_path / "p3.png"
    Image.new("RGB", (100, 100), (255, 255, 255)).save(img_path)

    calls = {"n": 0}

    def fake_chat_completion(payload, use_cache=True, allow_network=True, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return parse_raw
        return struct_raw

    monkeypatch.setattr(parse, "chat_completion", fake_chat_completion)
    monkeypatch.setattr(structure, "chat_completion", fake_chat_completion)

    blocks, structured, obs_rows, med_rows = extraction.extract_page_items(img_path)
    assert len(blocks) == 8
    assert structured.kind == "lab"
    assert len(obs_rows) == 2
    assert med_rows == []

    hba1c = next(o for o in obs_rows if o["test"] == "hba1c")
    assert hba1c["value_std"] == 7.6
    assert hba1c["block_id"] == "b5"
    assert hba1c["unverified"] is False

    fbs = next(o for o in obs_rows if o["test"] == "fasting_glucose")
    assert fbs["converted"] is True
    assert fbs["value_std"] == 160.0
    assert fbs["unit_std"] == "mg/dL"
    assert fbs["block_id"] == "b6"
    assert fbs["unverified"] is False


def test_grounding_accepts_the_claimed_block():
    blocks = _blocks("Valley Diagnostics", "HbA1c 7.6 %", "Fasting glucose 8.9 mmol/L")
    assert verify_grounding("7.6", "b1", blocks) == ("b1", False)


def test_grounding_relinks_a_wrong_block_id():
    blocks = _blocks("Valley Diagnostics", "HbA1c 7.6 %", "Fasting glucose 8.9 mmol/L")
    assert verify_grounding("8.9", "b1", blocks) == ("b2", False)


def test_grounding_rejects_invented_values():
    blocks = _blocks("Valley Diagnostics", "HbA1c 7.6 %")
    assert verify_grounding("9.1", "b1", blocks) == (None, True)


def test_grounding_numbers_must_match_whole_numbers():
    # "24" must not be found inside the year 2024 or inside 1.24.
    blocks = _blocks("Date: 21 Aug 2024", "Creatinine 1.24 mg/dL")
    assert verify_grounding("24", None, blocks) == (None, True)
    blocks = _blocks("Date: 21 Aug 2024", "Urine ACR 24 mg/g")
    assert verify_grounding("24", None, blocks) == ("b1", False)


def test_grounding_ambiguous_match_is_unverified():
    blocks = _blocks("Tab. Glycomet 500 1-0-1", "Tab. Glycomet 500 1-0-1 (repeat)")
    assert verify_grounding("Glycomet", None, blocks) == (None, True)
    # But the model's own block is accepted when it contains the value.
    assert verify_grounding("Glycomet", "b0", blocks) == ("b0", False)


def test_grounding_without_blocks_is_unverified():
    assert verify_grounding("7.6", None, []) == (None, True)
    assert verify_grounding("", "b0", _blocks("x")) == (None, True)


def test_vision_fallback_used_when_parse_finds_too_little(monkeypatch, tmp_path):
    img_path = tmp_path / "rx.png"
    Image.new("RGB", (100, 100), (255, 255, 255)).save(img_path)
    parse_raw = {"choices": [{"message": {"content": "[]"}}]}
    vision_raw = {
        "choices": [
            {
                "message": {
                    "content": '```json\n{"kind":"rx","source_org":"Dr. B","doc_date":"02/07/2024",'
                    '"observations":[],"medications":[{"name":"Tab. Amaryl","strength":"? mg","frequency":"1-0-0",'
                    '"block_id":"b9","uncertain":true,"note":"dose smudged"}]}\n```'
                }
            }
        ]
    }
    monkeypatch.setattr(parse, "chat_completion", lambda payload, **kw: parse_raw)
    monkeypatch.setattr(structure, "chat_completion", lambda payload, **kw: vision_raw)

    blocks, structured, obs_rows, med_rows = extraction.extract_page_items(img_path)
    assert blocks == []
    assert structured.kind == "rx"
    (med,) = med_rows
    assert med["generic_name"] == "glimepiride"
    assert med["block_id"] is None  # the invented "b9" is dropped
    assert med["unverified"] is True
    assert med["uncertain"] is True
    assert "date order assumed DD/MM" in med["note"]


def test_structuring_retries_once_then_fails(monkeypatch):
    calls = {"n": 0}

    def bad(payload, **kw):
        calls["n"] += 1
        return {"choices": [{"message": {"content": "Sorry, I cannot help."}}]}

    monkeypatch.setattr(structure, "chat_completion", bad)
    with pytest.raises(ValueError):
        structure.structure_from_blocks(_blocks("a", "b", "c"))
    assert calls["n"] == 2


def test_structuring_accepts_numbers_and_nulls(monkeypatch):
    content = (
        '{"kind":"Lab Report","source_org":null,"doc_date":"14 Feb 2023","doc_date_block":null,'
        '"observations":[{"label":"HbA1c","value":7.2,"unit":"%","block_id":"b0","uncertain":null,"note":null}],'
        '"medications":null}'
    )
    monkeypatch.setattr(structure, "chat_completion", lambda payload, **kw: {"choices": [{"message": {"content": content}}]})
    page = structure.structure_from_blocks(_blocks("HbA1c 7.2 %", "b", "c"))
    assert page.kind == "lab"
    assert page.observations[0].value == "7.2"
    assert page.observations[0].uncertain is False
    assert page.medications == []


def test_compress_image_fits_the_api_limit(tmp_path):
    from services.nvidia_client import compress_image_for_api

    noisy = Image.effect_noise((3000, 4000), 90).convert("RGB")
    path = tmp_path / "noisy.png"
    noisy.save(path)
    data, w, h = compress_image_for_api(path)
    assert len(data) <= 170_000
    assert max(w, h) <= 1600


def test_short_names_must_match_as_whole_words():
    # A 3-letter name must not be "found" inside longer words, or an invented medicine looks grounded.
    assert not extraction._block_contains("ORS", "FOR (Full name, address)")
    assert not extraction._block_contains("ORS", "Superscription")
    assert extraction._block_contains("ORS", "Sig: ORS 2 sachets")
    assert extraction._block_contains("Amphogel", "Amphogel good")


def test_rows_from_an_undated_page_are_marked_unsure(monkeypatch, tmp_path):
    img_path = tmp_path / "rx.png"
    Image.new("RGB", (100, 100), (255, 255, 255)).save(img_path)
    lines = [{"text": t, "bbox": [100, 100 + 60 * i, 800, 140 + 60 * i]} for i, t in enumerate(["Dr. B", "Date: smudged", "Tab. Glycomet 500 1-0-1"])]
    parse_raw = {"choices": [{"message": {"content": json.dumps(lines)}}]}
    struct = {"kind": "rx", "source_org": "Dr. B", "doc_date": "smudged", "medications": [
        {"name": "Glycomet", "strength": "500", "frequency": "1-0-1", "block_id": "b2", "uncertain": False}]}
    struct_raw = {"choices": [{"message": {"content": json.dumps(struct)}}]}
    monkeypatch.setattr(parse, "chat_completion", lambda payload, **kw: parse_raw)
    monkeypatch.setattr(structure, "chat_completion", lambda payload, **kw: struct_raw)

    _, _, _, med_rows = extraction.extract_page_items(img_path)
    (med,) = med_rows
    assert med["rx_date"] is None
    assert med["uncertain"] is True
    assert "date not readable" in med["note"]
