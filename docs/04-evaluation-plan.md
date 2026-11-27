# 04 Evaluation plan

This is a research hackathon, so the demo is backed by two small experiments on **synthetic data**. Neither has been run yet. All targets below are plans, not results.

## Experiment 1: extraction accuracy

**Question:** How accurately does the system read values, dates, units and medicines from phone photos of lab reports and prescriptions?

**Method**
1. Build 25 to 30 synthetic lab reports and prescriptions covering at least 3 different lab layouts, units in both mmol/L and mg/dL, and both English and Hindi text where practical.
2. Photograph or render them with realistic damage: blur, rotation, shadows, folds, low light.
3. Hand-label the true value of every target field (test name, value, unit, date, medicine, dose).
4. Run the extraction and compare field by field.

**Report**
- Field-level accuracy overall and per field type (value, unit, date, medicine).
- Accuracy on clean versus damaged images.
- A short, honest list of failure cases and what the source-link would have let a doctor catch.

**Baseline for context:** published work on typed breast-cancer pathology reports reports 87.9% (GPT-4o mini) and 91.6% (Llama 3.1 70B) accuracy on 83 test reports. That is a different task (typed text, not photos), so it is context only, not a target.

## Experiment 2: clinician time study

**Question:** Can a clinician review a patient's history faster and catch more missing items with our summary than with a paper stack?

**Method**
1. Prepare one synthetic patient history with a set of **planted gaps** (for example: no kidney test in 12+ months, a medicine mentioned but not prescribed, a unit mismatch).
2. Recruit 3 to 5 doctors, residents or final-year medical students. Ask for their consent to take part.
3. Each reviewer reviews the same patient twice: once from the paper stack, once from our summary. Alternate which comes first to reduce order effects, and use two comparable synthetic patients.
4. Record minutes to complete the review and how many planted gaps each reviewer identified.

**Report**
- Median review time for each condition.
- Planted gaps found out of the total, for each condition.
- Reviewer comments.

With so few reviewers this shows a direction, not statistical proof. Say so.

## Principles

- Synthetic data only. No real patient records.
- Report failures. A list of what went wrong is part of the result.
- No time-saving or accuracy claim in any slide until these numbers exist.

## Open items

- [ ] Find 3 to 5 doctors, residents or students for the time study.
- [ ] Decide the reviewer protocol and consent wording.
- [ ] Create the synthetic report set and the ground-truth labels file.
