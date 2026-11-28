# 09 Complete guide for answering questions

Written 27 Nov 2026 for Team Mayhem. It covers what the project is, how it works, what is proven, what is not, and short answers to the questions evaluators are likely to ask. Everything here comes from the repo and the running app. Where something is unproven, it says so, because saying so is safer than being caught overclaiming.

Companion documents: [08 How it works, step by step](08-how-it-works-step-by-step.md) (every step of the software), [01 Problem and evidence](01-problem-and-evidence.md), [05 Safety, privacy and ethics](05-safety-privacy-ethics.md).

---

## 0. The ten things to remember

1. **What it is:** a pre-consultation intake and summary tool for Type 2 diabetes follow-up visits in Indian OPDs.
2. **The problem:** the doctor has a few minutes, and the patient arrives with loose papers from many labs and clinics, in different units, and cannot recall every medicine.
3. **The promise:** every number the doctor sees points back to the exact line on the paper it came from.
4. **The rule:** **the AI reads, plain code decides.** The AI never decides what is urgent.
5. **It never** diagnoses, never changes a medicine, never gives treatment advice.
6. **No OCR engine.** Pages are read by NVIDIA's free hosted vision-language models.
7. **Synthetic data only.** No real patient data has been used in the project.
8. **Measured:** 64 of 64 fields correct on 14 synthetic images. That is a small, clean, made-up set, so it shows direction only.
9. **Known weakness (say it first):** on real handwriting the AI misreads, so we added a second reading by a different model that flags disagreements. It cannot catch a mistake both models share.
10. **SDG 3** (target 3.4 non-communicable diseases, 3.8 quality of care). We do not claim proven outcomes.

---

## 1. Pitch versions

**30 seconds.** In an Indian diabetes clinic the doctor has a few minutes and the patient brings a bag of loose papers. MediKiosk-DM asks the patient a fixed set of questions in Hindi or English while they wait, and reads photos of their old reports and prescriptions. The doctor gets one page: what needs attention, how the numbers moved, which medicines, what the patient said. Every value opens the original paper with the exact line highlighted, so the doctor can check the AI in one click. It never diagnoses or advises treatment.

**2 minutes.** Add: the AI only reads. Unit conversion, medicine-name mapping, dates and every flag are plain, reviewable code. If the AI is unsure, the value is marked unsure and never guessed. A second AI model re-reads each value line and a mismatch is flagged. The doctor can correct any value and the original reading is kept. We tested on synthetic data: 64 of 64 fields correct on printed reports, and we are open that real handwriting is much harder.

**5 minutes.** Add the demo (section 4), the three patient trajectories, the monitoring plan the doctor sets, the safety design (section 7), the limits (section 13), and the roadmap.

---

## 2. The problem and the evidence

Type 2 diabetes does not go away, so patients return every few months for life and collect papers from many doctors and labs. At each visit the doctor must work out what the patient takes now, whether they miss doses, whether sugar is improving, and whether complications are developing, in a few minutes.

Numbers (from `docs/01`, with the caveats the team already wrote):

| Claim | Number | How to say it |
|---|---|---|
| People with diabetes in India | An estimated **101 million** (11.4%), ICMR-INDIAB, Lancet Diabetes & Endocrinology 2023 | "An estimated 101 million". It is a modelled estimate. The original paper was not opened by the team, only summaries. |
| Records are thin | **24%** of 509 documents patients received at outpatient clinics held diagnosis, medication, long-term care and follow-up information | Chronic disease outpatients, **Kerala and Himachal Pradesh only**, not diabetes only, not all of India |
| Patients forget | **55%** (283 of 513) recalled verbal follow-up and medication instructions | Same study and same caveat |

**Do not** claim any time saved. No time study has been run (see section 9).

The persona used everywhere is **Ramesh ji, 58**, diabetic for 10 years, three doctors, three labs, one lab in mmol/L and another in mg/dL. He is illustrative, not a real patient.

---

## 3. What the product does

