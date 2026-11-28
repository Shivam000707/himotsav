"""Demo seeding route: creates "Ramesh ji" with his 7 synthetic reports and intake answers.

Modes:
- live:     every report is read by the real NVIDIA pipeline. Responses are cached on disk,
            so running it again later is instant and needs no network.
- cached:   same pipeline, but only from the disk cache (no network). Fails clearly for any
            report that has not been read in live mode before.
- scripted: offline backup for when there is no API key or no internet. Values come from the
            synthetic answer key (data/synthetic/ramesh.json), NOT from AI. Every document is
            marked source_mode="scripted" and the dashboard says so.
"""
from __future__ import annotations

import json
import logging
import shutil

from fastapi import APIRouter, Depends, HTTPException, Query
from PIL import Image
from sqlmodel import Session, select

from config import REPO_ROOT, UPLOADS_DIR, settings
from db import get_session
from models import Block, Document, IntakeAnswer, Medication, Observation, Page, Patient
from services.ingest import ingest_page
from services.normalize import canonicalize_test, convert_unit, map_brand_to_generic, parse_indian_date

router = APIRouter(prefix="/api", tags=["demo"])
log = logging.getLogger("medikiosk.demo")

SYNTH_DIR = REPO_ROOT / "data" / "synthetic"
DEMO_PATIENT_NAME = "Ramesh Kumar"  # display_name in data/synthetic/ramesh.json

# Intake answers matching the simulation's QA script (simulation/medikiosk-simulation.html).
DEMO_INTAKE = [
    ("diabetes_years", 10, "करीब दस साल से।"),
    ("current_meds", [{"name": "Glycomet", "frequency": "1-0-1"}], "ग्लाइकोमेट, सुबह और रात को एक-एक गोली।"),
    ("missed_doses", "1_2_weekly", "हाँ, हफ़्ते में दो-तीन बार रात की गोली भूल जाता हूँ।"),
    ("shaky_sweaty", "yes", "हाँ, पिछले महीने दो-तीन बार शाम को ऐसा हुआ।"),
    ("urgent_symptoms", ["none"], None),
    ("feet", ["tingling"], "पैरों में कभी-कभी झुनझुनी होती है।"),
    ("eyes", "fine", None),
    ("anything_else", "", "नहीं, बस इतना ही।"),
]

# Text positions used by data/synthetic/generate.py (page is 1240 x 1754 px). Used only in
# scripted mode, to draw the source box over the right line of the synthetic report.
_PAGE_W, _PAGE_H = 1240.0, 1754.0
_FIRST_ROW_Y = 420
_ROW_STEP = {"lab": 85, "rx": 95}
_ROW_X = {"lab": (70, 1110), "rx": (70, 660)}


def _scripted_bbox(kind: str, idx: int) -> tuple[float, float, float, float]:
    y = _FIRST_ROW_Y + idx * _ROW_STEP[kind]
    x0, x1 = _ROW_X[kind]
    return x0 / _PAGE_W, (y - 12) / _PAGE_H, x1 / _PAGE_W, (y + 52) / _PAGE_H


def _create_patient_with_intake(
    session: Session,
    p_info: dict,
    intake: list | None = None,
    intake_meds: list | None = None,
) -> Patient:
    """A patient with confirmed kiosk answers and the medicines they named. Defaults are Ramesh ji's."""
    patient = Patient(display_name=p_info["display_name"], age=p_info["age"], language=p_info["language"])
    session.add(patient)
    session.flush()
    for qid, val, raw_txt in intake if intake is not None else DEMO_INTAKE:
        session.add(
            IntakeAnswer(
                patient_id=patient.id,
                question_id=qid,
                value_json=json.dumps(val, ensure_ascii=False),
                raw_text=raw_txt,
                confirmed=True,
            )
        )
    for name, strength, frequency in intake_meds if intake_meds is not None else [["Glycomet", "500 mg", "1-0-1"]]:
        session.add(
            Medication(
                patient_id=patient.id,
                source="intake",
                name_as_written=name,
                generic_name=map_brand_to_generic(name),
                strength=strength,
                frequency=frequency,
            )
        )
    session.commit()
    session.refresh(patient)
    return patient


