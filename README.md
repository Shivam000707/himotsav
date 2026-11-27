# MediKiosk-DM

AI-assisted clinical intake for Type 2 diabetes follow-up OPDs in India.

> Before the doctor says hello, the patient's story and papers are already organised.

**Team:** Team Mayhem (Swami Rama Himalayan University) · **Team leader:** Rohit Negi · **Members:** Vaishnavi Bijalwan, Nayan, Shivam Thapliyal, Vasavi · **Event:** Himovation 2026: Solve-a-Thon, Swami Rama Himalayan University (screening submission 14 Oct 2026, final presentation 28 Oct 2026)

## The problem in one paragraph

Type 2 diabetes is lifelong, so patients return to clinics again and again, often to different doctors and labs. Their prescriptions and reports are scattered across bags and formats, and the doctor has only minutes to piece the history together. In a study of chronic-disease outpatients in Kerala and Himachal Pradesh, only 24% of the documents patients received at clinics held diagnosis, medication, long-term care and follow-up information. See [docs/01-problem-and-evidence.md](docs/01-problem-and-evidence.md).

## The idea in one paragraph

While the patient waits, a self-service screen asks about their diabetes history in their own language and reads photos of their old reports. The system builds a timeline of results and medicines, flags urgent symptoms and missing tests using fixed rules, and gives the doctor an editable one-page summary in which every value links back to the original report.

**MediKiosk-DM supports documentation and clinical review only. It never diagnoses, changes medicines or recommends treatment.**

## Documentation

| Doc | What it covers |
|---|---|
| [01 Problem and evidence](docs/01-problem-and-evidence.md) | The problem, the persona, and the verified numbers behind it |
| [02 Solution and scope](docs/02-solution-and-scope.md) | The five features, what we will not do, and the hackathon scope |
| [03 Architecture](docs/03-architecture.md) | System flow, components, data model, rules and the open-source stack |
| [04 Evaluation plan](docs/04-evaluation-plan.md) | The two experiments that give us measured results |
| [05 Safety, privacy and ethics](docs/05-safety-privacy-ethics.md) | Boundaries, data handling and known risks |
| [06 Roadmap and demo](docs/06-roadmap-and-demo.md) | Plan to 28 Oct, demo script, and open items |
| [07 References](docs/07-references.md) | Every source, and how far we verified it |
| [Build plan](BUILD_PLAN.md) | How the working version is built: stack, pipeline, rules, phases and checks |

## Status

A working version is built: the kiosk, the NVIDIA extraction pipeline, the rule engine and the doctor dashboard. It runs on a laptop with free tools only. The backend has 36 automated tests, all passing offline.

**Not measured yet:** the extraction accuracy run (`eval/`) needs an NVIDIA API key, and the clinician time study needs reviewers. Until both have numbers, do not claim accuracy or time saved.

## How to run

You need Python 3.11 or newer, Node.js 18 or newer, and a free NVIDIA API key.

### 1. Get a free NVIDIA key