### The five features (as designed in `docs/02`)
1. **Conversational intake**: 8 fixed questions in Hindi or English, each answer confirmed by the patient.
2. **Report intelligence**: photos of old reports and prescriptions are read for dates, HbA1c, glucose, kidney tests, lipids and medicines.
3. **Longitudinal timeline**: results over time, units normalised.
4. **Safety flags**: fixed rules for symptoms needing attention and for missing or outdated tests.
5. **Clinician-ready summary**: one page, every value source-linked, uncertain values marked.

### What is actually built and running
- **Kiosk** (`/kiosk`): language, name and age, 8 questions with confirm slips, voice (browser speech recognition), photo upload, done screen.
- **Doctor's desk** (`/doctor`, `/doctor/<id>`): needs-attention list, trends for every test, results table, medicines with status, papers, what the patient said, notes (autosave), print.
- **Source viewer:** click any highlighted value, see the zoomed crop and the full page with the line highlighted, then verify or correct.
- **Tracking over time:** trend charts with rate of change, medicine events on the timeline, a doctor-set monitoring plan (targets, review margin, repeat interval), a test schedule, and a "change from own baseline" check that only exists when the doctor sets a margin.
- **Three made-up demo patients** with different trajectories.
- **Public demo** deployable on Vercel (frontend) and Railway (backend), using saved AI replies and no API key.

### What is not built (say so before you are asked)
- Returning patients and repeated visits (each kiosk session creates a new patient).
- Blood pressure and cardiovascular history, eye or foot screening records, CGM data.
- A patient-facing progress view.
- ABHA/ABDM or EMR integration.
- A login, user accounts, or real-data privacy controls.
- NVIDIA speech-to-text (code exists, never tested against the real service; the browser fallback works).
- The clinician time study (see section 9).

---

## 4. The demo, step by step (about 3 minutes)

Start: backend on port 8000, frontend on http://localhost:5173. Check http://localhost:8000/api/health first.

1. **Home.** Read the headline: "Every number the doctor sees points back to the paper it came from."
2. **Doctor's desk, Ramesh ji.** Point at **Needs attention**: possible low-sugar symptoms (the patient said shaky and sweaty), HbA1c / kidney / cholesterol tests missing, Amaryl not mentioned, Amaryl dose unclear.
3. **Click a highlighted value** (for example HbA1c 8.9 %). The paper opens with the line highlighted. This is the key moment.
4. **The smudged dose.** Open the Amaryl dose: it reads "? mg", marked unsure. Correct it and show that the flag clears and the AI's original reading is kept.
5. **Trends.** HbA1c rises 7.2 to 8.9; the fasting glucose point from the mmol/L paper is a hollow point, converted, both values kept.
6. **Second patient (Mohan Lal).** HbA1c rises then falls; dashed lines mark when a second medicine appeared in the prescriptions. Say: "this shows the order of events in the records, not that the medicine caused it."
7. **Third patient (Kavita Sharma).** Steady for a year, then a jump. In the Monitoring plan, type a review margin of 1 for HbA1c and save. The "change from own baseline" check appears. Say: "the doctor sets the number, the software does not suggest one."
8. **Kiosk in Hindi** (if time): answer a few questions, show the confirm slip written back in handwriting.

**If the internet or the key fails:** use the backup values button (labelled "Offline demo data" on screen). The three patients all work with no AI at all.

---

## 5. How it works (the short version)

```
Patient at kiosk  ->  8 confirmed answers  ----------------------------+
                                                                         |
Photo of old paper -> AI reads page into lines + positions               |
                   -> AI turns lines into tests / medicines (JSON)       v
                   -> code checks each value really appears on the page  Database
                   -> code normalises names, units, dates, brands        (SQLite)
                   -> second AI re-reads each value line; code compares     |
                   -> saved with its document, page and box  ---------------+
                                                                         |
Rules (plain code) + trends + schedule + doctor's plan  <----------------+
                   -> doctor's one-page summary, every value linked to its paper
```

Stack that was **built**: Python 3.12, FastAPI, SQLModel with SQLite, Pillow and pypdfium2 for images and PDFs, rapidfuzz for fuzzy matching; React 18, TypeScript, Vite, Recharts, React Router; pytest (69 tests). Hosted AI: NVIDIA's free developer API.