def _add_document_with_page(session: Session, patient: Patient, paper: dict, source_mode: str) -> tuple[Document, Page]:
    img_src = SYNTH_DIR / "images" / f"{paper['id']}.png"
    if not img_src.exists():
        raise HTTPException(status_code=500, detail=f"Missing synthetic image {img_src}. Run data/synthetic/generate.py.")
    doc_dir = UPLOADS_DIR / str(patient.id) / paper["id"]
    doc_dir.mkdir(parents=True, exist_ok=True)
    dest_img = doc_dir / "page_1.png"
    shutil.copyfile(img_src, dest_img)
    with Image.open(dest_img) as im:
        w_px, h_px = im.size

    doc = Document(
        patient_id=patient.id,
        file_path=str(dest_img),
        page_count=1,
        status="pending",
        source_mode=source_mode,
        original_filename=f"{paper['id']}.png",
    )
    session.add(doc)
    session.flush()
    page = Page(document_id=doc.id, page_no=1, image_path=str(dest_img), width_px=w_px, height_px=h_px)
    session.add(page)
    session.commit()
    session.refresh(doc)
    session.refresh(page)
    return doc, page


def _seed_scripted_values(session: Session, patient: Patient, doc: Document, page: Page, paper: dict) -> None:
    doc_date, date_note = parse_indian_date(paper["date"])
    doc.kind = paper["kind"]
    doc.source_org = paper["org"]
    doc.doc_date = doc_date
    for idx, row in enumerate(paper["rows"]):
        xmin, ymin, xmax, ymax = _scripted_bbox(paper["kind"], idx)
        if row.get("smudge_strength"):
            # The dose is unreadable on the printed page, so the "text found there" must not show it.
            printed = f"{row.get('med_name') or row['label']} ? mg {row['value']}"
        else:
            printed = f"{row['label']} {row['value']} {row.get('unit', '')}".strip()
        block = Block(
            page_id=page.id,
            block_key=f"b{idx}",
            text=printed,
            block_type="Text",
            xmin=xmin,
            ymin=ymin,
            xmax=xmax,
            ymax=ymax,
        )
        session.add(block)
        session.flush()
        if paper["kind"] == "lab":
            test_name = canonicalize_test(row["label"])
            conv = convert_unit(test_name, row["value"], row.get("unit"))
            session.add(
                Observation(
                    patient_id=patient.id,
                    document_id=doc.id,
                    page_id=page.id,
                    block_id=block.id,
                    test=test_name,
                    label_as_written=row["label"],
                    value_raw=row["value"],
                    unit_raw=row.get("unit"),
                    value_num=conv.value_num,
                    unit_std=conv.unit_std,
                    value_std=conv.value_std,
                    converted=conv.converted,
                    obs_date=doc_date,
                    uncertain=bool(row.get("uncertain") or conv.uncertain),
                    unverified=False,
                    note=conv.note or date_note,
                )
            )
        else:
            med_name = row.get("med_name") or row["label"]
            uncertain = bool(row.get("uncertain", False))
            session.add(
                Medication(
                    patient_id=patient.id,
                    source="rx",
                    document_id=doc.id,
                    page_id=page.id,
                    block_id=block.id,
                    name_as_written=med_name,
                    generic_name=map_brand_to_generic(med_name),
                    # The smudged dose is not readable on the paper, so it is not stated here either.
                    strength="? mg" if row.get("smudge_strength") else row.get("strength"),
                    frequency=row.get("frequency") or row.get("value"),
                    rx_date=doc_date,
                    uncertain=uncertain,
                    unverified=False,
                    note="Dose smudged on the paper: looks like 1 mg or 2 mg" if uncertain else date_note,
                )
            )
    doc.status = "done"
    session.add(doc)
    session.commit()


