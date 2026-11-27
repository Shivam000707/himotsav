# MediKiosk-DM: Build Plan

**Audience:** an AI coding agent (Antigravity) building the first working version, and the team members supervising it.
**Time box:** about 3 hours of build time. The phases are ordered so that a demo works after every phase. If time runs out, stop at the end of the last finished phase.
**Cost rule:** everything must be free. That means the NVIDIA build.nvidia.com free developer API, open-source libraries, SQLite, and running on a laptop. Do not add paid services, paid hosting, or any OCR engine (no Tesseract, no PaddleOCR).

## 1. Context

MediKiosk-DM is an intake kiosk for Type 2 diabetes follow-up visits in Indian OPDs. While the patient waits, it does three things:
1. It asks fixed questions in Hindi or English.
2. It reads photos of old lab reports and prescriptions.
3. It gives the doctor a one-page summary in which every value links back to the exact region of the source document.

The repo holds documentation only: `docs/01` to `docs/07`, a submission deck, and a scripted simulation in `simulation/medikiosk-simulation.html`. No application code exists yet. This plan turns that design into working software.

Read these before coding:
- `docs/02-solution-and-scope.md`: the features and the non-goals.
- `docs/03-architecture.md`: the components, the data model and the draft rules.
- `docs/05-safety-privacy-ethics.md`: the boundaries the product must keep.
- `simulation/medikiosk-simulation.html`: the target experience and the demo data. These lines are its source of truth:
  - `PAPERS` (around line 641): the 7 synthetic documents for "Ramesh ji".
  - `QA` (around line 659): the intake questions in Hindi and English.
  - `EX` (around line 685): the expected extractions.
  - `RULES` (around line 702): the 9 expected rule results.
  - CSS `:root` tokens (around line 17): the colour palette to reuse.

### Hard rules (never break these)
1. The product **never diagnoses, never suggests or changes medicines, and never gives treatment advice**. Every screen that shows output carries: "Documentation aid only. Not a diagnosis or treatment advice."
2. **The AI reads. Plain code decides.** Unit conversion, brand-to-generic mapping, date handling, flags and missing-data checks are all deterministic Python. The language model never decides whether something is urgent.
3. **No value without a source.** Every extracted value stores its document, page and bounding box. A value the model cannot tie to a source block is shown as "unverified", never as fact.
4. **Uncertain means uncertain.** If text is unclear, mark it `uncertain: true` and show it to the doctor. Never guess.
5. **Synthetic data only.** No real patient data anywhere.
6. **The API key stays on the backend.** It goes in `.env`, which is git-ignored, and never reaches the frontend or a commit.

> **Update, 27 Nov 2026 (checked against the live service):** NVIDIA has retired `nvidia/nemotron-parse`, `meta/llama-3.3-70b-instruct` and `meta/llama-3.2-90b-vision-instruct` (HTTP 410). The page reader now uses the vision-language model `nvidia/nemotron-3.5-super-vl-120b-a12b`, which returns each line of text with a box on a 0 to 1000 scale. Structuring uses `nvidia/nemotron-3.5-lightning-30b-a3b`. Both are called with `chat_template_kwargs {"enable_thinking": false}`. Where this plan says "Nemotron Parse" or "Llama", read it as these models. Still no OCR engine.

## 2. Free services and the NVIDIA API

All AI calls go to NVIDIA's hosted free developer API, at build.nvidia.com, with one key.

| Need | NVIDIA model (hosted, free trial) | How it is called | Notes |
|---|---|---|---|
| Read a document image into text blocks with bounding boxes | **Nemotron Parse** (`nvidia/nemotron-parse`; the older name is `nvidia/nemoretriever-parse`) | OpenAI-style `POST https://integrate.api.nvidia.com/v1/chat/completions`, image as base64 `<img src="data:image/...;base64,..."/>`, tool `markdown_bbox` | It returns text, a semantic class and a bounding box for each block. This is a vision-language model, not an OCR engine. |
| Turn the blocks into structured medical fields | A text LLM, default `meta/llama-3.3-70b-instruct` | Same endpoint, `temperature: 0` | Returns JSON that refers to block ids, so bounding boxes come from Nemotron Parse and are never invented by the LLM. |
| Fallback when Parse reads a page badly (for example handwriting) | A vision LLM, default `meta/llama-3.2-90b-vision-instruct` | Same endpoint, image in the message | Values from this path get the whole page as their source region and `unverified: true` unless they can be text-matched to a Parse block. |
| Hindi or English speech to text | **Parakeet 1.1B RNNT multilingual ASR** (its build.nvidia.com page lists Hindi) | gRPC via `nvidia-riva-client` to `grpc.nvcf.nvidia.com:443`, with `function-id` and `authorization: Bearer <key>` metadata | Optional, Phase 5. The browser Web Speech API (`hi-IN`) and typing are the fallbacks. |

