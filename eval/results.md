# Experiment 1: Extraction accuracy results

Run on 28 Nov 2026 09:55 with models: parse `nvidia/nemotron-3.5-super-vl-120b-a12b`, text `nvidia/nemotron-3.5-lightning-30b-a3b`, vision fallback `nvidia/nemotron-3.5-super-vl-120b-a12b`.

Data: 7 synthetic documents for one made-up patient (5 lab reports, 2 prescriptions), each as a clean image and a damaged copy (rotated, blurred, darkened, JPEG quality 55). This is a small synthetic set: it shows a direction, not a general accuracy figure.

| Field | Clean | Damaged | All |
|---|---|---|---|
| date | 7/7 (100.0%) | 7/7 (100.0%) | 14/14 (100.0%) |
| value | 11/11 (100.0%) | 11/11 (100.0%) | 22/22 (100.0%) |
| unit | 11/11 (100.0%) | 11/11 (100.0%) | 22/22 (100.0%) |
| med | 3/3 (100.0%) | 3/3 (100.0%) | 6/6 (100.0%) |
| **all fields** | 32/32 (100.0%) | 32/32 (100.0%) | 64/64 (100.0%) |

- Extracted values tied to a source box on the page: 28/28 (100.0%)
- Smudged Amaryl dose (should be marked uncertain, not guessed):
  - p5_clean: marked uncertain (strength read as '? mg')
  - p5_damaged: NOT marked uncertain (strength read as '1 mg')

## Images that failed
- None

## Misses
- None
