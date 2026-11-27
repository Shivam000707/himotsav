# 02 Solution and scope

## What MediKiosk-DM does

A self-service intake station in the clinic waiting area (the "kiosk"). For the hackathon the kiosk is a web page that runs on any tablet, phone or laptop. In a real clinic it could be a low-cost tablet on a stand or a QR code the patient scans.

| # | Feature | What it does |
|---|---|---|
| 1 | Conversational intake | Interviews the patient in Hindi or English from a fixed question script: diabetes duration, current medicines, missed doses, shaky or sweaty spells, complications, other medical history. The screen shows what it understood and the patient confirms or corrects each answer. |
| 2 | Report intelligence | The patient or a clinic assistant photographs old reports and prescriptions. The system extracts dates, HbA1c, glucose, kidney function (creatinine/eGFR, urine albumin-creatinine ratio), lipid results and medicines. |
| 3 | Longitudinal timeline | Shows how results and prescriptions changed across visits on one chart, with units normalised (mmol/L and mg/dL). |
| 4 | Safety flags | Rule-based alerts for reported symptoms that need urgent assessment, plus a list of missing or outdated information. |
| 5 | Clinician-ready summary | An editable one-page history. Every extracted value links to the exact area of the source report. Uncertain values and unanswered questions are marked. |

## What it must never do (non-goals)

- Diagnose diabetes or any complication.
- Suggest, change or stop a medicine or dose.
- Recommend treatment or give medical advice to the patient.
- Replace the doctor's judgement. The doctor can edit every field.
- Store real patient data during the hackathon.

## Hackathon scope (to 28 Oct)

| In scope | Out of scope (roadmap) |
|---|---|
| Hindi and English | Other Indian languages |
| Tests: HbA1c, fasting/post-meal glucose, creatinine/eGFR, urine albumin-creatinine ratio, lipid profile | Other tests and imaging |
| Synthetic reports and a synthetic patient | Real patient data and hospital deployment |
| Web kiosk and doctor dashboard | ABDM/ABHA integration, EMR integration |
| Rule-based flags with a small, clinician-reviewed rule set | A broad clinical rule library |

## Why this scope

The core value is turning scattered documents into a trustworthy, checkable timeline. Report extraction, unit conversion, the timeline and the source-linked dashboard are the parts to make solid first. Voice intake is the riskiest part (speech recognition mistakes), so it is built last and always confirmed on screen.