**Free tier facts to design around:**
- Access is a trial for research and testing under NVIDIA's API Trial Terms. That is fine for a hackathon. It is not for production.
- Calls are **rate-limited, roughly 40 requests per minute**, and can be throttled. Therefore:
  - Cache every NVIDIA response on disk, keyed by the SHA-256 of the request.
  - Retry 429 and 5xx errors with exponential backoff: 3 tries, starting at 2 s.
  - Never call NVIDIA from a loop without a small delay.
- Hosted vision endpoints have historically limited inline base64 images to about **180 KB**. Before every vision call, resize the long side to at most 1600 px and re-encode as JPEG, lowering the quality until the file is under 170 KB.
- Model names and ASR function IDs change. **Put every model id and function id in `.env`.** Confirm each one on its build.nvidia.com page during Phase 0, before building on it.

Getting a key (a team member does this once): sign in at build.nvidia.com, open any model page, click "Get API Key", and put it in `app/backend/.env` as `NVIDIA_API_KEY=nvapi-...`.

## 3. Stack (all free)

| Layer | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI, Uvicorn, SQLModel on SQLite, Pydantic v2, httpx, Pillow, pypdfium2 (to turn PDFs into images), python-dateutil, rapidfuzz, PyYAML, python-dotenv, nvidia-riva-client (Phase 5) |
| Frontend | React with TypeScript on Vite, React Router, Recharts for charts, plain CSS using the simulation's colour tokens |
| Tests | pytest. Network calls are mocked with recorded fixtures. |
| Fonts for synthetic reports | Google Fonts under the OFL licence: Kalam (handwriting), Noto Sans and Noto Sans Devanagari. Download the TTFs into `data/synthetic/fonts/`. |
| Run | Local laptop: backend on `:8000`, frontend on `:5173` |

## 4. Repository layout to create

```
BUILD_PLAN.md                 this file
README.md                     add "How to run" section at the end
.gitignore                    .env, data/uploads/, data/cache/, *.db, node_modules/, __pycache__/
app/
  backend/
    .env.example              NVIDIA_API_KEY=, model ids, DEMO_TODAY=2026-10-14
    requirements.txt
    main.py                   FastAPI app, CORS for http://localhost:5173 only
    config.py                 reads .env
    db.py, models.py          SQLModel tables (section 5)
    schemas.py                request/response models
    routers/
      patients.py intake.py documents.py doctor.py asr.py demo.py
    services/
      nvidia_client.py        one place for all HTTP calls, caching, retry, image compression
      parse.py                Nemotron Parse call + block parsing
      structure.py            LLM call that turns blocks into fields (prompt in section 7)
      extraction.py           orchestrates parse -> structure -> normalise -> save
      normalize.py            units, test names, medicine names, dates (pure functions)
      rules.py                rule engine (pure functions)
      summary.py              deterministic summary builder
      asr.py                  Riva gRPC client (Phase 5)
    resources/
      questions.json          intake script, Hindi + English
      rules.yaml              thresholds and keyword lists
      med_map.csv             brand -> generic
      test_aliases.yaml       label variants -> canonical test name
    tests/
      fixtures/               recorded NVIDIA responses (JSON)
      test_normalize.py test_rules.py test_parse.py test_extraction.py
  frontend/
    (Vite React TS app; pages and components in section 9)
data/
  synthetic/
    ramesh.json               the 7 papers, ported from the simulation's PAPERS
    generate.py               renders PNGs + damaged variants + labels.json
    fonts/
    images/                   generated
    labels.json               generated ground truth
  uploads/                    runtime, git-ignored
  cache/                      runtime NVIDIA cache, git-ignored
eval/
  run_extraction_eval.py
  results.md                  generated
```

## 5. Data model (SQLite via SQLModel)

