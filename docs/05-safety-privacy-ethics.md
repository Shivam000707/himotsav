# 05 Safety, privacy and ethics

## Safety boundaries

- MediKiosk-DM is a **documentation and review aid**. It does not diagnose, change medicines or recommend treatment, and it says so wherever it shows output.
- The patient never receives medical advice from the system. If a flag is raised, the message to the patient is only that the doctor will be told.
- All safety flags come from fixed rules in plain code, listed in a reviewable file. The language model never decides whether something is urgent.
- Every extracted value shows its source and can be edited by the doctor. Uncertain values are marked as uncertain rather than guessed.
- The urgent-symptom list and the missing-data thresholds in [03 Architecture](03-architecture.md) are drafts. A doctor must review them before they are presented as clinically sound.

## Known risks and how we handle them

| Risk | Handling |
|---|---|
| Report photo read wrongly | Source-linking, doctor edits, confidence marking, measured accuracy in [04](04-evaluation-plan.md) |
| Hindi speech misheard | Fixed script, on-screen confirmation of each answer, option to type or tap |
| Unit mix-ups (mmol/L vs mg/dL) | Deterministic converter, both units displayed |
| Medicine brand mapped to the wrong generic | Mapping table reviewed by a clinician, original written name always shown |
| Doctor over-trusts the summary | Source link on every value, "uncertain" marks, unanswered questions listed |
| A real emergency while waiting | Urgent flags are shown to clinic staff, and the kiosk does not replace triage |
| Model invents information | Extraction restricted to values present in the image, with the source region stored. A value without a source region is not shown as fact. |

## Privacy

- **Hackathon:** synthetic data only. No real patient records are collected, stored or shared.
- **Real use (future):** health data is sensitive personal data under India's Digital Personal Data Protection Act, 2023. A real deployment would need informed consent in the patient's language, purpose limitation, minimal retention, access control and encryption, and a clear way to delete data. Alignment with ABDM consent rules would be reviewed then. This is a design direction, not legal advice.
- Time-study reviewers take part voluntarily and see only synthetic patients.

## Ethics notes

- Language access is a goal: Hindi first, more languages later. Speech models perform unevenly across accents and dialects, which is a fairness risk to test, not assume away.
- Patients with low literacy or no smartphone should still be served, for example through a clinic assistant who helps with the kiosk.
- We state clearly what is measured and what is not. No result is claimed before it exists.
