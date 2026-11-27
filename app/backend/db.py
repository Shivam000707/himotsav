"""SQLite engine and session helper."""
from __future__ import annotations

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from config import DB_PATH

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False},
)

# Columns added after the first version of the schema. create_all() does not add columns to a
# table that already exists, so an older medikiosk.db gets them here instead.
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "document": {
        "source_mode": "VARCHAR NOT NULL DEFAULT 'ai'",
        "original_filename": "VARCHAR",
    },
}


def _add_missing_columns(target_engine) -> None:
    inspector = inspect(target_engine)
    with target_engine.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            if not inspector.has_table(table):
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db(target_engine=None) -> None:
    target_engine = target_engine or engine
    SQLModel.metadata.create_all(target_engine)
    _add_missing_columns(target_engine)


def get_session():
    with Session(engine) as session:
        yield session
