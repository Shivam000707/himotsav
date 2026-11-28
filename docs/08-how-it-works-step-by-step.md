# MediKiosk-DM: how it works, step by step

Written 27 Nov 2026 from the running code. Every number, threshold and rule below is taken from the code, not from the plan. Where something is untested or a known weakness, it says so.

---

## 1. In one paragraph

A Type 2 diabetes patient waits for a follow-up visit. A kiosk asks them 8 fixed questions in Hindi or English and lets them photograph their old lab reports and prescriptions. AI reads the photos. Plain code then converts units, matches medicine names, compares what the patient said against what the papers say, and checks nine documentation rules. The doctor gets one page: what needs attention, how the numbers moved, which medicines, and what the patient said. **Every value on that page opens the original paper with the exact line highlighted**, so the doctor can check the AI in one click.

It never diagnoses, never suggests or changes a medicine, and never gives treatment advice. It uses synthetic (made-up) data only.

---

## 2. The two people who use it, and the four screens

| Who | Screen | Address | What they do |
|---|---|---|---|
| Patient | **Kiosk** | `/kiosk` | Answers questions, adds photos of old papers |
| Doctor or staff | **Doctor's desk, list** | `/doctor` | Sees every patient who used the kiosk |
| Doctor | **Doctor's desk, summary** | `/doctor/<id>` | Reads the one-page summary, opens sources, corrects values, writes notes, prints |
| Anyone | **Home** | `/` | Starts the kiosk or the desk, loads the demo patient, shows a system check |

The patient never sees the doctor's flags or any medical interpretation. Only the doctor's pages show them.

---

## 3. The patient's journey at the kiosk

### Step 1. Choose a language
Two large tiles: **हिन्दी** and **English**. The whole kiosk, including every question, switches to that language.

### Step 2. A notice, then name and age
- A notice says this is a demo, to use made-up details only, that the doctor will see the answers, and that the kiosk gives no medical advice.
- **Name** is optional. If left empty it becomes "Patient (demo)" or "मरीज़ (डेमो)".
- **Age** is required, a whole number from 1 to 120. Otherwise the screen shows an error and does not continue.
- On "Continue" the app creates the patient record and loads the question list.

### Step 3. Eight questions, one at a time
A progress bar shows 9 segments: 8 questions and the final upload step. Back and Next stay fixed at the bottom of the screen.

| # | Question (English) | Answer type |
|---|---|---|
| 1 | How many years have you had sugar (diabetes)? | A number, with − and + buttons |
| 2 | Which medicines do you take these days? | Tick any of 12 brands, or "I don't know". Each ticked medicine then asks *when* (morning and night, morning only, night only, 3 times a day, afternoon only) |
| 3 | Do you ever forget to take your medicine? | Never / less than once a week / 1-2 times a week / 3 or more times a week |
| 4 | Do you ever suddenly feel shaky, sweaty or uneasy? | Yes / No |
| 5 | Have you had any of these symptoms recently? | Chest pain, fainting, severe breathlessness, or none (tick any) |
| 6 | Any wound, numbness or tingling in your feet? | Non-healing wound, numbness, tingling, or none (tick any) |
| 7 | Any trouble with your vision? | Fine / blurry / sudden vision loss |
| 8 | Anything else you would like to tell the doctor today? | Free text, optional |

The 12 medicine brands in question 2 are: Glycomet, Glycomet GP, Amaryl, Janumet, Januvia, Galvus Met, Jardiance, Forxiga, Lantus, Telma, Atorva, Rosuvas.

Questions 1 to 7 also have an optional "Anything to add?" box, where the patient can type or **speak** (see step 4).

### Step 3b. Every answer is confirmed
After "Next", the kiosk shows a slip titled "Did we understand you?" with the question and the answer **written back in a handwriting font**, plus any extra words. The patient taps **Yes, correct** or **Change**.

An answer is saved to the database **only after "Yes, correct"** and is stored as confirmed. The next question appears only after that. Back works at any time.

