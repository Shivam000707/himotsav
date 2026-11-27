import json
from datetime import date

from services.rules import evaluate


def test_ramesh_rules_match_simulation():
    today = date(2026, 10, 14)
    patient_data = {
        "answers": [
            {"question_id": "diabetes_years", "value_json": json.dumps(10), "raw_text": None, "confirmed": True},
            {"question_id": "current_meds", "value_json": json.dumps([{"name": "Glycomet", "frequency": "1-0-1"}]), "raw_text": None, "confirmed": True},
            {"question_id": "missed_doses", "value_json": json.dumps("1_2_weekly"), "raw_text": "Night tablet, 2-3 times a week", "confirmed": True},
            {"question_id": "shaky_sweaty", "value_json": json.dumps({"choice": "yes"}), "raw_text": "2-3 times last month, in the evening", "confirmed": True},
            {"question_id": "urgent_symptoms", "value_json": json.dumps(["none"]), "raw_text": None, "confirmed": True},
            {"question_id": "feet", "value_json": json.dumps(["tingling"]), "raw_text": None, "confirmed": True},
            {"question_id": "eyes", "value_json": json.dumps("fine"), "raw_text": None, "confirmed": True},
        ],
        "observations": [
            {"id": 1, "test": "hba1c", "label_as_written": "HbA1c", "value_raw": "8.9", "obs_date": date(2026, 8, 12), "uncertain": False, "unverified": False, "verified_by_clinician": False},
            {"id": 2, "test": "creatinine", "label_as_written": "Creatinine", "value_raw": "1.2", "obs_date": date(2025, 8, 21), "uncertain": False, "unverified": False, "verified_by_clinician": False},
            {"id": 3, "test": "ldl", "label_as_written": "LDL cholesterol", "value_raw": "128", "obs_date": date(2024, 6, 18), "uncertain": False, "unverified": False, "verified_by_clinician": False},
        ],
        "medications": [
            {"id": 1, "source": "intake", "name_as_written": "Glycomet", "generic_name": "metformin", "rx_date": None, "uncertain": False, "unverified": False, "verified_by_clinician": False},
            {"id": 2, "source": "rx", "name_as_written": "Tab. Glycomet", "generic_name": "metformin", "rx_date": date(2024, 7, 2), "uncertain": False, "unverified": False, "verified_by_clinician": False},
            {"id": 3, "source": "rx", "name_as_written": "Tab. Amaryl", "generic_name": "glimepiride", "strength": "1 mg", "rx_date": date(2024, 7, 2), "uncertain": True, "unverified": False, "verified_by_clinician": False},
        ],
    }

    results = {r.rule_id: r for r in evaluate(patient_data, today=today)}
    assert results["urgent_symptoms"].status == "ok"
    assert results["low_sugar_symptoms"].status == "flag"
    assert results["missed_doses"].status == "note"
    assert results["feet_eyes"].status == "note"
    assert results["hba1c_recent"].status == "ok"
    assert results["kidney_recent"].status == "missing"
    assert results["lipid_recent"].status == "missing"
    assert results["med_match"].status == "check"
    assert results["unclear_readings"].status == "check"
