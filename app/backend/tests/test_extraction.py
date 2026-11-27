import json
from pathlib import Path

from services import extraction, parse, structure

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_extraction_p3_offline(monkeypatch, tmp_path):
    parse_raw = json.loads((FIXTURES_DIR / "p3_parse_fixture.json").read_text(encoding="utf-8"))
    struct_raw = json.loads((FIXTURES_DIR / "p3_structure_fixture.json").read_text(encoding="utf-8"))

    # Create a dummy image file
    from PIL import Image

    img_path = tmp_path / "p3.png"
    Image.new("RGB", (100, 100), (255, 255, 255)).save(img_path)

    calls = {"n": 0}

    def fake_chat_completion(payload, use_cache=True, allow_network=True):
        calls["n"] += 1
        if calls["n"] == 1:
            return parse_raw
        return struct_raw

    monkeypatch.setattr(parse, "chat_completion", fake_chat_completion)
    monkeypatch.setattr(structure, "chat_completion", fake_chat_completion)

    blocks, structured, obs_rows, med_rows = extraction.extract_page_items(img_path)
    assert len(blocks) == 4
    assert structured.kind == "lab"
    assert len(obs_rows) == 2

    hba1c = next(o for o in obs_rows if o["test"] == "hba1c")
    assert hba1c["value_std"] == 7.6
    assert hba1c["block_id"] == "b2"
    assert hba1c["unverified"] is False

    fbs = next(o for o in obs_rows if o["test"] == "fasting_glucose")
    assert fbs["converted"] is True
    assert fbs["value_std"] == 160.0
    assert fbs["unit_std"] == "mg/dL"
    assert fbs["block_id"] == "b3"
    assert fbs["unverified"] is False
