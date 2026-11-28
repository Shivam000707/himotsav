from datetime import date

from services.normalize import (
    canonicalize_test,
    convert_unit,
    map_brand_to_generic,
    parse_indian_date,
)


def test_canonicalize_test():
    assert canonicalize_test("Glycated Hb") == "hba1c"
    assert canonicalize_test("FBS") == "fasting_glucose"
    assert canonicalize_test("Urine albumin / creatinine") == "uacr"
    assert canonicalize_test("Completely Unknown Assay") == "other"


def test_unit_conversions():
    g = convert_unit("fasting_glucose", "8.9", "mmol/L")
    assert g.converted is True
    assert g.value_std == 160.0
    assert g.unit_std == "mg/dL"

    h = convert_unit("hba1c", "60", "mmol/mol")
    assert h.converted is True
    assert h.value_std == 7.6
    assert h.unit_std == "%"

    c = convert_unit("creatinine", "106", "µmol/L")
    assert c.converted is True
    assert c.value_std == 1.2
    assert c.unit_std == "mg/dL"

    u = convert_unit("hba1c", "7.6", None)
    assert u.uncertain is True
    assert u.note == "unit not readable"


def test_parse_indian_date():
    d1, n1 = parse_indian_date("09/02/2023")
    assert d1 == date(2023, 2, 9)
    assert n1 == "date order assumed DD/MM"

    d2, n2 = parse_indian_date("18 Jun 2024")
    assert d2 == date(2024, 6, 18)
    assert n2 is None


def test_brand_to_generic():
    assert map_brand_to_generic("Tab. Glycomet 500") == "metformin"
    assert map_brand_to_generic("Tab. Amaryl 1 mg") == "glimepiride"
    assert map_brand_to_generic("Galvus Met 50/500") == "vildagliptin + metformin"


def test_canonicalize_brackets_and_no_substring_matches():
    assert canonicalize_test("HbA1c (Glycated Haemoglobin)") == "hba1c"
    assert canonicalize_test("Glycosylated Haemoglobin") == "hba1c"
    assert canonicalize_test("Serum Creatinine") == "creatinine"
    assert canonicalize_test("LDL Cholesterol") == "ldl"
    assert canonicalize_test("HDL Cholesterol") == "hdl"
    # Too vague to know which glucose test it is: keep as "other" rather than guess.
    assert canonicalize_test("Glucose") == "other"
    assert canonicalize_test("") == "other"


def test_more_unit_conversions():
    assert convert_unit("ldl", "3.3", "mmol/L").value_std == 128.0
    assert convert_unit("triglycerides", "1.7", "mmol/L").value_std == 151.0
    assert convert_unit("uacr", "2.7", "mg/mmol").value_std == 24.0
    assert convert_unit("creatinine", "97", "μmol/L").value_std == 1.1  # Greek mu
    assert convert_unit("creatinine", "1.1", "mg/dL").converted is False
    assert convert_unit("fasting_glucose", "142", "mg/dl").value_std == 142.0
    odd = convert_unit("fasting_glucose", "142", "furlongs")
    assert odd.uncertain is True and odd.value_std is None
    nonnum = convert_unit("hba1c", "seven", "%")
    assert nonnum.uncertain is True and nonnum.value_num is None


def test_dates_need_day_month_and_year():
    assert parse_indian_date("Date: 09 Sep 2023") == (date(2023, 9, 9), None)
    assert parse_indian_date("2026-08-12") == (date(2026, 8, 12), None)
    assert parse_indian_date("14/02/23")[0] == date(2023, 2, 14)
    assert parse_indian_date("Sep 2023") == (None, "date not readable")
    assert parse_indian_date("not a date") == (None, "date not readable")
    assert parse_indian_date(None) == (None, None)


def test_brand_mapping_is_strict():
    assert map_brand_to_generic("Glycomet GP 1") == "glimepiride + metformin"
    assert map_brand_to_generic("Tab. Amaryl ? mg") == "glimepiride"
    assert map_brand_to_generic("Glycomett 500") == "metformin"  # small spelling slip
    assert map_brand_to_generic("Metformin 500 mg") == "metformin"
    assert map_brand_to_generic("Amaryl M 1") is None  # different product: shown as written
    assert map_brand_to_generic("Tab. Unknownex") is None


def test_two_digit_year_after_a_month_name():
    from datetime import date

    from services.normalize import parse_indian_date

    assert parse_indian_date("23 Jan 99") == (date(1999, 1, 23), None)
    assert parse_indian_date("23 JAN 24") == (date(2024, 1, 23), None)
    assert parse_indian_date("Jan 99") == (None, "date not readable")  # still needs a day


def test_test_name_found_in_the_line_when_the_label_is_a_diagnosis():
    from services.normalize import canonicalize_test_in_text

    assert canonicalize_test_in_text("Imp: hypoglycemic (RBS-50mg/dl)") == "random_glucose"
    assert canonicalize_test_in_text("Forms and orders") == "other"  # no whole-word match inside longer words
    assert canonicalize_test_in_text("HbA1c 7.6 FBS 120") == "other"  # two tests on one line: never guess