| Table | Fields |
|---|---|
| `Patient` | id, display_name (synthetic), age, language (`hi`/`en`), created_at |
| `Document` | id, patient_id, kind (`lab`/`rx`/`unknown`), source_org (nullable), doc_date (nullable), file_path, page_count, status (`pending`/`done`/`failed`), error (nullable), created_at |
| `Page` | id, document_id, page_no, image_path, width_px, height_px |
| `Block` | id, page_id, text, block_type, xmin, ymin, xmax, ymax (normalised 0 to 1) |
| `Observation` | id, patient_id, document_id, page_id, block_id (nullable), test (canonical), label_as_written, value_raw, unit_raw, value_num (nullable), unit_std, value_std (nullable), converted (bool), obs_date, uncertain (bool), unverified (bool), note, verified_by_clinician (bool), edited_value (nullable) |
| `Medication` | id, patient_id, source (`rx`/`intake`), document_id (nullable), block_id (nullable), name_as_written, generic_name (nullable), strength, frequency (for example `1-0-1`), rx_date (nullable), uncertain (bool), note |
| `IntakeAnswer` | id, patient_id, question_id, value_json, raw_text (nullable, the voice or typed words), confirmed (bool), answered_at |
| `DoctorNote` | id, patient_id, text, updated_at |

Rule results and the summary are computed on request from these tables. They are not stored.

## 6. Normalisation (deterministic, `services/normalize.py`)

**Canonical tests:**
- `hba1c`
- `fasting_glucose`
- `postprandial_glucose`
- `random_glucose`
- `creatinine`
- `egfr`
- `uacr`
- `total_cholesterol`
- `ldl`
- `hdl`
- `triglycerides`

`test_aliases.yaml` maps label variants to them, matched case-insensitively with rapidfuzz above a score of 90. Examples: "Glycated Hb", "HbA1C", "A1c" → `hba1c`; "FBS", "Fasting Blood Sugar", "FPG" → `fasting_glucose`; "Urine albumin / creatinine", "UACR", "ACR" → `uacr`. Anything that does not match keeps `test="other"` and is still shown.

**Unit conversion** (stored as `value_std` and `unit_std`; the original value is always kept and shown):

| Test | From | To | Formula |
|---|---|---|---|
| Glucose (all three) | mmol/L | mg/dL | × 18.016, rounded to an integer (8.9 → 160) |
| HbA1c | mmol/mol | % | 0.09148 × v + 2.152, one decimal |
| Creatinine | µmol/L | mg/dL | ÷ 88.4, two decimals |
| Total, LDL and HDL cholesterol | mmol/L | mg/dL | × 38.67, integer |
| Triglycerides | mmol/L | mg/dL | × 88.57, integer |
| UACR | mg/mmol | mg/g | × 8.84, integer |

Set `converted=true` whenever a conversion happened. If the unit is missing or unknown, keep the raw value, set `uncertain=true` and add the note "unit not readable".

**Dates:** parse with `dateutil.parser.parse(dayfirst=True)`, since Indian reports use DD/MM/YYYY. If the day and month could swap (both 12 or less) and the text uses only digits, keep the day-first reading but add the note "date order assumed DD/MM".

**Medicines:** `med_map.csv` has the columns `brand,generic,notes` and starts with these rows:
- Glycomet → metformin
- Glycomet GP → glimepiride + metformin
- Amaryl → glimepiride
- Janumet → sitagliptin + metformin
- Januvia → sitagliptin
- Galvus Met → vildagliptin + metformin
- Jardiance → empagliflozin
- Forxiga → dapagliflozin
- Lantus → insulin glargine
- Telma → telmisartan
- Atorva → atorvastatin
- Rosuvas → rosuvastatin
- Ecosprin → aspirin

Match with rapidfuzz above 88 after removing "Tab.", "Cap." and strengths. Always store and show `name_as_written`. The header comment in the file must say: "Draft list. Needs clinician review."

## 7. Extraction pipeline (`services/extraction.py`)

