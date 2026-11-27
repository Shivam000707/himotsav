"""Deterministic normalisation for test names, units, dates, and medicines."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import yaml
from dateutil import parser as date_parser
from rapidfuzz import fuzz, process

RESOURCES_DIR = Path(__file__).resolve().parent.parent / "resources"


def _load_test_aliases() -> dict[str, list[str]]:
    path = RESOURCES_DIR / "test_aliases.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(k): [str(v) for v in (vals or [])] for k, vals in data.items()}


def _load_med_map() -> list[dict[str, str]]:
    path = RESOURCES_DIR / "med_map.csv"
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8") as f:
        lines = [line for line in f if not line.lstrip().startswith("#") and line.strip()]
    reader = csv.DictReader(lines)
    for row in reader:
        rows.append(
            {
                "brand": (row.get("brand") or "").strip(),
                "generic": (row.get("generic") or "").strip(),
                "notes": (row.get("notes") or "").strip(),
            }
        )
    return rows


TEST_ALIASES = _load_test_aliases()
MED_MAP = _load_med_map()


def _clean_label(text: str) -> str:
    text = text.lower().replace("haemoglobin", "hemoglobin").replace("glycosylated", "glycated")
    text = re.sub(r"[^a-z0-9%/ ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


ALIAS_TO_CANONICAL: dict[str, str] = {
    _clean_label(alias): canonical for canonical, aliases in TEST_ALIASES.items() for alias in aliases
}


def canonicalize_test(label: str) -> str:
    """Map a printed lab test label to a canonical test id.

    Tries the whole label, then the text outside and inside brackets ("HbA1c (Glycated
    Hemoglobin)"). Exact alias first, then a whole-string fuzzy ratio >= 90. A substring match
    is deliberately not used: "Glucose" alone must not become "fasting glucose".
    """
    if not label or not label.strip():
        return "other"
    candidates = [label]
    outside = re.sub(r"\(.*?\)|\[.*?\]", " ", label)
    if outside.strip() and outside != label:
        candidates.append(outside)
    candidates.extend(re.findall(r"\((.*?)\)", label))

    cleaned = [c for c in (_clean_label(x) for x in candidates) if c]
    for c in cleaned:
        if c in ALIAS_TO_CANONICAL:
            return ALIAS_TO_CANONICAL[c]
    for c in cleaned:
        match = process.extractOne(c, list(ALIAS_TO_CANONICAL.keys()), scorer=fuzz.ratio)
        if match and match[1] >= 90:
            return ALIAS_TO_CANONICAL[match[0]]
    return "other"


@dataclass
class UnitConversionResult:
    value_num: Optional[float]
    value_std: Optional[float]
    unit_std: Optional[str]
    converted: bool
    uncertain: bool
    note: Optional[str]


def _parse_float(raw: str) -> Optional[float]:
    m = re.search(r"[-+]?\d+(?:\.\d+)?", raw.replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def convert_unit(test: str, value_raw: str, unit_raw: Optional[str]) -> UnitConversionResult:
    """Convert lab value to standard unit. Keeps raw values intact."""
    val = _parse_float(value_raw)
    if val is None:
        return UnitConversionResult(None, None, unit_raw, False, True, "value not numeric")

    if not unit_raw or not unit_raw.strip():
        return UnitConversionResult(val, None, None, False, True, "unit not readable")

    # Normalise spelling: Greek mu and micro sign both become "u"; drop spaces.
    u_clean = unit_raw.strip().lower().replace("μ", "u").replace("µ", "u").replace(" ", "")

    if test in {"fasting_glucose", "postprandial_glucose", "random_glucose"}:
        if "mmol" in u_clean:
            std = round(val * 18.016)
            return UnitConversionResult(val, float(std), "mg/dL", True, False, None)
        if "mg/dl" in u_clean or "mg%" in u_clean:
            return UnitConversionResult(val, float(round(val)), "mg/dL", False, False, None)

    elif test == "hba1c":
        if "mmol/mol" in u_clean:
            std = round(0.09148 * val + 2.152, 1)
            return UnitConversionResult(val, std, "%", True, False, None)
        if "%" in u_clean or "percent" in u_clean:
            return UnitConversionResult(val, round(val, 1), "%", False, False, None)

    elif test == "creatinine":
        if "umol/l" in u_clean or "micromol/l" in u_clean:
            std = round(val / 88.4, 2)
            return UnitConversionResult(val, std, "mg/dL", True, False, None)
        if "mg/dl" in u_clean:
            return UnitConversionResult(val, round(val, 2), "mg/dL", False, False, None)

    elif test in {"total_cholesterol", "ldl", "hdl"}:
        if "mmol" in u_clean:
            std = round(val * 38.67)
            return UnitConversionResult(val, float(std), "mg/dL", True, False, None)
        if "mg/dl" in u_clean:
            return UnitConversionResult(val, float(round(val)), "mg/dL", False, False, None)

    elif test == "triglycerides":
        if "mmol" in u_clean:
            std = round(val * 88.57)
            return UnitConversionResult(val, float(std), "mg/dL", True, False, None)
        if "mg/dl" in u_clean:
            return UnitConversionResult(val, float(round(val)), "mg/dL", False, False, None)

    elif test == "uacr":
        if "mg/mmol" in u_clean:
            std = round(val * 8.84)
            return UnitConversionResult(val, float(std), "mg/g", True, False, None)
        if "mg/g" in u_clean or "mcg/mg" in u_clean:
            return UnitConversionResult(val, float(round(val)), "mg/g", False, False, None)

    elif test == "egfr":
        return UnitConversionResult(val, round(val, 1), unit_raw.strip(), False, False, None)

    return UnitConversionResult(val, None, unit_raw.strip(), False, True, "unit not readable")


def parse_indian_date(raw_date: Optional[str]) -> tuple[Optional[date], Optional[str]]:
    """Parse DD/MM/YYYY-first date; note ambiguity when day and month are both <= 12."""
    if not raw_date or not raw_date.strip():
        return None, None
    text = re.sub(r"^\s*(date|dated|report date|collected on)\s*[:\-]?\s*", "", raw_date.strip(), flags=re.IGNORECASE)
    # Require a day, a month and a year: dateutil would otherwise fill gaps with today's date.
    if len(re.findall(r"\d+", text)) < 2 or not re.search(r"\d{4}|\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2}", text):
        return None, "date not readable"
    try:
        if re.match(r"^\s*\d{4}[-/.]\d{1,2}[-/.]\d{1,2}", text):
            # Year first (ISO style, 2026-08-12): the month comes before the day.
            dt = date_parser.parse(text, yearfirst=True, dayfirst=False).date()
        else:
            dt = date_parser.parse(text, dayfirst=True).date()
    except (ValueError, TypeError, OverflowError):
        return None, "date not readable"

    note = None
    numeric_match = re.fullmatch(r"\s*(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\s*", text)
    if numeric_match:
        first, second = int(numeric_match.group(1)), int(numeric_match.group(2))
        if first <= 12 and second <= 12 and first != second:
            note = "date order assumed DD/MM"
    return dt, note


def map_brand_to_generic(name_as_written: str) -> Optional[str]:
    """Strip Tab./Cap. and strengths, then fuzzy match against med_map.csv (>= 88)."""
    cleaned = name_as_written.strip().lower()
    cleaned = re.sub(r"^(tab|tablet|cap|capsule|inj|injection|syp|syrup)\b\.?\s*", "", cleaned)
    cleaned = re.sub(r"\d+(?:\.\d+)?\s*(mg|mcg|g|ml|iu|units?)\b", " ", cleaned)
    cleaned = re.sub(r"[^a-z ]+", " ", cleaned)  # digits, slashes, dots, question marks
    cleaned = re.sub(r"\b(mg|mcg|g|ml|iu|units?|tab|tabs|od|bd|tds|sr|xr)\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return None

    brand_to_generic = {row["brand"].lower(): row["generic"] for row in MED_MAP if row["brand"]}
    generics = {row["generic"].lower(): row["generic"] for row in MED_MAP if row["generic"]}
    if cleaned in brand_to_generic:
        return brand_to_generic[cleaned]
    if cleaned in generics:  # already written as a generic name, e.g. "Metformin"
        return generics[cleaned]

    # Whole-string similarity only: "Amaryl M" (glimepiride + metformin) must not become
    # plain "Amaryl". An unmatched name is shown as written, which is the safe outcome.
    match = process.extractOne(cleaned, list(brand_to_generic.keys()), scorer=fuzz.ratio)
    if match and match[1] >= 88:
        return brand_to_generic[match[0]]
    return None
