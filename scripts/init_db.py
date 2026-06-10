from __future__ import annotations

import csv
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "oligosafety.db"
SCHEMA_PATH = DATA_DIR / "schema_sqlite.sql"
SEED_DIR = DATA_DIR / "seed"
GENERATED_SOURCE_CSV = DATA_DIR / "generated" / "source_document_pubmed_v1.csv"
GENERATED_QUEUE_CSV = DATA_DIR / "generated" / "curation_queue_v1.csv"
GENERATED_CANDIDATE_CSV = DATA_DIR / "generated" / "curation_candidate_v1.csv"

LOAD_PLAN = [
    ("source_document", SEED_DIR / "source_document.csv"),
    ("source_document", GENERATED_SOURCE_CSV),
    ("modality", SEED_DIR / "modality.csv"),
    ("molecule", SEED_DIR / "molecule.csv"),
    ("assay", SEED_DIR / "assay.csv"),
    ("curation_audit", SEED_DIR / "curation_audit.csv"),
    ("benchmark_split", SEED_DIR / "benchmark_split.csv"),
    ("curation_queue", GENERATED_QUEUE_CSV),
    ("curation_candidate", GENERATED_CANDIDATE_CSV),
]


def coerce_value(value: str) -> object:
    if value == "":
        return None
    return value


def load_csv_path(conn: sqlite3.Connection, table: str, path: Path) -> None:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if not rows:
        return

    columns = reader.fieldnames or []
    placeholders = ", ".join(["?"] * len(columns))
    col_sql = ", ".join(columns)
    conn.executemany(
        f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})",
        [[coerce_value(row[col]) for col in columns] for row in rows],
    )


def load_csv(conn: sqlite3.Connection, table: str) -> None:
    load_csv_path(conn, table, SEED_DIR / f"{table}.csv")


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        for table, path in LOAD_PLAN:
            load_csv_path(conn, table, path)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Initialized {DB_PATH}")
