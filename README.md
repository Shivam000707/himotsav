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

## Status

Idea and screening stage. No code yet. The screening deck is done, and the build starts after screening (see the roadmap).

## Repository layout

```
README.md
docs/            project documentation (this index)
```

Code folders (`app/`, `data/`, `eval/`) will be added when the build starts.
