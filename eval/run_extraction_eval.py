"""Run Experiment 1: extraction accuracy across all 14 synthetic images (clean + damaged)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "app" / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from services.extraction import extract_page_items  # noqa: E402
from services.normalize import map_brand_to_generic, parse_indian_date  # noqa: E402


def main() -> int:
    labels_path = REPO_ROOT / "data" / "synthetic" / "labels.json"
    labels = json.loads(labels_path.read_text(encoding="utf-8"))

    total_fields = 0
    matched_fields = 0
    clean_total = 0
    clean_ok = 0
    damaged_total = 0
    damaged_ok = 0
    misses: list[str] = []
    smudged_flagged = False

    for item in labels:
        img_path = REPO_ROOT / item["image_path"]
        variant = item["variant"]
        _, structured, obs_rows, med_rows = extract_page_items(img_path, use_cache=True, allow_network=True)

        expected_date, _ = parse_indian_date(item["date"])
        got_date, _ = parse_indian_date(structured.doc_date)
        date_ok = expected_date == got_date
        total_fields += 1
        if date_ok:
            matched_fields += 1
        else:
            misses.append(f"{item['id']} date: expected {item['date']}, got {structured.doc_date}")

        if variant == "clean":
            clean_total += 1
            clean_ok += int(date_ok)
        else:
            damaged_total += 1
            damaged_ok += int(date_ok)

        for row in item["rows"]:
            if item["kind"] == "lab":
                total_fields += 2
                found = next((o for o in obs_rows if o["test"] == row.get("test")), None)
                val_ok = bool(found and found["value_raw"].strip() == str(row["value"]).strip())
                unit_ok = bool(found and (found["unit_raw"] or "").strip().lower() == row.get("unit", "").strip().lower())
                matched_fields += int(val_ok) + int(unit_ok)
                if not val_ok:
                    misses.append(f"{item['id']} {row['label']} value: expected {row['value']}, got {found['value_raw'] if found else None}")
                if not unit_ok:
                    misses.append(f"{item['id']} {row['label']} unit: expected {row.get('unit')}, got {found['unit_raw'] if found else None}")
                if variant == "clean":
                    clean_total += 2
                    clean_ok += int(val_ok) + int(unit_ok)
                else:
                    damaged_total += 2
                    damaged_ok += int(val_ok) + int(unit_ok)
            else:
                total_fields += 1
                expected_gen = map_brand_to_generic(row.get("med_name") or row["label"])
                found_m = next((m for m in med_rows if m.get("generic_name") == expected_gen), None)
                med_ok = bool(found_m and (found_m.get("frequency") or "").strip() == row.get("frequency", row["value"]).strip())
                matched_fields += int(med_ok)
                if row.get("smudge_strength") and found_m and found_m.get("uncertain"):
                    smudged_flagged = True
                if not med_ok:
                    misses.append(f"{item['id']} med {row['label']}: expected {expected_gen} {row.get('frequency', row['value'])}")
                if variant == "clean":
                    clean_total += 1
                    clean_ok += int(med_ok)
                else:
                    damaged_total += 1
                    damaged_ok += int(med_ok)

    overall_pct = (100.0 * matched_fields / total_fields) if total_fields else 0.0
    clean_pct = (100.0 * clean_ok / clean_total) if clean_total else 0.0
    damaged_pct = (100.0 * damaged_ok / damaged_total) if damaged_total else 0.0

    lines = [
        "# Experiment 1: Extraction Accuracy Results",
        "",
        f"- **Overall field accuracy:** {matched_fields}/{total_fields} ({overall_pct:.1f}%)",
        f"- **Clean images:** {clean_ok}/{clean_total} ({clean_pct:.1f}%)",
        f"- **Damaged images:** {damaged_ok}/{damaged_total} ({damaged_pct:.1f}%)",
        f"- **Smudged Amaryl dose flagged uncertain:** {'Yes' if smudged_flagged else 'No'}",
        "",
        "## Misses",
        *(["- None"] if not misses else [f"- {m}" for m in misses]),
    ]
    out_path = REPO_ROOT / "eval" / "results.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