### Step 4. Voice (optional, in the "Anything to add?" box)
The mic button tries, in order:
1. **NVIDIA speech-to-text** (Parakeet), if `NVIDIA_ASR_FUNCTION_ID` is set on the server.
2. **The browser's own speech recognition** (Chrome or Edge), in Hindi (`hi-IN`) or English (`en-IN`).
3. **Nothing**: the button disappears and the patient types.

Recognised words only fill the text box. The patient still sees and confirms them in step 3b. **Status: the NVIDIA path is untested against the real service** (the function id was not available). The browser path is the one that works today.

### Step 5. Upload old reports and prescriptions
The patient takes a photo or picks a file: JPG, PNG, WebP or PDF, up to 10 MB, up to 5 pages per file. Each file shows a row: reading, then "Read N values", "Nothing found, staff will check", or "Could not read, staff will check". Files are read **one at a time** because the free NVIDIA tier is rate limited. If the patient has no papers they just press Finish.

### Step 6. Done
"Thank you. Please wait to be called." No advice. Two staff links: open this patient's summary, or start the kiosk for the next patient.

---

## 4. What happens to every uploaded paper

This is the AI part. It runs on the server, when a file is uploaded.

### Step 1. Check the file
Type must be JPG, PNG, WebP or PDF. It must not be empty or over 10 MB. A PDF is turned into page images (at most 5 pages). Phone-photo rotation is corrected. A bad file is refused with a message saying why.

### Step 2. Save the original
The file and its page images are stored under `data/uploads/<patient>/<document>/`. A record is created with status "pending". Page images are kept at full size for display.

### Step 3. Shrink a copy for the AI
The AI service accepts only small inline images. A copy is made with the long side at most 1600 pixels, re-saved as JPEG at the highest quality that fits **under 170 KB**.

### Step 4. The AI reads the page (AI use #1)
Model: **`nvidia/nemotron-3.5-super-vl-120b-a12b`**, a vision-language model. It is asked to transcribe the page and return a list, in reading order, of `{text, bbox}`:
- one item per printed or written line;
- a table row is joined into one item, for example `"HbA1c 7.6 %"`;
- `bbox` is the line's box on a **0 to 1000** scale across the image;
- an unreadable character must be written as `?`;
- it must not correct, interpret or add anything.

Boxes are converted to fractions of the page. Items with no text or no usable box are dropped, never guessed. The model is run with thinking switched off and temperature 0.

The box is the model's own estimate. I checked it by drawing the boxes on a real page: they sit correctly on the text.