For each uploaded file:
1. **Save** the file to `data/uploads/<patient>/<doc>/`. Accept JPEG, PNG, WebP and PDF, up to 10 MB. Turn PDF pages into PNG at 150 dpi with pypdfium2. Fix EXIF rotation with Pillow.
2. **Compress** each page for the API as described in section 2. Keep the full-size image for display.
3. **Parse** each page with Nemotron Parse (`services/parse.py`):
   - Use the `markdown_bbox` tool and `tool_choice` naming it.
   - Read `choices[0].message.tool_calls[0].function.arguments`. It is a JSON string holding a list of blocks with `bbox{xmin,ymin,xmax,ymax}`, `text` and `type`. Flatten nested lists.
   - Coordinates come normalised from 0 to 1. **Confirm this in Phase 0.** If they turn out to be pixels of the sent image, divide by its size.
   - Save the blocks with ids `b0, b1, ...` for each page.
4. **Structure** with the text LLM (`services/structure.py`). Send the block list as `[{"id":"b3","type":"Text","text":"HbA1c 7.6 %"}, ...]` with this system prompt, word for word:

   ```
   You extract data from ONE diabetes lab report or prescription. You receive text blocks, each with an id.
   Return ONLY a JSON object with this shape:
   {"kind":"lab"|"rx"|"unknown","source_org":string|null,"doc_date":string|null,"doc_date_block":string|null,
    "observations":[{"label":string,"value":string,"unit":string|null,"block_id":string,"uncertain":boolean,"note":string|null}],
    "medications":[{"name":string,"strength":string|null,"frequency":string|null,"block_id":string,"uncertain":boolean,"note":string|null}]}
   Rules:
   - Copy values exactly as written. Do not convert units, do not correct spelling, do not compute anything.
   - Every item must have the block_id of the block it was read from. If you cannot point to a block, leave the item out.
   - If any character of a value, unit, dose or date is unclear, smudged or ambiguous, set "uncertain": true and explain in "note". Never guess.
   - Do not add medical interpretation, diagnosis, or advice. Extract only.
   - Include only these tests if present: HbA1c, fasting / post-meal / random glucose, creatinine, eGFR, urine albumin-creatinine ratio, total cholesterol, LDL, HDL, triglycerides. Include every medicine on a prescription.
   ```

   Validate the reply with Pydantic. If it is invalid, retry once with the validation error added to the message. If it is still invalid, mark the document `failed` and keep the blocks so a person can see them.
5. **Verify grounding.** Each item's `value` must appear in its block's text (rapidfuzz `partial_ratio` of 90 or more). If it does not, search all blocks on the page and re-link to the best match. If nothing matches, set `unverified=true`. This is the defence against invented values.
6. **Fallback.** If Parse returns fewer than 3 blocks, or the structuring step finds nothing on a page whose `kind` is `rx`, send the page image to the vision LLM with the same output schema, using `block_id: null`. Then run step 5 against the Parse blocks. Values that match nothing get `unverified=true` and the whole page as their region.
7. **Normalise** each item (section 6) and save the `Observation` and `Medication` rows. Set `Document.status=done`.

Run extraction synchronously inside the upload request. A page takes about 2 NVIDIA calls, which is fine for the demo. Return the document with its items so the kiosk can show "Read 3 values from this report".

## 8. Rule engine (`services/rules.py` + `resources/rules.yaml`)

Pure functions with the signature `evaluate(patient_data, today) -> list[RuleResult]`. A `RuleResult` holds `{rule_id, name, question, status, evidence_text, evidence_refs}`. `status` is one of `ok`, `flag`, `missing`, `check` or `note`. `evidence_refs` points to observation, medication or answer ids. `today` comes from `DEMO_TODAY` if it is set, otherwise from the real date. Set `DEMO_TODAY=2026-10-14` for the demo, because that is the simulation's date.

Implement exactly these 9 rules. They match the simulation's `RULES` array.

| id | Name | Logic | Status |
|---|---|---|---|
| `urgent_symptoms` | Urgent symptoms | Answer `urgent_symptoms` includes chest pain, fainting or severe breathlessness, OR free text matches the urgent keywords | `flag` if found, else `ok` |
| `low_sugar_symptoms` | Possible low-sugar symptoms | Answer `shaky_sweaty` is yes, OR free text matches the low-sugar keywords | `flag` / `ok` |
| `missed_doses` | Missed doses | Answer `missed_doses` frequency is weekly or more | `note` / `ok` |
| `feet_eyes` | Feet and eyes | Any yes among foot wound, numbness or tingling, blurry vision | `note` / `ok` (a non-healing foot wound is `flag`) |
| `hba1c_recent` | HbA1c up to date | Latest `hba1c` is no older than `hba1c_max_days` (90) | `ok` / `missing` |
| `kidney_recent` | Kidney test up to date | Latest `creatinine`, `egfr` or `uacr` is no older than 365 days | `ok` / `missing` |
| `lipid_recent` | Cholesterol test up to date | Latest `ldl`, `total_cholesterol`, `hdl` or `triglycerides` is no older than 365 days | `ok` / `missing` |
| `med_match` | Medicine match | Every generic on the prescriptions from the last 24 months appears among the patient's intake medicines | `check` for each missing one, else `ok` |
| `unclear_readings` | Unclear readings | Any observation or medication with `uncertain` or `unverified` set | `check` / `ok` |

