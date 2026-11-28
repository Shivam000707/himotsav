"""The second reading: it only marks values unsure, never changes them, and never breaks extraction."""
from PIL import Image

from services import verify
from services.normalize import split_value_and_unit
from services.parse import ParsedBlock


def _block(block_id="b0", text="x"):
    return ParsedBlock(block_id, text, "Text", 0.1, 0.1, 0.9, 0.15)


def _obs(value="50", block_id="b0", uncertain=False):
    return {"test": "random_glucose", "value_raw": value, "block_id": block_id, "uncertain": uncertain, "note": None}


def _med(strength="500", frequency="1-0-1", block_id="b0"):
    return {"name_as_written": "Glycomet", "strength": strength, "frequency": frequency, "block_id": block_id,
            "uncertain": False, "note": None}


def _reader(monkeypatch, reply):
    monkeypatch.setattr(verify, "read_line_again", lambda *a, **k: reply)


def test_agreement_leaves_everything_alone(monkeypatch, tmp_path):
    _reader(monkeypatch, "Imp: hypoglycemic (RBS- 50mg/dl)")
    obs = [_obs("50")]
    assert verify.cross_check_rows(tmp_path / "p.png", [_block()], obs, []) == 0
    assert obs[0]["uncertain"] is False and obs[0]["value_raw"] == "50"


def test_disagreeing_number_is_marked_unsure_with_both_readings(monkeypatch, tmp_path):
    _reader(monkeypatch, "Imp: hypoglycemic (RBS- 50mg/dl)")
    obs = [_obs("10")]
    assert verify.cross_check_rows(tmp_path / "p.png", [_block()], obs, []) == 1
    assert obs[0]["uncertain"] is True
    assert obs[0]["value_raw"] == "10"  # never overwritten
    assert "50mg/dl" in obs[0]["note"]


def test_dose_and_timing_disagreements(monkeypatch, tmp_path):
    _reader(monkeypatch, "Tab. Amaryl 2 mg 1-0-0")
    meds = [_med("1 mg", "1-0-0"), _med("2 mg", "1-0-1"), _med("2 mg", "1-0-0")]
    verify.cross_check_rows(tmp_path / "p.png", [_block()], [], meds)
    assert [m["uncertain"] for m in meds] == [True, True, False]
    assert "dose" in meds[0]["note"] and "timing" in meds[1]["note"]


def test_second_reader_unavailable_marks_nothing(monkeypatch, tmp_path):
    _reader(monkeypatch, None)
    obs = [_obs("10")]
    assert verify.cross_check_rows(tmp_path / "p.png", [_block()], obs, []) == 0
    assert obs[0]["uncertain"] is False


def test_rows_without_a_line_or_already_unsure_are_skipped(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(verify, "read_line_again", lambda *a, **k: calls.append(1) or "99")
    obs = [_obs("10", block_id=None), _obs("10", uncertain=True)]
    assert verify.cross_check_rows(tmp_path / "p.png", [_block()], obs, []) == 0
    assert obs[1]["note"] is None


def test_one_call_per_line_even_with_several_values(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(verify, "read_line_again", lambda *a, **k: calls.append(1) or "HbA1c 7.6 8.9")
    verify.cross_check_rows(tmp_path / "p.png", [_block()], [_obs("7.6"), _obs("8.9")], [])
    assert len(calls) == 1


def test_a_failing_reader_never_breaks_extraction(monkeypatch, tmp_path):
    img = tmp_path / "p.png"
    Image.new("RGB", (200, 200), "white").save(img)

    def boom(*a, **k):
        raise RuntimeError("NVIDIA API 429")

    monkeypatch.setattr(verify, "chat_completion", boom)
    assert verify.read_line_again(img, _block()) is None


def test_crop_is_enlarged_and_inside_the_page(tmp_path):
    img = tmp_path / "p.png"
    Image.new("RGB", (400, 800), "white").save(img)
    crop = verify.crop_line(img, ParsedBlock("b0", "x", "Text", 0.0, 0.0, 1.0, 0.1))
    assert crop.width > 400 and crop.height > 0


def test_phrase_values_are_reduced_to_the_number():
    assert split_value_and_unit("RBS-10mg/dl", "mg/dl") == ("10", "mg/dl", 'value was written as "RBS-10mg/dl"')
    assert split_value_and_unit("7.6", "%") == ("7.6", "%", None)
    assert split_value_and_unit("50 mg/dl", None)[:2] == ("50", "mg/dl")
    assert split_value_and_unit("N/A", None) == ("N/A", None, None)