def seed_demo_patient(session: Session, mode: str) -> dict:
    """Create Ramesh ji with his 7 synthetic papers. Used by the route and by the startup auto-seed."""
    ramesh_data = json.loads((SYNTH_DIR / "ramesh.json").read_text(encoding="utf-8"))
    patient = _create_patient_with_intake(session, ramesh_data["patient"])
    source_mode = "scripted" if mode == "scripted" else "ai"

    failed: list[dict[str, str]] = []
    for paper in ramesh_data["papers"]:
        doc, page = _add_document_with_page(session, patient, paper, source_mode)
        if mode == "scripted":
            _seed_scripted_values(session, patient, doc, page, paper)
            continue
        try:
            ingest_page(session, patient_id=patient.id, doc=doc, page=page, use_cache=True, allow_network=(mode == "live"))
            doc.status = "done"
            session.add(doc)
            session.commit()
        except Exception as exc:
            log.exception("Demo extraction failed for %s", paper["id"])
            session.rollback()
            doc = session.get(Document, doc.id)
            doc.status = "failed"
            doc.error = str(exc)[:1000]
            session.add(doc)
            session.commit()
            failed.append({"paper": paper["id"], "error": str(exc)[:300]})

    return {
        "patient_id": patient.id,
        "display_name": patient.display_name,
        "mode": mode,
        "documents_total": len(ramesh_data["papers"]),
        "documents_failed": failed,
    }


def seed_personas(session: Session) -> list[dict]:
    """Two more made-up patients with different trajectories, from data/synthetic/personas.json.
    Always backup (scripted) values, labelled as such on the dashboard. Safe to call twice."""
    path = SYNTH_DIR / "personas.json"
    if not path.exists():
        return []
    created: list[dict] = []
    for persona in json.loads(path.read_text(encoding="utf-8"))["personas"]:
        name = persona["patient"]["display_name"]
        existing = session.exec(select(Patient).where(Patient.display_name == name)).first()
        if existing is not None:
            created.append({"patient_id": existing.id, "display_name": name, "trajectory": persona["trajectory"], "created": False})
            continue
        patient = _create_patient_with_intake(session, persona["patient"], persona["intake"], persona["intake_meds"])
        for paper in persona["papers"]:
            doc, page = _add_document_with_page(session, patient, paper, "scripted")
            _seed_scripted_values(session, patient, doc, page, paper)
        created.append({"patient_id": patient.id, "display_name": name, "trajectory": persona["trajectory"], "created": True})
    return created


@router.post("/demo/seed-personas")
def seed_demo_personas(session: Session = Depends(get_session)) -> list[dict]:
    return seed_personas(session)


@router.post("/demo/seed")
def seed_demo(
    mode: str = Query(default="live", pattern="^(live|cached|scripted)$"),
    session: Session = Depends(get_session),
) -> dict:
    if mode == "live" and settings.public_demo:
        raise HTTPException(
            status_code=403,
            detail="Live reading is switched off on the public demo. Use the saved AI replies instead.",
        )
    if mode == "live" and not settings.nvidia_key_present:
        raise HTTPException(
            status_code=400,
            detail="NVIDIA_API_KEY is not set in app/backend/.env. Add it and restart the backend, or use the offline scripted demo.",
        )
    if settings.public_demo:
        # Anyone can press the button: hand back the existing demo patient instead of adding a copy each time.
        existing = session.exec(select(Patient).where(Patient.display_name == DEMO_PATIENT_NAME)).first()
        if existing is not None:
            return {
                "patient_id": existing.id,
                "display_name": existing.display_name,
                "mode": mode,
                "documents_total": len(session.exec(select(Document).where(Document.patient_id == existing.id)).all()),
                "documents_failed": [],
            }
    return seed_demo_patient(session, mode)