`rules.yaml` holds the thresholds and keyword lists in both languages. Low-sugar keywords, for example: shaky, sweating, sweaty, trembling, dizzy, confused, काँपना, कांपना, पसीना, घबराहट, चक्कर, kaanpna, paseena. The urgent keywords: chest pain, सीने में दर्द, faint, बेहोश, breathless, साँस फूलना. The file header must say: "Draft thresholds from general knowledge. Must be reviewed by a doctor before being presented as clinically sound."

When a flag fires, the patient sees only "We will tell the doctor about this." The patient never sees medical advice.

## 9. API (FastAPI, prefix `/api`)

| Method + path | Purpose |
|---|---|
| `POST /patients` | Create a patient `{display_name, age, language}` and return it |
| `GET /patients` | List patients for the doctor |
| `GET /intake/questions?lang=hi` | The question script |
| `POST /patients/{id}/answers` | Upsert one answer `{question_id, value, raw_text, confirmed}` |
| `POST /patients/{id}/documents` | Multipart upload of one file. Runs extraction and returns the document, its observations and its medications. |
| `GET /documents/{doc_id}/pages/{page_no}/image` | Serve the full-size page image |
| `GET /patients/{id}/timeline` | Observations grouped by test, sorted by date, with std values; medications with dates |
| `GET /patients/{id}/rules` | List of `RuleResult` |
| `GET /patients/{id}/summary` | Deterministic summary: latest value for each test with source refs, medication list with intake status, rule results, unanswered questions, doctor note |
| `PATCH /observations/{id}` | Doctor edits `{edited_value?, verified_by_clinician?}` |
| `PATCH /medications/{id}` | Same, for medications |
| `PUT /patients/{id}/note` | Doctor's free-text note |
| `POST /asr?lang=hi-IN` | Upload a WAV file (16 kHz mono PCM) and return `{text}` (Phase 5) |
| `POST /demo/seed?mode=cached\|live` | Create "Ramesh ji" (58, hi), upload the 7 generated images, fill his answers from the simulation `QA`. `cached` uses `data/cache` so it works offline. |
| `GET /health` | `{ok, nvidia_key_present}` |

## 10. Intake script (`resources/questions.json`)

Port the simulation's `QA` topics into structured questions, so that the rules read structured answers and not free text. Each question has `id`, `text_hi`, `text_en` and `type`, plus `options` where needed. Every question also allows an optional voice or typed "details" field.

1. `diabetes_years`: number.
2. `current_meds`: multi-select chips of common brands from `med_map.csv`, plus "Other" free text and "I don't know". Each chosen med asks for its frequency (`1-0-1` style picker).
3. `missed_doses`: choice from never / less than weekly / 1–2 times a week / 3 or more times a week.
4. `shaky_sweaty`: yes or no, plus a details field.
5. `urgent_symptoms`: multi-select from chest pain / fainting / severe breathlessness / none.
6. `feet`: multi-select from wound that is not healing / numbness / tingling / none.
7. `eyes`: choice from fine / blurry / sudden vision loss.
8. `anything_else`: free text.

After each answer, show a confirm card with "What we understood: ..." and the buttons Correct / Change, using the simulation's `ch` and `ce` lines as the model. Store `confirmed=true` only after the patient taps Correct.

## 11. Frontend (`app/frontend`)

Copy the simulation's `:root` colour tokens and fonts into `src/styles/tokens.css`. The role colours are `--pat`, `--ai`, `--code` and `--doc`. Use big touch targets on the kiosk, at least 48 px. Every page must work at a phone width of 390 px.