Sign in at [build.nvidia.com](https://build.nvidia.com), open any model page and click **Get API Key**. The key starts with `nvapi-`. The free tier is a trial for testing, limited to about 40 requests a minute.

### 2. Backend (terminal 1)

Windows (Git Bash or PowerShell):

```bash
cd app/backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
cp .env.example .env          # then open .env and paste your key after NVIDIA_API_KEY=
.venv/Scripts/python scripts/spike_parse.py      # checks the key and every model: run this first
.venv/Scripts/python -m uvicorn main:app --port 8000
```

On macOS or Linux, use `.venv/bin/python` instead of `.venv/Scripts/python`.

`.env` holds your key and is git-ignored. Never commit it.

### 3. Frontend (terminal 2)

```bash
cd app/frontend
npm install
npm run dev
```

Open <http://localhost:5173>.

### 4. Try it

- **Load and read with NVIDIA AI** on the home page reads Ramesh ji's 7 synthetic papers with the real pipeline. The first run makes about 14 NVIDIA calls and can take up to 2 minutes. Every reply is saved in `data/cache/`, so later runs are instant and also work offline through **Saved AI replies only**.
- **Backup without AI** loads the same patient from the answer key, with no AI and no key needed. The dashboard labels it as offline demo data. Use it only if the internet or the key fails during a presentation.
- **Patient kiosk** runs the Hindi or English intake and accepts photos or PDFs of reports.
- On the doctor dashboard, every **Source** button opens the original paper with the exact region highlighted.

### Tests and the accuracy experiment

```bash
cd app/backend
.venv/Scripts/python -m pytest                          # 36 tests, no network needed
.venv/Scripts/python ../../eval/run_extraction_eval.py  # Experiment 1: writes eval/results.md (needs the key)
```

### Optional: NVIDIA voice input

The kiosk's mic button uses the browser's speech recognition (Chrome or Edge) by default. To use NVIDIA speech-to-text instead:

1. Open the Parakeet 1.1B RNNT multilingual ASR model on build.nvidia.com.
2. Copy the function id from its API example into `NVIDIA_ASR_FUNCTION_ID` in `.env`.
3. Check it with `.venv/Scripts/python scripts/check_asr.py`.

### If something goes wrong

| Problem | Fix |
|---|---|
| Home page says "NVIDIA key: missing" | Put the key in `app/backend/.env` and restart the backend |
| Home says the backend is not reachable on the deployed site | The Railway service may be starting up: wait a minute. Also check `VITE_API_BASE` on Vercel and `CORS_ORIGINS` on Railway |
| `spike_parse.py` reports 404 or 410 for a model | NVIDIA renamed or retired it (this already happened to Nemotron Parse and Llama 3.x in 2026). The script lists the models your key can use: pick a vision-language model for `NVIDIA_PARSE_MODEL` and `NVIDIA_VISION_MODEL`, and a text model for `NVIDIA_TEXT_MODEL`, in `.env` |
| A document shows "Could not be read" | Its error message is on the dashboard under Documents. A 429 means the rate limit was hit: wait a minute and upload again |
| Rules say HbA1c is missing for Ramesh ji | `DEMO_TODAY=2026-10-14` is not set in `.env`, so the rules use the real date |
| "Cannot reach the backend" | Start the backend on port 8000 before the frontend |

## Deploy the public demo (Vercel + Railway)

The backend runs in Docker (`Dockerfile` at the repo root, `railway.json`) and the frontend is a static Vite build on Vercel. The public site is a demo: **no live NVIDIA calls, no uploads, synthetic data only**. It shows the saved AI replies for the 7 demo papers (`data/demo_cache`), so it needs no API key and nobody can spend yours.

**Railway (backend)**
1. railway.com, sign in with GitHub, New project, Deploy from GitHub repo, pick this repo. It finds `Dockerfile` and `railway.json` by itself.
2. Settings, Networking, Generate Domain. Copy the address.
3. Variables: add `CORS_ORIGINS` with your Vercel address (step 3 below). Nothing else is required: the image already sets `PUBLIC_DEMO=1`, `AUTO_SEED_DEMO=cached` and `DEMO_TODAY=2026-10-14`. **Do not add `NVIDIA_API_KEY`.**
4. Check `<railway address>/api/health`: it should say `"public_demo": true`.

**Vercel (frontend)**
1. vercel.com, Add New, Project, import this repo, set Root Directory to `app/frontend`.
2. Environment Variable `VITE_API_BASE` = the Railway address, no trailing slash. Deploy.
3. Put the Vercel address in Railway's `CORS_ORIGINS` (a comma-separated list if you have several, for example a custom domain).

The database lives on the container's disk, so it resets on every deploy or restart. `AUTO_SEED_DEMO=cached` loads Ramesh ji again at each start. Patients created at the kiosk on the public site are lost on restart. If you ever change the NVIDIA models or prompts, run `eval/run_extraction_eval.py` locally and copy the new files from `data/cache` to `data/demo_cache`, because replies are saved under a hash of the request.

Test the image on your machine: `docker build -t medikiosk-backend .` then `docker run -p 8001:8000 -e CORS_ORIGINS=http://localhost:5173 medikiosk-backend`.

## Repository layout

```
README.md
BUILD_PLAN.md          how the build is organised (for AI coding agents and the team)
docs/                  project documentation
app/backend/           FastAPI + SQLite: NVIDIA pipeline, rules, API, tests
  services/            parse, structure, extraction, normalize, rules, summary, asr
  resources/           questions.json, rules.yaml, med_map.csv, test_aliases.yaml (draft, need clinician review)
  scripts/             spike_parse.py (check NVIDIA setup), check_asr.py
app/frontend/          React + Vite: home, kiosk, doctor dashboard, source viewer
data/synthetic/        Ramesh ji's 7 synthetic papers, damaged copies, labels.json, generate.py
eval/                  run_extraction_eval.py (Experiment 1)
simulation/            scripted walkthrough of the intended experience
submission/            Himovation 2026 screening deck
```