### Step 5. Fallback if the reading was poor
- If the model returns **fewer than 3 lines**, the page image is sent to the vision model again and asked to produce the structured result directly (step 6's format).
- If the page is a prescription but **no medicines** were found, the same fallback is tried, and it is used only if it finds medicines.
- Values from this fallback have no line to point at. They are marked **unverified** unless step 7 can match them to a line.

### Step 6. The AI turns lines into fields (AI use #2)
Model: **`nvidia/nemotron-3.5-lightning-30b-a3b`**, a text model, temperature 0. It receives the lines with ids (`b0`, `b1`, ...) and must return JSON:
- `kind`: lab or prescription;
- `source_org` and `doc_date` (and the line the date came from);
- for each test: label, value, unit, **the id of the line it came from**, an `uncertain` flag and a note;
- for each medicine: name, strength, frequency, line id, `uncertain`, note.

Its instructions say: copy values exactly as written; convert nothing; correct nothing; if a character is unclear set `uncertain` and explain; **leave out anything you cannot point to a line for**; add no interpretation. Only these tests are extracted: HbA1c, fasting / post-meal / random glucose, creatinine, eGFR, urine albumin-creatinine ratio, total cholesterol, LDL, HDL, triglycerides, plus every medicine on a prescription.

The reply is validated. If it is malformed, the model is asked **once more** with the error. If it still fails, the document is marked **failed** and the error is saved, but the document stays so a person can look at it.

### Step 7. Grounding check (plain code, the anti-invention defence)
Each extracted value must actually appear in the text of the line it points at.
- **Numbers must match as whole numbers.** "24" is not accepted inside "2024" or "1.24".
- Words use a fuzzy match of at least 90 out of 100.
- If the claimed line contains the value: accepted.
- If not, but **exactly one** other line contains it: the value is re-pointed to that line.
- If no line, or more than one line, contains it: the value is marked **unverified** and has no highlight.

### Step 8. Normalise (plain code)
- **Test names.** Variants are mapped to one canonical name using a list (`HbA1c`, `A1c`, `Glycated Hb`, `FBS`, `Fasting Blood Sugar`, `UACR`, ...), with a fuzzy match of at least 90. An unknown test is kept as "other".
- **Units.** Everything is converted to one standard unit, and **the original value and unit are always kept**:

| Test | From | To | Rule |
|---|---|---|---|
| Glucose (fasting, post-meal, random) | mmol/L | mg/dL | × 18.016, rounded (8.9 becomes 160) |
| HbA1c | mmol/mol | % | 0.09148 × value + 2.152, one decimal |
| Creatinine | µmol/L | mg/dL | ÷ 88.4, two decimals |
| Total, LDL, HDL cholesterol | mmol/L | mg/dL | × 38.67, rounded |
| Triglycerides | mmol/L | mg/dL | × 88.57, rounded |
| Urine albumin/creatinine | mg/mmol | mg/g | × 8.84, rounded |

  A converted value is flagged `converted`. If the unit is missing or unknown, the raw value is kept, marked unsure, with the note "unit not readable".
- **Dates.** Indian reports are day first. "09/07/2024" is read as 9 July. If the day and month could swap, the date is kept day first and the note "date order assumed DD/MM" is added. A date missing its day, month or year is "date not readable".
- **Medicines.** The brand is matched to its generic name (Glycomet to metformin, Amaryl to glimepiride, Telma to telmisartan, and so on, from a 13-row list), ignoring "Tab.", "Cap." and strengths, with a fuzzy match of at least 88. **A brand that does not match stays unmapped**, so "Amaryl M" is never silently turned into glimepiride. The name as written is always kept. The list is a draft that needs clinician review.

### Step 9. Second reading (AI use #3, then plain code compares)
A different model, **`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`**, re-reads **each line that holds a value** from a zoomed, enlarged crop of that line. It only transcribes. Plain code then compares the numbers:
- a test value that does not appear in the second reading, or a medicine dose or timing (such as `1-0-1`) that differs, is **marked unsure** and the note shows what the second reader saw;
- a value is **never changed**, only marked, so the doctor sees both readings and rule 9 lists it;
- if the second reader is unavailable, the check is skipped and nothing is marked (it never fails an upload);
- one call per line, so a page with two values on two lines costs two extra calls.

Why: on a real handwritten note the first reader read "RBS 50 mg/dl" as **10** and reported it as clear. The grounding check in step 7 could not catch it, because 10 really was in the line the model wrote. The second reader read 50, so the disagreement is now flagged. This is one note, not a proof of reliability. It cannot catch an error **both** readers share.

### Step 10. Save
Test results and medicines are saved, each with its document, page and box. The document becomes "done". The kiosk shows the count.

### Saved replies (cache)
Every reply from the AI service is saved to disk under a hash of the request. Running the same page again costs nothing and works offline. Replies for the 7 demo papers are also shipped with the project (`data/demo_cache`).

---

## 5. The nine rules (plain code, no AI)

The doctor's "Needs attention" list comes from these rules. The AI never decides what is urgent. Thresholds are in `app/backend/resources/rules.yaml` and are **drafts from general knowledge that a doctor must review**.

"Today" is the real date, or the date in `DEMO_TODAY` (14 Oct 2026 for the demo).

| # | Rule | Looks at | Result |
|---|---|---|---|
| 1 | **Urgent symptoms** | Chest pain, fainting or severe breathlessness ticked; or sudden vision loss; or an urgent word in any free text (chest pain, faint, breathless, in English, Hindi script or romanised Hindi) | Flag if found, otherwise OK |
| 2 | **Possible low-sugar symptoms** | "Shaky or sweaty" answered Yes; or a word like shaky, sweaty, trembling, dizzy, confused, काँपना, पसीना, चक्कर in free text | Flag if found, otherwise OK |
| 3 | **Missed doses** | Forgets medicine 1-2 times a week or more | Note if so, otherwise OK |
| 4 | **Feet and eyes** | Non-healing wound or sudden vision loss: **flag**. Numbness, tingling or blurry vision: **note**. Otherwise OK | Flag, note or OK |
| 5 | **HbA1c up to date** | Latest HbA1c within **90 days** | OK, or missing (with the last date) |
| 6 | **Kidney test up to date** | Latest creatinine, eGFR or urine albumin test within **365 days** | OK, or missing |
| 7 | **Cholesterol test up to date** | Latest LDL, total cholesterol, HDL or triglycerides within **365 days** | OK, or missing |
| 8 | **Medicine match** | Every medicine on a prescription from the last **30 months** should be among the medicines the patient named today. Also reports a medicine the patient named that is on no prescription | "To confirm" with each mismatch, otherwise OK |
| 9 | **Unclear readings** | Any value or medicine that is unsure or unverified and not yet checked by the doctor | "To confirm", otherwise OK |

Statuses shown to the doctor: **Doctor to review** (flag), **Missing**, **To confirm**, **Note**, **Nothing to report** (OK).

For the demo patient (Ramesh ji) the expected and measured result is: urgent symptoms OK; low-sugar symptoms flag; missed doses note; feet and eyes note; HbA1c OK (12 Aug 2026); kidney test missing (21 Aug 2025); cholesterol test missing (18 Jun 2024); medicine match to confirm (Amaryl not mentioned); unclear readings to confirm (Amaryl dose).

---

## 6. What the doctor sees

### The patient list (`/doctor`)
Every patient who used the kiosk, with age, language and check-in date. An empty list explains how to load the demo patient.

### The summary (`/doctor/<id>`), top to bottom

1. **Header.** Name, age, kiosk language, the date the rules were checked, the disclaimer, and a **Print this page** button.
2. **Banners**, only if needed: "Offline demo data" (values came from the answer key, not AI), or "N papers could not be read".
3. **Needs attention.** The rules from section 5 that are not OK, with their evidence. Highlighted chips (for example "HbA1c 8.9 %") open the source paper. Rules with nothing to report are in a collapsed list.
4. **Trends.** HbA1c and fasting glucose over time. Each point shows its value and opens its paper when clicked. A converted value is a hollow point. A note appears when two HbA1c readings are more than a year apart ("No HbA1c in the papers from Jun 2024 to Aug 2026").
5. **Latest results.** The newest value of each test, with date and lab. The value is the highlighted button. Notes show "Converted from 8.9 mmol/L", "Unsure reading", "No exact source" or "Checked by doctor".
6. **Medicines.** Each medicine from the prescriptions, generic name first with the brand in brackets, plus a status: **Confirmed today**, **Not mentioned today**, **Dose unclear**, or **No prescription found** (named by the patient, on no paper).
7. **Papers.** Every uploaded document, its type, date, how many results and medicines were read, and any error.
8. **What the patient said** (right-hand column). Each confirmed answer, with the patient's own words in handwriting. Unanswered questions are listed.
9. **Your notes** (right-hand column). A text box that **saves itself** about half a second after typing stops.

### Tracking over time (added 27 Nov 2026)
All of this is plain code on the saved records. None of it is AI, and none of it diagnoses or advises.

- **Trends for every test**, not only HbA1c and glucose: each test with dated numbers gets a chart on a true date axis. Points open their paper. Under each chart: the change since the previous result and a straight-line rate of change per year (only when there are at least 2 results spanning 60 days or more).
- **Medicine events on the timeline.** From the dated prescriptions the app lists, and draws as dashed lines on the charts: *first prescription seen*, *dose or timing differs from the previous prescription*, and *not on a later prescription*. Unsure doses never create a "changed" event. The page says this shows the order of events only and does not show that a medicine caused any change.
- **Monitoring plan, set by the doctor.** For each test the doctor can type a target range, a **review margin** and a **repeat interval**. Nothing is pre-filled or suggested, and a blank field means none is set.
  - A target range is drawn as a shaded band on the chart. It never raises a flag by itself.
  - A repeat interval replaces the draft default (90 / 365 / 365 days) in the matching "up to date" rule for that patient, and the evidence says "interval set by the doctor".
  - A review margin turns on one extra rule, **change from own baseline**: the latest value is compared with the patient's own average over the previous 12 months (at least 2 earlier results needed). If it is further away than the margin, the doctor sees "HbA1c is 1.43 above this patient's own average of 6.97 ... the doctor set the review margin at 1".
- **Test schedule.** A table of Last done, Repeat, Next due and a status: Completed, Due (within 14 days of the due date), Overdue, No record, or Interval not set.
- **Three demo patients with different trajectories** (all made up, backup values, labelled as such): Ramesh ji (slow rise with a long gap), Mohan Lal (HbA1c rises through 2025, a second medicine is added in Oct 2025, then it falls), and Kavita Sharma (steady for a year, then a jump in Aug 2026 that the baseline check catches once a margin is set).

Not built: repeated kiosk visits for the same patient (each kiosk session still creates a new patient), blood pressure and cardiovascular history, eye or foot screening records, a patient-facing progress view, and CGM data.

### Opening a source
Clicking any highlighted value opens a panel with:
- the value, and what was printed on the paper if it was converted;
- a zoomed crop with the line highlighted, and the exact text found there;
- the whole page with the same line highlighted;
- warnings if the AI marked the value unsure or could not find an exact place.

The doctor can then:
- press **This matches the paper**, which marks it checked, or
- **type the correct value** and save. The doctor's value is shown everywhere, the AI's original reading is kept and shown ("Corrected by the doctor. The AI read ..."), and the value is marked checked.

Once a value is checked, it no longer counts as an unclear reading in rule 9.

### Printing
The print layout drops the buttons and panels and fits the summary on one page, with the disclaimer at the bottom.

---

## 7. Where AI is used, and where it is not

| Job | Done by | Model |
|---|---|---|
| Read a page photo into lines and positions | **AI** | `nvidia/nemotron-3.5-super-vl-120b-a12b` |
| Turn lines into test values and medicines | **AI** | `nvidia/nemotron-3.5-lightning-30b-a3b` |
| Fallback: read the image straight into fields | **AI** | `nvidia/nemotron-3.5-super-vl-120b-a12b` |
| Second reading of each value line, from a zoomed crop | **AI** | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` |
| Compare the two readings and mark disagreements unsure | Plain code | none |
| Voice to text | **AI** (optional) | Parakeet 1.1B multilingual, or the browser |
| Check a value really appears on the page | Plain code | none |
| Names, units, dates, medicine brands | Plain code | none |
| The nine rules and every flag | Plain code | none |
| Trends, summary, "needs attention" order | Plain code | none |

No OCR engine is used. NVIDIA retired its dedicated parsing model (Nemotron Parse) and the Llama models in Nov 2026 (the service answers "Gone"), which is why the page reader is now a general vision-language model.

The AI service is NVIDIA's free hosted developer API: roughly 40 requests a minute, intended for trials and testing. A page takes about 4 to 6 seconds.

---

## 8. The safety design, in one list

1. **AI reads, code decides.** AI never judges urgency or interprets results.
2. **No value without a source.** Every value stores its document, page and box. A value with no matching line is shown as *unverified*.
3. **Uncertain stays uncertain.** An unreadable character is written `?`, the value is marked unsure, and rule 9 puts it in front of the doctor.
4. **The doctor can check and correct in one click**, and the original reading is never erased.
5. **The patient confirms every answer** before it is saved.
6. **No advice anywhere.** Every screen carries "Documentation aid only. Not a diagnosis or treatment advice."
7. **Synthetic data only.** The patient sees none of the flags.
8. **The API key stays on the server** in a git-ignored file and never reaches the browser.

---

## 9. Demo modes

On the home page, three ways to load the demo patient **Ramesh ji** (58, Hindi, 7 papers from 3 labs and 2 clinics, one lab in mmol/L, one smudged dose):

| Mode | What it does | Needs |
|---|---|---|
| **Read with NVIDIA AI** (live) | The AI really reads the 7 papers and saves the replies | API key, internet |
| **Saved AI replies** (cached) | Same pipeline, but only from saved replies | Nothing |
| **Backup values** (scripted) | Fills the values from the synthetic answer key, **not AI**. Every screen is labelled "Offline demo data" | Nothing |

In every mode his 8 kiosk answers are pre-filled and the nine rules run on the result.

---

## 10. The public demo (Vercel and Railway)

The backend runs as a Docker container (Railway) and the frontend as a static site (Vercel). The public site has no API key and:
- shows the saved AI replies (works with no key);
- has live reading and uploads switched off;
- loads Ramesh ji at every start (the disk resets on every restart);
- keeps the demo patient to one copy.

The kiosk still works, so a visitor can answer the questions and see them on the doctor's desk.

---

## 11. What is stored

SQLite database plus image files on disk:

| Table | Holds |
|---|---|
| Patient | name, age, language |
| Document, Page | each upload, its pages, status, error |
| Block | each line the AI read, with its box |
| Observation | each test result: raw and standard value, converted?, date, unsure?, unverified?, checked by doctor?, doctor's correction |
| Medication | each medicine from a prescription or from the patient: name as written, generic, strength, frequency |
| IntakeAnswer | each confirmed kiosk answer, with the patient's own words |
| DoctorNote | the doctor's note |

Rule results and the summary are **computed fresh each time they are requested**, never stored.

---

## 12. What is proven, and what is not

**Measured**
- On 14 synthetic images (7 papers, each clean and damaged by blur, rotation, darkening and heavy JPEG): **64 of 64 fields correct** (dates, values, units, medicines), and **every value tied to a box on the page**.
- The demo patient, read live by the AI, produced exactly the expected nine rule results.
- 43 automated tests pass. The deployment container was built and tested locally.

**Not proven, say so openly**
- **Small and synthetic.** 7 made-up papers for one made-up patient. This shows direction, not general accuracy, and says nothing about real handwriting or real lab layouts.
- **A faint smudge can still be guessed.** On the clean synthetic prescription the AI wrote "? mg" and flagged it. On the damaged copy a faint ghost of a digit remains and **both readers read it as "1 mg"**, so the second reading agrees and nothing is flagged. The second reading catches readers that disagree (it caught a real 10-versus-50 misread on a handwritten note). It cannot catch a mistake both readers make.
- **Real handwriting is much harder than the synthetic set.** On a real handwritten hospital note the first reader misread several words and one number; only the number disagreement is caught automatically. Names and ordinary words can still be wrong, which is why every value links to its paper.
- **Voice through NVIDIA is untested.** Only the browser fallback is known to work.
- **Rule thresholds are drafts.** They have not been reviewed by a doctor.
- **No clinical validation or pilot** has been done, and no real patient data has ever been used.
- **No login.** Anyone with the link can open the doctor's pages, which is acceptable only because the data is synthetic.
- **The AI models change.** NVIDIA retired three of the original models during this project. The setup script (`scripts/spike_parse.py`) tells you when one is gone and lists the replacements.

---

## 13. Quick reference

| I want to... | Do this |
|---|---|
| Check the AI setup | `cd app/backend`, then `.venv\Scripts\python scripts\spike_parse.py` |
| Measure accuracy | `.venv\Scripts\python ..\..\eval\run_extraction_eval.py` (writes `eval/results.md`) |
| Run the tests | `.venv\Scripts\python -m pytest` (in `app/backend`) |
| Start the backend | `.venv\Scripts\python -m uvicorn main:app --port 8000 --reload` |
| Start the frontend | `npm run dev` in `app/frontend`, open http://localhost:5173 |
| Add the key | `app/backend/.env`, line `NVIDIA_API_KEY=`, then restart the backend |
| Deploy the public demo | See the README, section "Deploy the public demo" |