**Routes:**
- `/`: two big buttons (Patient kiosk / Doctor dashboard) and a "Load demo patient" button that calls `/demo/seed?mode=cached`.
- `/kiosk`: a step flow with one screen at a time:
  1. Language: हिन्दी / English.
  2. A note: "This is a demo with made-up data. Your doctor will see your answers."
  3. The questions from section 10, each followed by its confirm card. A mic button records audio for the details field (Phase 5).
  4. Report upload: `<input type="file" accept="image/*,application/pdf" capture="environment" multiple>`. One row per file shows spinner → "Read N values" or "Could not read, staff will check".
  5. Done: "Thank you. Please wait to be called. Your doctor will see this." No advice.
- `/doctor`: the patient list.
- `/doctor/:id`: the dashboard, made of:
  - **Header:** name, age, language, the disclaimer line.
  - **Needs attention:** rule results with status `flag`, `missing` or `check` first, as coloured badges (Doctor to review / Missing / To confirm / Note), each with its evidence and source chips.
  - **Latest results table:** test, value (std unit with a "converted from 8.9 mmol/L" sub-line when converted), date, lab, and a source chip.
  - **HbA1c chart and fasting-glucose chart** (Recharts LineChart). Each point is labelled with its lab, and converted points get a ring marker. Mark gaps of more than 12 months between HbA1c values ("No HbA1c from Jun 2024 to Aug 2026").
  - **Medicines:** generic name with the brand in brackets, strength, frequency, and status ("confirmed today" / "not mentioned today" / "dose unclear").
  - **Patient said:** the confirmed intake answers.
  - **Doctor note:** a textarea that autosaves.
  - **Print** button: a print stylesheet that fits one A4 page.
- **`SourceViewer` component:** clicking any source chip opens a side drawer with the full page image. An absolutely positioned rectangle is drawn at `left = xmin×100%` and `top = ymin×100%`, sized to the bbox, over the image, with the image scrolled to it. It also shows a zoomed crop of the box (CSS `background-position`), plus Verify and Edit buttons that PATCH the row. Show an "unverified, no exact source" banner when `block_id` is null.

## 12. Synthetic data and evaluation

**`data/synthetic/generate.py`** reads `ramesh.json`, which holds the 7 papers ported exactly from the simulation's `PAPERS`.
- It renders each paper as a 1240×1754 PNG with Pillow. Lab reports get a coloured letterhead in the style of the simulation's `--lab-*` colours, using Noto Sans with a Devanagari subtitle where practical. Prescriptions are handwritten in Kalam.
- On p5 the Amaryl dose is drawn smudged (low contrast and blurred), so the ground truth is `uncertain`.
- It writes `labels.json` with the true value, unit, date, document and test for each item, which becomes the ground truth.
- It writes a "damaged" copy of every paper: rotated ±3°, Gaussian blur at radius 1.2, darkened by 25%, and JPEG quality 55. That gives 14 images in total.

**`eval/run_extraction_eval.py`** runs the real pipeline on all 14 images, using the cache when it is there, and compares field by field:
- the test identified;
- the value (exact string after trimming);
- the unit;
- the date;
- the medicine name and frequency.

It writes `eval/results.md` with:
- accuracy overall, for each field type, and for clean versus damaged images;
- whether the smudged dose was flagged as uncertain;
- a list of every miss.

These are the "measured results" for the deck. The clinician time study in `docs/04-evaluation-plan.md` is run by the team, not built here.

## 13. Phases, time boxes and checkpoints

Work in order. At the end of each phase, run the checkpoint and `git commit` (run `git init` in Phase 0, because the repo is not under git yet).

