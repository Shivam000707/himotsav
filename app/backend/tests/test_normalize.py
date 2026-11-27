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
