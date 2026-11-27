# 06 Roadmap and demo

## Key dates

| Date | Milestone | Status |
|---|---|---|
| 14 Oct 2026 | College screening presentation | Deck ready (see below) |
| 28 Oct 2026 | Final presentation | In progress |

## Proposed plan to 28 Oct

A suggested schedule, to be adjusted by the team after screening.

| Window | Focus | Done when |
|---|---|---|
| 15-17 Oct | Synthetic report set with ground-truth labels. Report extraction and unit/medicine normalisation. | Extraction runs on all synthetic reports and we have a first accuracy number |
| 18-20 Oct | Timeline store and doctor dashboard with click-to-source | Doctor can open a patient and verify any value against its source |
| 21-22 Oct | Rule engine: urgent-symptom flags and missing-data checks. Get the rule list reviewed by a doctor. | Flags fire on the planted cases |
| 23-24 Oct | Kiosk interview with speech-to-text and on-screen confirmation | Ramesh ji persona can complete the intake in Hindi |
| 25-26 Oct | Run the two experiments (accuracy, time study) | Results table filled in |
| 27 Oct | Final deck, demo rehearsal, backup recording | Demo runs end to end twice without failure |
| 28 Oct | Final presentation | |

## Demo script (3 minutes)

Persona: Ramesh ji, 58, arrives with 4 messy reports from 3 labs.

1. He answers the intake questions in Hindi on the kiosk, confirming each answer on screen.
2. He uploads his reports. One uses mmol/L, and the system converts it and shows both units.
3. He mentions shaky, sweaty episodes, which raises a low-blood-sugar flag for the doctor.
4. The doctor's screen shows his HbA1c trend over time, a missing kidney test, and his medicines.
5. The doctor clicks a value and sees the exact region of the original report it came from.
6. Close on the measured results from the two experiments.

Record a backup video of the demo in case of network or hardware problems.

## Deliverables so far

| Item | Where |
|---|---|
| **Official submission deck** (Himovation 2026 template, 4 slides) | `submission/MediKiosk-DM_Himovation2026_Idea.pptx` and `.pdf` |
| Earlier drafts built on the wrong (SIH) structure. Do not submit these. | https://claude.ai/artifact/BWQwDRRX3mknM448tjKVeT and https://claude.ai/artifact/T9nroDM6X3tDghDJYAVQs3 |
| Project overview document | Claude doc: https://claude.ai/code/artifact/40b1f2db-1f3a-491a-a7c9-a56feed434f1 |

The slide artifacts are private unless shared from their Share menu. The exported `MediKiosk-DM Project Overview.md` in the repo root is an older snapshot of the overview doc and contains outdated references. The docs in this folder replace it.

## Open items

- [ ] Fill in the **Team ID** on the title slide.
- [ ] Confirm the **theme** on the portal (suggested: MedTech / BioTech / HealthTech) and the category (Software).
- [ ] Find a doctor to review the rule list and to join the time study.
- [ ] Confirm the final-round format and judging criteria with the college coordinator.
- [ ] Decide the final name if "MediKiosk-DM" should change.
- [ ] Check the licence of each open model before claiming "fully open source".
