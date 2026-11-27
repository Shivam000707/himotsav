"""Demo seeding route: creates Ramesh ji with his 7 synthetic reports and intake answers."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from PIL import Image
from sqlmodel import Session

from config import REPO_ROOT, UPLOADS_DIR
from db import get_session
from models import Block, Document, IntakeAnswer, Medication, Observation, Page, Patient
from services.extraction import extract_page_items
from services.normalize import canonicalize_test, convert_unit, map_brand_to_generic, parse_indian_date

router = APIRouter(prefix="/api", tags=["demo"])

SYNTH_DIR = REPO_ROOT / "data" / "synthetic"


@router.post("/demo/seed")
def seed_demo(
    mode: str = Query(default="cached", pattern="^(cached|live)$"),
    session: Session = Depends(get_session),
) -> dict:
    ramesh_data = json.loads((SYNTH_DIR / "ramesh.json").read_text(encoding="utf-8"))
    p_info = ramesh_data["patient"]

    patient = Patient(
        display_name=p_info["display_name"],
        age=p_info["age"],
        language=p_info["language"],
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)

    # Seed intake answers matching simulation QA
    intake_rows = [
        ("diabetes_years", 10, "करीब दस साल से।"),
        ("current_meds", [{"name": "Glycomet", "frequency": "1-0-1"}], "ग्लाइकोमेट, सुबह और रात को एक-एक गोली।"),
        ("missed_doses", "1_2_weekly", "हाँ, हफ़्ते में दो-तीन बार रात की गोली भूल जाता हूँ।"),
        ("shaky_sweaty", {"choice": "yes", "details": "2-3 times last month, in the evening"}, "हाँ, पिछले महीने दो-तीन बार शाम को ऐसा हुआ।"),
        ("urgent_symptoms", ["none"], None),
        ("feet", ["tingling"], "पैरों में कभी-कभी झुनझुनी होती है।"),
        ("eyes", "fine", "आँखें ठीक हैं।"),
        ("anything_else", "नहीं, बस इतना ही।", "नहीं, बस इतना ही।"),
    ]
    for qid, val, raw_txt in intake_rows:
        session.add(
            IntakeAnswer(
                patient_id=patient.id,
                question_id=qid,
                value_json=json.dumps(val, ensure_ascii=False),
                raw_text=raw_txt,
                confirmed=True,
            )
        )
    session.add(
        Medication(
            patient_id=patient.id,
            source="intake",
            name_as_written="Glycomet",
            generic_name=map_brand_to_generic("Glycomet"),
            strength="500 mg",
            frequency="1-0-1",
        )
    )

    for paper in ramesh_data["papers"]:
        img_src = SYNTH_DIR / "images" / f"{paper['id']}.png"
        doc_dir = UPLOADS_DIR / str(patient.id) / paper["id"]
        doc_dir.mkdir(parents=True, exist_ok=True)
        dest_img = doc_dir / "page_1.png"
        shutil.copyfile(img_src, dest_img)

        with Image.open(dest_img) as im:
            w_px, h_px = im.size

        doc_date, date_note = parse_indian_date(paper["date"])
        doc = Document(
            patient_id=patient.id,
            kind=paper["kind"],
            source_org=paper["org"],
            doc_date=doc_date,
            file_path=str(dest_img),
            page_count=1,
            status="done",
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)

        page = Page(
            document_id=doc.id,
            page_no=1,
            image_path=str(dest_img),
            width_px=w_px,
            height_px=h_px,
        )
        session.add(page)
        session.commit()
        session.refresh(page)

        if mode == "live":
            blocks, _, obs_rows, med_rows = extract_page_items(dest_img, use_cache=True, allow_network=True)
            block_map: dict[str, int] = {}
            for b in blocks:
                db_b = Block(
                    page_id=page.id,
                    block_key=b.block_id,
                    text=b.text,
                    block_type=b.block_type,
                    xmin=b.xmin,
                    ymin=b.ymin,
                    xmax=b.xmax,
                    ymax=b.ymax,
                )
                session.add(db_b)
                session.commit()
                session.refresh(db_b)
                block_map[b.block_id] = db_b.id

            for o in obs_rows:
                session.add(
                    Observation(
                        patient_id=patient.id,
                        document_id=doc.id,
                        page_id=page.id,
                        block_id=block_map.get(o["block_id"]) if o["block_id"] else None,
                        test=o["test"],
                        label_as_written=o["label_as_written"],
                        value_raw=o["value_raw"],
                        unit_raw=o["unit_raw"],
                        value_num=o["value_num"],
                        unit_std=o["unit_std"],
                        value_std=o["value_std"],
                        converted=o["converted"],
                        obs_date=o["obs_date"] or doc_date,
                        uncertain=o["uncertain"],
                        unverified=o["unverified"],
                        note=o["note"],
                    )
                )
            for m in med_rows:
                session.add(
                    Medication(
                        patient_id=patient.id,
                        source="rx",
                        document_id=doc.id,
                        page_id=page.id,
                        block_id=block_map.get(m["block_id"]) if m["block_id"] else None,
                        name_as_written=m["name_as_written"],
                        generic_name=m["generic_name"],
                        strength=m["strength"],
                        frequency=m["frequency"],
                        rx_date=m["rx_date"] or doc_date,
                        uncertain=m["uncertain"],
                        unverified=m["unverified"],
                        note=m["note"],
                    )
                )
        else:
            # Offline cached seed using deterministic coordinates from generate.py layout
            y_start = 420 if paper["kind"] == "rx" else 420
            row_step = 95 if paper["kind"] == "rx" else 85
            for idx, row in enumerate(paper["rows"]):
                ymin = (y_start + idx * row_step) / 1754.0
                ymax = (y_start + idx * row_step + 55) / 1754.0
                db_b = Block(
                    page_id=page.id,
                    block_key=f"b{idx}",
                    text=f"{row['label']} {row['value']} {row.get('unit', '')}".strip(),
                    block_type="Text",
                    xmin=0.05,
                    ymin=ymin,
                    xmax=0.90,
                    ymax=ymax,
                )
                session.add(db_b)
                session.commit()
                session.refresh(db_b)

                if paper["kind"] == "lab":
                    test_name = canonicalize_test(row["label"])
                    conv = convert_unit(test_name, row["value"], row.get("unit"))
                    session.add(
                        Observation(
                            patient_id=patient.id,
                            document_id=doc.id,
                            page_id=page.id,
                            block_id=db_b.id,
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
                    session.add(
                        Medication(
                            patient_id=patient.id,
                            source="rx",
                            document_id=doc.id,
                            page_id=page.id,
                            block_id=db_b.id,
                            name_as_written=med_name,
                            generic_name=map_brand_to_generic(med_name),
                            strength=row.get("strength"),
                            frequency=row.get("frequency") or row.get("value"),
                            rx_date=doc_date,
                            uncertain=bool(row.get("uncertain", False)),
                            unverified=False,
                            note="Smudged dose: 1 mg or 2 mg?" if row.get("uncertain") else date_note,
                        )
                    )

    session.commit()
    return {"patient_id": patient.id, "display_name": patient.display_name, "mode": mode}
