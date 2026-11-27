import json
from pathlib import Path

from services.parse import parse_page_response

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _reply(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def test_parse_p3_real_reply():
    """A reply recorded from the real service for the synthetic Valley Diagnostics report."""
    raw = json.loads((FIXTURES_DIR / "p3_parse_fixture.json").read_text(encoding="utf-8"))
    blocks = parse_page_response(raw)
    assert len(blocks) == 8
    assert [b.block_id for b in blocks][:2] == ["b0", "b1"]
    hba1c = next(b for b in blocks if b.text == "HbA1c 7.6 %")
    # Boxes are returned on a 0..1000 scale and stored as 0..1 fractions.
    assert 0.0 <= hba1c.xmin < hba1c.xmax <= 1.0
    assert 0.2 < hba1c.ymin < hba1c.ymax < 0.3


def test_parse_scales_boxes_and_tolerates_fences_and_odd_items():
    content = (
        "Here is the page:\n```json\n"
        + json.dumps(
            [
                {"text": "HbA1c 7.6 %", "bbox": [100, 200, 850, 220]},
                {"text": "no box"},
                {"text": "", "bbox": [0, 0, 10, 10]},
                {"text": "flipped", "bbox": [500, 300, 100, 250]},
                {"text": "empty box", "bbox": [10, 10, 10, 30]},
                {"text": "off the page", "bbox": [-20, 990, 1200, 1100]},
            ]
        )
        + "\n```"
    )
    blocks = parse_page_response(_reply(content))
    assert [b.text for b in blocks] == ["HbA1c 7.6 %", "flipped", "off the page"]
    first = blocks[0]
    assert (first.xmin, first.ymin, first.xmax, first.ymax) == (0.1, 0.2, 0.85, 0.22)
    flipped = blocks[1]
    assert (flipped.xmin, flipped.xmax, flipped.ymin, flipped.ymax) == (0.1, 0.5, 0.25, 0.3)
    last = blocks[2]
    assert (last.xmin, last.xmax, last.ymax) == (0.0, 1.0, 1.0)  # clamped to the page


def test_parse_handles_broken_replies():
    assert parse_page_response({}) == []
    assert parse_page_response(_reply("")) == []
    assert parse_page_response(_reply("plain text, no list")) == []
    assert parse_page_response(_reply("[{not json")) == []
    # A reasoning model that ran out of tokens leaves content empty.
    assert parse_page_response({"choices": [{"message": {"content": None, "reasoning_content": "thinking..."}}]}) == []