| Phase | Time | Build | Checkpoint (must pass before moving on) |
|---|---|---|---|
| **0. Setup and API spike** | 20 min | `git init`, `.gitignore`, backend venv + `requirements.txt`, Vite app, `.env.example`. Write `app/backend/scripts/spike_parse.py`, which sends one test image to Nemotron Parse and one prompt to the text LLM, then saves the raw responses to `app/backend/tests/fixtures/`. Confirm the model ids, the bbox format (normalised or pixels) and the image size limit. | `GET /health` returns `nvidia_key_present: true`. The fixture files exist, and the real response shape is noted at the top of `parse.py`. |
| **1. Synthetic data + extraction core** | 40 min | `generate.py`, `nvidia_client.py` (cache, retry, compress), `parse.py`, `structure.py`, `normalize.py`, `extraction.py`, plus tests for normalisation and for parsing the recorded fixture | `pytest` passes. Running the extraction CLI on p3 prints HbA1c 7.6 % and fasting glucose 8.9 mmol/L → 160 mg/dL, both with block ids. |
| **2. DB, API, rules** | 30 min | Models, routers, `rules.py`, `rules.yaml`, `summary.py`, `/demo/seed` | `pytest tests/test_rules.py` reproduces all 9 simulation `RULES` statuses for Ramesh ji with `DEMO_TODAY=2026-10-14` (see Verification). `POST /demo/seed?mode=live` and then `GET /patients/1/summary` returns the expected values. |
| **3. Doctor dashboard** | 35 min | `/doctor`, `/doctor/:id`, charts, `SourceViewer`, the edit and verify actions, print | Clicking "8.9 %" HbA1c opens p7 with the box drawn on the HbA1c line. Editing a value persists after a reload. |
| **4. Kiosk** | 25 min | Language, questions, confirm cards, upload flow, done screen | A full Hindi run by tap works end to end, and the answers appear on the dashboard. Uploading a damaged image shows "Read N values". |
| **5. Voice (optional)** | 20 min | `asr.py` with the Riva client using `NVIDIA_ASR_FUNCTION_ID` and `NVIDIA_ASR_LANG` (copy the exact function id and language code from the Parakeet multilingual model's API page), `POST /asr`, a browser WAV recorder (Web Audio at 16 kHz mono, about 40 lines, no ffmpeg needed). Fallback: Web Speech API `hi-IN`, then typing. | Saying "हाँ, शाम को पसीना आता है" fills the details box. The text is confirmed before saving. |
| **6. Eval + polish** | 10 min | Run `eval/run_extraction_eval.py`, write `README` "How to run", warm the cache for the demo | `eval/results.md` exists with real numbers. `mode=cached` seeding works with Wi-Fi off. |

If time is short, cut from the bottom: voice first, then the damaged-image eval, then print. Never cut source-linking, the rules or the disclaimers.

## 14. Verification (end to end)

1. `cd app/backend && pytest`. Everything passes offline, because all network calls are mocked from fixtures.
2. With `DEMO_TODAY=2026-10-14`, `GET /api/patients/1/rules` must return:
   - `urgent_symptoms` ok;
   - `low_sugar_symptoms` flag;
   - `missed_doses` note;
   - `feet_eyes` note;
   - `hba1c_recent` ok (last value 12 Aug 2026);
   - `kidney_recent` missing (last value 21 Aug 2025);
   - `lipid_recent` missing (last value 18 Jun 2024);
   - `med_match` check (glimepiride from Jul 2024 not mentioned);
   - `unclear_readings` check (Amaryl dose).
3. The summary shows these, and nothing else is missing:
   - HbA1c values 7.2 → 7.6 → 8.3 → 8.9 %;
   - fasting glucose 142 → 160 (converted) → 176 mg/dL;
   - creatinine 1.1 and 1.2;
   - UACR 24 mg/g;
   - LDL 128;
   - metformin 500 mg 1-0-1 confirmed;
   - glimepiride with its dose uncertain.
   This matches the simulation's `EX`, which has 14 items.
4. In the browser, run the demo script from `docs/06-roadmap-and-demo.md`:
   - a Hindi kiosk run;
   - upload a report;
   - the shaky or sweaty answer raises a flag;
   - the dashboard shows the trend, the missing kidney test and the medicines;
   - clicking a value shows its source region.
5. Run `grep -ri "nvapi-" app/ data/ eval/` from the repo root. It must find nothing outside `.env`.
6. Read every screen once and check that no text gives medical advice or a diagnosis.

## 15. Known risks for the builder

| Risk | What to do |
|---|---|
| Nemotron Parse response shape differs from this plan | Phase 0 records the real response first. Adapt `parse.py` to that shape and update this file. |
| Parse reads handwriting badly | The vision-LLM fallback (step 7.6). Mark those values `unverified` unless they are text-matched. |
| 429 rate limit during the demo | Use the cache and `mode=cached` seeding. Warm the cache by seeding in live mode once before presenting. |
| Image too large for the API | The compression in `nvidia_client.py`. Log the byte size of every request. |
| ASR Hindi accuracy or gRPC setup fails | Use the Web Speech API, then typing. Voice is optional. |
| An agent "helpfully" adds advice text or LLM-decided flags | Not allowed. See the hard rules in section 1. |
