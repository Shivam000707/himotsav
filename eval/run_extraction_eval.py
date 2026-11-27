"""Experiment 1: extraction accuracy on the 14 synthetic images (7 clean + 7 damaged).

Runs the real NVIDIA pipeline (Nemotron Parse -> LLM structuring -> grounding -> normalisation)
on every image in data/synthetic/labels.json and compares each field with the answer key.

    cd app/backend
    .venv/Scripts/python ../../eval/run_extraction_eval.py            # live (uses the cache when present)
    .venv/Scripts/python ../../eval/run_extraction_eval.py --offline  # cache only, no network

Writes eval/results.md. Fields scored:
- date   : document date (one per image)
- value  : test result exactly as printed, for each lab row
- unit   : unit exactly as printed (case-insensitive), for each lab row
- med    : medicine recognised (same generic) with the right frequency, for each prescription row
Also reports whether each value was tied to a source box, and whether the smudged dose was
marked uncertain instead of guessed.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "app" / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from config import settings  # noqa: E402
from services.extraction import extract_page_items  # noqa: E402
from services.normalize import map_brand_to_generic, parse_indian_date  # noqa: E402


def _norm(s: object) -> str:
    return str(s or "").strip().lower().replace(" ", "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="use only cached NVIDIA responses")
    ap.add_argument("--delay", type=float, default=2.0, help="seconds between images on cache misses (rate limit)")
    args = ap.parse_args()

    if not args.offline and not settings.nvidia_key_present:
        print("NVIDIA_API_KEY is not set in app/backend/.env. Set it, or run with --offline.")
        return 1

    labels = json.loads((REPO_ROOT / "data" / "synthetic" / "labels.json").read_text(encoding="utf-8"))

    # score[variant][field] = [correct, total]
    score: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    misses: list[str] = []
    grounded = [0, 0]  # values tied to a source box / values extracted
    smudge_results: list[str] = []
    errors: list[str] = []

    def mark(variant: str, field: str, ok: bool) -> None:
        score[variant][field][0] += int(ok)
        score[variant][field][1] += 1

    for item in labels:
        img_path = REPO_ROOT / item["image_path"]
        variant = item["variant"]
        started = time.monotonic()
        try:
            _, structured, obs_rows, med_rows = extract_page_items(
                img_path, use_cache=True, allow_network=not args.offline
            )
        except Exception as exc:  # count every field of a failed image as missed
            errors.append(f"{item['id']}: {exc}")
            mark(variant, "date", False)
            for row in item["rows"]:
                if item["kind"] == "lab":
                    mark(variant, "value", False)
                    mark(variant, "unit", False)
                else:
                    mark(variant, "med", False)
            print(f"{item['id']}: FAILED ({exc})")
            continue
        elapsed = time.monotonic() - started

        expected_date, _ = parse_indian_date(item["date"])
        got_date, _ = parse_indian_date(structured.doc_date)
        mark(variant, "date", expected_date == got_date)
        if expected_date != got_date:
            misses.append(f"{item['id']} date: expected {item['date']}, got {structured.doc_date!r}")

        for o in obs_rows:
            grounded[1] += 1
            grounded[0] += int(not o["unverified"])
        for m in med_rows:
            grounded[1] += 1
            grounded[0] += int(not m["unverified"])

        for row in item["rows"]:
            if item["kind"] == "lab":
                found = next((o for o in obs_rows if o["test"] == row.get("test")), None)
                val_ok = bool(found and _norm(found["value_raw"]) == _norm(row["value"]))
                unit_ok = bool(found and _norm(found["unit_raw"]) == _norm(row.get("unit")))
                mark(variant, "value", val_ok)
                mark(variant, "unit", unit_ok)
                if not val_ok:
                    misses.append(
                        f"{item['id']} {row['label']} value: expected {row['value']}, "
                        f"got {found['value_raw'] if found else 'nothing (test not found)'}"
                    )
                if not unit_ok:
                    misses.append(
                        f"{item['id']} {row['label']} unit: expected {row.get('unit')}, "
                        f"got {found['unit_raw'] if found else 'nothing (test not found)'}"
                    )
            else:
                expected_gen = map_brand_to_generic(row.get("med_name") or row["label"])
                found_m = next((m for m in med_rows if m.get("generic_name") == expected_gen), None)
                expected_freq = row.get("frequency", row["value"])
                med_ok = bool(found_m and _norm(found_m.get("frequency")) == _norm(expected_freq))
                mark(variant, "med", med_ok)
                if not med_ok:
                    got = (
                        f"{found_m['name_as_written']} {found_m.get('frequency')}" if found_m else "not found"
                    )
                    misses.append(f"{item['id']} medicine {row['label']}: expected {expected_gen} {expected_freq}, got {got}")
                if row.get("smudge_strength"):
                    if not found_m:
                        smudge_results.append(f"{item['id']}: medicine not found")
                    elif found_m.get("uncertain"):
                        smudge_results.append(f"{item['id']}: marked uncertain (strength read as {found_m.get('strength')!r})")
                    else:
                        smudge_results.append(
                            f"{item['id']}: NOT marked uncertain (strength read as {found_m.get('strength')!r})"
                        )
        print(f"{item['id']}: done in {elapsed:.1f}s")
        if elapsed > 1.0 and not args.offline:  # a real network call happened: respect the rate limit
            time.sleep(args.delay)

    def pct(c: int, t: int) -> str:
        return f"{c}/{t} ({100.0 * c / t:.1f}%)" if t else "n/a"

    fields = ["date", "value", "unit", "med"]
    lines = [
        "# Experiment 1: Extraction accuracy results",
        "",
        f"Run on {datetime.now().strftime('%d %b %Y %H:%M')} with models: parse `{settings.nvidia_parse_model}`, "
        f"text `{settings.nvidia_text_model}`, vision fallback `{settings.nvidia_vision_model}`.",
        "",
        "Data: 7 synthetic documents for one made-up patient (5 lab reports, 2 prescriptions), each as a clean image "
        "and a damaged copy (rotated, blurred, darkened, JPEG quality 55). This is a small synthetic set: "
        "it shows a direction, not a general accuracy figure.",
        "",
        "| Field | Clean | Damaged | All |",
        "|---|---|---|---|",
    ]
    tot_c = tot_t = 0
    for f in fields:
        c1, t1 = score["clean"][f]
        c2, t2 = score["damaged"][f]
        tot_c += c1 + c2
        tot_t += t1 + t2
        lines.append(f"| {f} | {pct(c1, t1)} | {pct(c2, t2)} | {pct(c1 + c2, t1 + t2)} |")
    clean_c = sum(score["clean"][f][0] for f in fields)
    clean_t = sum(score["clean"][f][1] for f in fields)
    dmg_c = sum(score["damaged"][f][0] for f in fields)
    dmg_t = sum(score["damaged"][f][1] for f in fields)
    lines.append(f"| **all fields** | {pct(clean_c, clean_t)} | {pct(dmg_c, dmg_t)} | {pct(tot_c, tot_t)} |")
    lines += [
        "",
        f"- Extracted values tied to a source box on the page: {pct(*grounded)}",
        "- Smudged Amaryl dose (should be marked uncertain, not guessed):",
        *[f"  - {s}" for s in (smudge_results or ["not evaluated"])],
        "",
        "## Images that failed",
        *([f"- {e}" for e in errors] or ["- None"]),
        "",
        "## Misses",
        *([f"- {m}" for m in misses] or ["- None"]),
    ]
    out_path = REPO_ROOT / "eval" / "results.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nOverall: {pct(tot_c, tot_t)}. Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
