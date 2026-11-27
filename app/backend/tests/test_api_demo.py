from datetime import date
from sqlmodel import Session, SQLModel, create_engine

import db
from routers import demo, doctor


def test_demo_seed_cached_and_summary(tmp_path):
    test_db = tmp_path / "test.db"
    test_engine = create_engine(f"sqlite:///{test_db}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(test_engine)

    with Session(test_engine) as session:
        seed = demo.seed_demo(mode="cached", session=session)
        assert seed["patient_id"] is not None
        pid = seed["patient_id"]

        rules_list = doctor.get_rules(pid, session=session)
        rules = {r["rule_id"]: r["status"] for r in rules_list}
        assert rules == {
            "urgent_symptoms": "ok",
            "low_sugar_symptoms": "flag",
            "missed_doses": "note",
            "feet_eyes": "note",
            "hba1c_recent": "ok",
            "kidney_recent": "missing",
            "lipid_recent": "missing",
            "med_match": "check",
            "unclear_readings": "check",
        }

        summary = doctor.get_summary(pid, session=session)
        assert summary["disclaimer"] == "Documentation aid only. Not a diagnosis or treatment advice."
        assert len(summary["latest_results"]) >= 4
        assert len(summary["medications"]) >= 2
        assert len(summary["rules"]) == 9
