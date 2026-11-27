# MediKiosk-DM: Project Overview

Oct 14, 2026 · @Shivam

MediKiosk-DM is an AI intake assistant that prepares a diabetes patient's history before the doctor sees them, so a rushed follow-up visit is spent on treatment, not paperwork.

## The problem

Type 2 diabetes patients in India see doctors again and again, often at different clinics, and their records never travel with them.

Take Ramesh ji, 58, diabetic for 10 years. He has seen 3 doctors and used 3 labs. He arrives with a bag of loose prescriptions and reports in different formats. The doctor has about 5 minutes and needs to know four things: his current medicines, whether he skips doses, whether his blood sugar is improving or worsening, and whether his kidneys are affected. Ramesh ji cannot recall it all, and the papers are jumbled. The doctor either burns the visit digging through paper or guesses and misses something.

- **101 million** Indians live with diabetes (ICMR-INDIAB study), so this happens millions of times a day.
- In a study of chronic-disease outpatients in Kerala and Himachal Pradesh, **only 24%** of OPD documents recorded the diagnosis, medicines and follow-up plan.
- Only **55%** of those patients remembered the medication and follow-up instructions they were given.
- Without reliable medication records, a later doctor may restart treatment or adjust doses badly, which can harm the patient.

## The solution

Think of a smart assistant at the clinic entrance that does the patient's paperwork before the doctor says hello. It supports documentation and review only. It never diagnoses, never changes medicines and never recommends treatment, so the doctor makes every decision.

1. **Conversational intake.** It interviews the patient in Hindi (other languages later) while they wait: how long they have had diabetes, current medicines, missed doses, shaky or sweaty spells, complications, other medical history.
2. **Report intelligence.** The patient uploads photos of old reports. The system extracts dates, HbA1c (the 3-month average blood sugar), glucose results, kidney-function and lipid results, and medicines.
3. **Longitudinal timeline.** One clean chart shows how results and prescriptions changed across visits, instead of a stack of papers.
4. **Safety flags.** Rule-based alerts for symptoms that need urgent assessment, plus a list of missing information, for example no kidney test in over a year.
5. **Clinician-ready summary.** An editable one-page history in which every extracted value links back to the original report, with uncertainties and unanswered questions marked.

## How we differ from existing products

Report scanning and AI note-taking already exist in India, so we do not pitch those as new. Our angle is a patient-side, diabetes-specific intake that happens before the consultation.

| Product | What it does | What it does not do |
| --- | --- | --- |
| [Eka Care / EkaScribe](https://medtechspectrum.com/news/16/24807/eka-cares-ai-powered-ekascribe-transforms-clinical-documentation-for-doctors-across-india.html) | Lab and prescription parsing, plus an AI scribe that writes notes during the consultation | No pre-consultation patient intake found in our search |
| [HealthPlix SmartScan](https://indiamedtoday.com/healthplix-launches-smartscan/) | Scans lab reports into the doctor's EMR | Works on the doctor's side; no patient interview |
| [ABHA Scan & Share](https://mohfw.gov.in/press-info/7554) | QR-based OPD registration and queue token | Registration only, not a clinical history |
| **MediKiosk-DM** | Patient interview in Hindi, report extraction, diabetes timeline, source-linked summary | Does not diagnose or advise treatment |

This comparison comes from public web pages and press releases, not from testing those products.

## How it works

&#91;embedded content: system flow · 4 stages\]

The language model asks the questions and reads the reports. Every safety decision (urgent symptoms, missing tests) is made by fixed rules in plain code, so it is predictable and explainable.

Build order, most important first:

1. Report extraction, unit conversion (mmol/L and mg/dL) and the timeline. This is the core, so make it solid first.
2. Doctor dashboard with click-to-source on every value.
3. Rule-based safety flags and missing-data checks.
4. Hindi voice intake.
5. Accuracy and time-study runs, then slides.

Scope for the hackathon: Hindi and English only, and only HbA1c, glucose, creatinine/eGFR, urine albumin-creatinine ratio and lipid profile. ABDM integration stays on the roadmap slide.

## How we prove it works

Being a research hackathon, we back the demo with two small experiments on synthetic data. No real patient records are used, which avoids consent and privacy problems under India's DPDP Act.

| Experiment | Method | Result to report |
| --- | --- | --- |
| Extraction accuracy | Build 25 to 30 synthetic lab reports and prescriptions in different lab formats, including blurred and rotated phone photos. Hand-label the true values. | Field-level accuracy, plus an honest list of failures |
| Clinician time study | 3 to 5 doctors, residents or medical students review the same synthetic patient twice: once from a paper stack, once from our summary. | Minutes to review, and how many planted missing items each method catches |

Published work gives us a baseline to compare against. Text-based pathology reports reach about 88 to 92% accuracy with LLMs, while one OCR pipeline on scanned lab reports scored an F1 of 0.86 and was sensitive to scan quality. Our own numbers on scanned diabetes reports are what we must measure.

## Demo script and open questions

The 3-minute demo follows one persona, Ramesh ji, 58, who arrives with 4 messy reports from 3 labs.

1. He answers the intake questions in Hindi.
2. One report uses mmol/L; the system converts it and shows both.
3. He mentions shaky, sweaty episodes, which raises a low-blood-sugar flag.
4. The doctor's screen shows his HbA1c trend, a missing kidney test and clickable sources.
5. We close on the time-study result.

Open questions we still need answered:

- [ ] What is the theme or problem statement of the hackathon?
- [ ] What are the judging criteria?
- [ ] What is the deadline, and is the final round a demo, a presentation or a paper?
- [ ] How many people are on the team, and what tech stack do we know?
- [ ] Which doctors or students can take part in the time study?

## Sources

- [ICMR-INDIAB: 101 million with diabetes (Gulf News)](https://gulfnews.com/world/asia/india/india-study-estimates-11-of-population-or-101-million-is-diabetic-1.96302385)
- [Clinical handover for outpatients with chronic disease in India (PMC6281223)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6281223/)
- [Challenges in primary care for diabetes and hypertension (BMC HSR 2019)](https://bmchealthservres.biomedcentral.com/track/pdf/10.1186/s12913-019-3876-9)
- [Scanned lab-report extraction preprint (Research Square)](https://www.researchsquare.com/article/rs-11152842/v1)
- [Breast pathology report extraction with LLMs (alphaXiv)](https://www.alphaxiv.org/overview/2502.12183)
- [Sarvam speech-to-text for Indian languages](https://www.sarvam.ai/apis/speech-to-text)
- [ABHA Scan & Share (MoHFW)](https://mohfw.gov.in/press-info/7554)
- [EkaScribe](https://medtechspectrum.com/news/16/24807/eka-cares-ai-powered-ekascribe-transforms-clinical-documentation-for-doctors-across-india.html)
- [HealthPlix SmartScan](https://indiamedtoday.com/healthplix-launches-smartscan/)

Figures come from web search results, not full-text reads of every paper; Sarvam's accuracy numbers are vendor-reported.