---

## 6. Where AI is used, and where it is not

| Job | Who does it | Model |
|---|---|---|
| Read a page photo into lines and positions | AI | `nvidia/nemotron-3.5-super-vl-120b-a12b` (vision-language model) |
| Turn the lines into tests and medicines | AI | `nvidia/nemotron-3.5-lightning-30b-a3b` |
| Fallback: read the image straight into fields | AI | the vision-language model |
| Second reading of each value line from a zoomed crop | AI | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` |
| Voice to text | AI (optional) | Parakeet 1.1B multilingual, or the browser's recognition (what works today) |
| Check a value really is on the page | plain code | |
| Names, units, dates, medicine brands | plain code | |
| The rules, flags, trends, schedule, baseline check | plain code | |

**Why a general vision model and not OCR?** The team chose "AI reading with the source line kept" over a pure OCR pipeline, and the project constraint was free tools only. NVIDIA's dedicated parsing model (Nemotron Parse) and the Llama 3.x models were **retired by NVIDIA** during the project (the service answers HTTP 410 "Gone"), so the page reader became a general vision-language model that also returns line positions. We tested that the positions land on the right lines.

**Why free hosted models?** It keeps the project free and runnable from a laptop. The cost is that models can be retired, which already happened. The setup script (`scripts/spike_parse.py`) detects a retired model and lists the replacements.

**The deck vs the built app.** The early architecture notes (`docs/03`) and the submitted deck mention a *planned* stack: Whisper, PaddleOCR or Tesseract, and PostgreSQL. The build uses NVIDIA hosted models and SQLite instead. If asked, say: "the deck described the planned open-source stack; during the build we moved to hosted vision-language models for the page reading because they give line positions and handle photos, and to SQLite because a demo does not need a server database. The design and safety rules did not change."

---

## 7. Safety design

1. **AI reads, code decides.** No flag is decided by an AI.
2. **No value without a source.** Every value stores its document, page and box. A value the check cannot tie to a line is shown as "unverified" with a dotted red underline.
3. **Grounding check.** A number must appear in the line the AI claims it came from, as a whole number ("24" is not accepted inside "2024"). Short names must match as whole words (so an invented "ORS" cannot match inside "FORM").
4. **Uncertain stays uncertain.** An unreadable character is written `?`, the value is marked unsure, and it appears in "Unclear readings".
5. **Second reading.** A different model re-reads each value line. A disagreement marks the value unsure and shows both readings. It never changes the value.
6. **Undated pages are unsure.** If a document date cannot be read, every value from that page is marked unsure.
7. **The doctor corrects in one click.** The correction is shown everywhere, and the original AI reading is kept.
8. **The patient confirms every answer** before it is saved, and never sees flags or medical interpretation.
9. **No advice anywhere.** Every screen says "Documentation aid only. Not a diagnosis or treatment advice."
10. **The software chooses no clinical numbers.** Targets, review margins and test intervals come from the doctor. The default rule thresholds are drafts and are labelled "a doctor must review".
11. **The API key stays on the server** and is never committed. The public demo has no key at all.

---

## 8. The nine fixed rules (plain code)

| Rule | Looks at | Result |
|---|---|---|
| Urgent symptoms | Chest pain, fainting, severe breathlessness ticked; sudden vision loss; urgent words in free text | Flag |
| Possible low-sugar symptoms | "Shaky or sweaty" yes, or words like shaky, sweaty, dizzy, काँपना, पसीना | Flag |
| Missed doses | Forgets medicine once a week or more | Note |
| Feet and eyes | Non-healing wound or sudden vision loss: flag. Numbness, tingling, blurry vision: note | Flag or note |
| HbA1c up to date | Last HbA1c within **90 days** | OK or missing |
| Kidney test up to date | Creatinine, eGFR or urine albumin within **365 days** | OK or missing |
| Cholesterol test up to date | LDL, total, HDL or triglycerides within **365 days** | OK or missing |
| Medicine match | Medicines on prescriptions from the last **30 months** compared with what the patient named, both ways | To confirm |
| Unclear readings | Anything unsure or unverified and not yet checked | To confirm |

A tenth kind, **change from own baseline**, exists only for a test where the doctor typed a review margin. The doctor's repeat intervals replace the draft defaults for that patient.

All thresholds are **drafts from general knowledge**. They have not been reviewed by a clinician. Say that yourself.

---

## 9. What is proven, and what is not

**Measured (the evaluation script, `eval/run_extraction_eval.py`)**
- 14 synthetic images: 7 made-up papers, each clean and damaged (blur, rotation, darkening, heavy JPEG).
- **64 of 64 fields correct** (dates, values, units, medicines), and every value tied to a box on the page. A page takes about 4 to 6 seconds.
- Last full run was before the latest prompt tweaks. It should be re-run before quoting it as current (see the pre-presentation checklist).
- The demo patient read by the AI produced exactly the expected nine rule results.
- 69 automated tests pass.

**Real-world tests that went wrong, and what we did about them (this is a strength if you tell it well)**
- On a **real handwritten hospital note**, the first reader read "RBS 50 mg/dl" as **10** and called it clear. We built the second reading; it read 50, so the disagreement is now flagged.
- On a **US military prescription form** (cursive, low resolution) the AI once invented a medicine "ORS" that is not on the page. The cause was an example sentence in our own instructions. We removed the copyable example, made short names require a whole-word match, and made medicine rows show "Unsure reading" and "No exact source" stamps.
- Names and ordinary handwritten words can still be misread. That is exactly why every value links to its paper.

**Not proven**
- **Small and synthetic.** 7 made-up papers for one made-up patient says nothing about real handwriting or real lab layouts.
- **A faint smudge can still be guessed.** On the damaged synthetic prescription both models read the ghost of a digit as "1 mg", so nothing is flagged. The second reading catches readers that disagree, not an error both make.
- **The clinician time study** from `docs/04` (3 to 5 reviewers, planted gaps, minutes taken) **has not been run.** So there is no time-saving or gap-finding number, and none may be claimed.
- **No clinical validation or pilot.** The thresholds are drafts.
- **NVIDIA voice** untested.
- **The AI is non-deterministic.** Even at temperature 0, the hosted models can answer slightly differently between runs on hard images. We save every reply, so a demo is repeatable, but a new hard page can give a different result.

---

## 10. What makes it different

**Novelty, honestly stated.** It is the combination and the discipline, not "we used AI":
- **Click-to-source on every value**, so the doctor checks the AI in one click instead of trusting a summary.
- **AI reads, code decides**, so the safety logic is auditable.
- **Cross-check of patient and papers**: what the patient says they take against what old prescriptions list, in both directions.
- **Indian paper reality**: mmol/L and mg/dL, DD/MM dates, brand names mapped to generics with the written name kept, handwriting.
- **Honest uncertainty**: unreadable stays `?`, two readers compared, never silently guessed.
- **Doctor-owned personalisation**: the targets, margins and intervals are typed by the doctor, and charts show records and medicine events without claiming cause.
- **Free to run**: free hosted models, open-source software, a laptop.

**Compared with ABHA (Ayushman Bharat Digital Mission).** They are complementary, so do not say "we are better".

| | ABHA | MediKiosk-DM |
|---|---|---|
| What it is | National health ID and a system for storing and sharing records with consent | A pre-consultation intake and summary tool |
| Main job | Keep and share records across providers | Make the next visit faster and safer |
| Data source | Records already digitised and linked to the ID | Photos of paper the patient carries, plus a guided Hindi/English interview |
| Output for the doctor | The records | One page of flags, trends and medicines, each value linked to its paper |

Gap we fill: ABHA works when records are already digital and linked. In a typical OPD patients still carry paper from many labs, and nothing asks them how they have been or checks their answers against old prescriptions. Future: an ABHA ID could be an input and the summary could be saved back. This is a design direction, not built. Check ABHA's current details from ABDM's own material before presenting, because this description is from general knowledge.

**Other products.** The team's rule (`docs/07`) is not to name competing products on slides. If asked, say existing tools are mostly EMRs and record vaults that store documents, not intake tools that read paper and cross-check it with the patient's own account.

---

## 11. Sustainable Development Goal

- **SDG 3, Good Health and Well-being.** Target **3.4** (reduce premature mortality from non-communicable diseases: diabetes is the biggest one in India) and **3.8** (universal health coverage, quality of care: a better few minutes in a crowded OPD).
- **SDG 10, Reduced inequalities:** Hindi-first, voice and touch, usable with staff help.
- **SDG 9, Industry, innovation and infrastructure:** a low-cost digital layer that complements existing systems.

Cautions: say these are the project's **aims**, not demonstrated outcomes. Do not claim mortality reduction. Check the official SDG target wording before printing it on a slide. Measurable proxies you can name: review time, extraction errors, planted gaps found, usability tests.

---

## 12. Deployment and cost

- **Local:** backend `uvicorn main:app --port 8000`, frontend `npm run dev`, open http://localhost:5173. Needs `app/backend/.env` with `NVIDIA_API_KEY`.
- **Public demo:** frontend on **Vercel** (root `app/frontend`, variable `VITE_API_BASE`), backend on **Railway** from the repo's `Dockerfile`. The public site has `PUBLIC_DEMO=1`: no live AI calls, no uploads, no API key, the demo patients load at every start. The database resets on every restart, which is fine for a demo.
- **Cost:** everything is free except hosting beyond trial credits. NVIDIA's key is a free developer key for trials and testing (rate limited, roughly 40 requests a minute, not for production). Railway gives a one-time trial credit, so check its pricing page. Beyond the trial you would pay for hosting or self-host the models.
- **Saved replies:** the demo needs the shipped AI replies (`data/demo_cache`). They are saved under a hash of the request, so they **must be rebuilt whenever the AI prompts or models change.**

---

## 13. Honest limits (say these before they ask)

- Synthetic data only, one small evaluation, no clinical validation, no pilot.
- Real handwriting is hard. The system reduces silent errors with a second reading and source links, and does not eliminate errors.
- The rule thresholds and the medicine map are drafts that need clinician review.
- No login or access control: anyone with the link can open the doctor pages. Acceptable only because data is synthetic.
- Real use would need consent in the patient's language, India's DPDP Act 2023 compliance, encryption, retention limits, and alignment with ABDM consent rules.
- The free hosted models can be retired or rate-limited at any time.
- Hindi speech recognition accuracy varies by accent and has not been tested here.

---

## 14. Questions and short answers

### The big ones
**Why does this need to exist?** The few minutes of a diabetes follow-up are where complications are caught or missed, and the information is trapped in paper and in the patient's memory.

**Who is it for?** The patient (a guided, confirmed intake in their language), and the doctor (a one-page, checkable summary). The clinic needs nothing integrated.

**What problem does it solve that a normal EMR does not?** An EMR needs records already typed in. We start from the paper in the patient's bag and from the patient's own account, and check one against the other.

**Why is this better than just asking the patient?** Patients forget (55% recalled instructions in the cited study) and papers hold facts they never mention. We compare both.

**What is your SDG?** SDG 3, mainly 3.4 and 3.8 (section 11).

**How is it different from ABHA?** Complementary: ABHA is the record layer, we are the intake and cross-check layer (section 10).

**Is it a medical device? Is it safe?** It is a documentation aid. It does not diagnose, change medicines or advise treatment, flags are fixed rules, every value is checkable and correctable, and a doctor makes every decision. It has not been clinically validated.

### AI and accuracy
**Why not just OCR?** We use vision-language models that read the whole page, handle photos and return line positions for the highlight. OCR alone gives text without understanding the layout of a lab table. (The earlier plan listed PaddleOCR or Tesseract; the build moved to hosted vision models.)

**What if the AI is wrong?** Every value opens its source line; the doctor verifies or corrects it. Unsure values are marked, a second model re-reads each value line, and any disagreement is flagged. The AI never changes a value silently.

**How accurate is it?** 64 of 64 fields on 14 synthetic images (clean and damaged). That is a small, made-up, printed set. On real handwriting it made mistakes, which we found by testing and addressed (section 9). Do not quote it as general accuracy.

**Does the AI invent things?** It did once, on a hard handwritten form. The cause was our own example text in the instructions. We removed it and added a stricter whole-word check. It can still happen, which is why unverified values show a "No exact source" stamp.

**Which AI models?** Section 6. All hosted on NVIDIA's free developer API.

**Why NVIDIA?** It offers free hosted models with one key and vision-language models that return line positions. The trade-off is that models are sometimes retired.

**Is the output the same every time?** Not always, even at temperature 0. We save every reply, so the demo is repeatable.

**Did you train a model?** No. We use pretrained hosted models and wrap them in checks.

**Where do the flags come from? Does AI decide urgency?** No. The rules are plain, reviewable code with thresholds in one file. The AI never decides what is urgent.

**How does the second reading work?** A different model re-reads each value's line from a zoomed crop. Code compares numbers; if they differ, the value is marked unsure and both readings are shown. We proved it on one real note (10 versus 50), not as general reliability.

### Clinical
**Who set the thresholds?** The team, from general knowledge. They are drafts, labelled as such, and need clinician review before being called clinically sound.

**Do you recommend targets or doses?** No. The doctor types any target, review margin or interval. The software suggests none.

**Does the medicine timeline say a medicine worked?** No. It shows the order of events in the records only, and says so on screen.

**What about hypoglycaemia?** The kiosk asks about shaky or sweaty spells, the rule flags it for the doctor, and the patient only ever sees that the doctor will be told. (The kiosk does not display flags to the patient.)

**What does the ADA say?** We have not verified the ADA 2026 statements that were discussed (individualised targets, A1C alone being incomplete), so do not cite them as ADA wording. The general principle that diabetes monitoring should be individualised is why the doctor, not the software, sets the numbers.

### Privacy and ethics
**Whose data is it?** Synthetic only. No real patient data was collected or stored. (A real handwritten note was used once for a local test, not saved, not committed, and not part of the demo.)

**What would real use need?** Informed consent in the patient's language, India's DPDP Act 2023, encryption, access control, minimal retention, deletion, ABDM consent alignment, and a clinician-reviewed rule set.

**Bias and fairness?** Speech and handwriting recognition perform unevenly across accents and writing styles. We confirm every voice answer on screen, allow typing and tapping, and mark uncertain readings. Testing across accents is future work.

**What about patients who cannot read or have no smartphone?** The kiosk uses large buttons, spoken answers and tick boxes, and a clinic assistant can operate it.

### Engineering
**What is the architecture?** Section 5.

**Why SQLite?** A demo needs no server database, and it keeps setup to one file. A real deployment would use a managed database.

**How do you handle PDFs and rotated phone photos?** PDFs become page images (up to 5 pages, 10 MB), and photo rotation is corrected.

**What happens if NVIDIA is down or rate-limited?** Calls retry with backoff, replies are cached on disk, and the backup values mode works with no AI at all.

**How is the key protected?** It sits in a git-ignored `.env` on the server only. The public demo has no key.

**How do you test it?** 69 automated tests (normalisation, rules, grounding, second reading, the API, plan and trends), plus the extraction evaluation on synthetic images, plus manual tests with real handwriting.

### Business and scale
**Is it sustainable?** Software and models are free or open. Costs are hosting and, beyond the free trial, model calls (a few cheap calls per page) or self-hosting the models. A pilot would test the real cost per patient.

**How would it make money or be adopted?** Not decided. A natural path is clinics or hospital groups through a pilot, integrating with ABHA and existing records. Do not invent revenue numbers.

**Why would a doctor trust it?** Because every value is one click from the paper, unsure values are visibly marked, and the rules are readable.

**What is next?** Re-run and widen the evaluation, a second read for doses, a clinician review of the rules, a small supervised pilot with the time study, returning patients and repeated visits, more languages, and ABHA integration.

### Team and process
**Who built it?** Team Mayhem for Himovation 2026 Solve-a-Thon at SRHU: Rohit Negi (leader), Vaishnavi Bijalwan, Nayan, Shivam Thapliyal and Vasavi. Rohit pushed the first code from the build plan, then the app was completed, redesigned and hardened.

**How did you build it so fast?** An AI coding assistant wrote and tested much of the code under the team's direction, from a written plan (`BUILD_PLAN.md`). The team supplied the design rules, the testing with real images, and the decisions. Be straightforward about this if asked.

---

## 15. Numbers cheat sheet

| What | Value |
|---|---|
| People with diabetes in India (estimate) | 101 million, 11.4% (ICMR-INDIAB 2023) |
| Documents with key follow-up information | 24% of 509 (chronic disease, Kerala and Himachal Pradesh) |
| Patients who recalled verbal instructions | 55% (283 of 513), same study |
| Kiosk questions | 8 |
| Rules | 9 fixed rules, plus a baseline check only when the doctor sets a margin |
| Default recency thresholds (draft) | HbA1c 90 days, kidney 365 days, lipids 365 days |
| Medicine match window | 30 months |
| Evaluation | 14 synthetic images, 64 of 64 fields, a small made-up set |
| Time per page | about 4 to 6 seconds (a hard handwritten page 12 to 20 seconds) |
| Tests | 69 passing |
| Demo patients | 3 (Ramesh Kumar, Mohan Lal, Kavita Sharma), all made up |
| Upload limits | JPG, PNG, WebP, PDF, 10 MB, 5 pages |
| Unit conversions | glucose ×18.016, cholesterol ×38.67, triglycerides ×88.57, creatinine ÷88.4, HbA1c 0.09148 × mmol/mol + 2.152, UACR ×8.84 |

---

## 16. Glossary

- **HbA1c:** average blood sugar over about 3 months, in %. **FBS / fasting glucose:** sugar after fasting. **RBS:** random blood sugar.
- **mmol/L vs mg/dL:** two units for glucose. Multiply mmol/L by 18.016 for mg/dL.
- **eGFR, creatinine, UACR:** kidney function tests. **LDL, HDL, triglycerides, total cholesterol:** lipid (cholesterol) tests.
- **Rx:** prescription. **1-0-1:** one tablet in the morning, none at noon, one at night.
- **OPD:** outpatient department. **ABHA / ABDM:** India's health ID and the digital mission behind it.
- **Grounding:** checking that an extracted value really appears in the line the AI says it came from.
- **Bounding box:** the rectangle around a line of text on the page, used for the highlight.
- **Synthetic data:** made-up data that looks real but belongs to no person.
- **Baseline:** a patient's own recent average, used to spot a change from their usual.

---

## 17. Things not to say

- "It is clinically validated" or "it saves doctors X minutes". Neither has been measured.
- "It diagnoses / predicts / recommends / prevents complications."
- "It is better than ABHA" or "it replaces the EMR".
- "The AI is 100% accurate." The 64 of 64 is a small clean synthetic set.
- "It uses OCR." It uses AI vision models, and the deck's OCR wording is the planned design.
- "Real patient data was used." It was not (one real note was tested locally and discarded).
- Any ADA citation as exact wording, until it is checked.
- Any revenue or user numbers.

---

## 18. Before you present: checklist

1. Start the backend and frontend. Open http://localhost:8000/api/health and check `"ok": true`.
2. Open http://localhost:5173 and load the demo. **If "Use saved AI replies" errors, the saved replies need rebuilding** (the prompts changed after they were saved). Until then, use "Read the 7 papers with NVIDIA AI" (needs the key and internet) or "Use backup values (no AI)".
3. Click "Add 2 more demo patients" on the home page so Mohan Lal and Kavita Sharma are there.
4. Rehearse the demo in section 4 once, including setting Kavita's review margin.
5. Have a screenshot or recording of the dashboard as a fallback.
6. Re-run the evaluation if you plan to quote a number (`eval/run_extraction_eval.py`).
7. Do not use any real patient paper in front of the evaluators.
