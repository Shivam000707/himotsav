import json
from pathlib import Path

from services.parse import parse_nemotron_response

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_parse_p3_fixture():
    raw = json.loads((FIXTURES_DIR / "p3_parse_fixture.json").read_text(encoding="utf-8"))
    blocks = parse_nemotron_response(raw, img_w=1240, img_h=1754)
    assert len(blocks) == 4
    assert blocks[0].block_id == "b0"
    assert blocks[2].text == "HbA1c 7.6 %"
    assert 0.0 <= blocks[2].xmin <= 1.0
    assert 0.0 <= blocks[3].ymax <= 1.0
