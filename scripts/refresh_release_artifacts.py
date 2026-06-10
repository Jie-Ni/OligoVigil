from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "oligosafety.db"
SEED_SOURCE = ROOT / "data" / "seed" / "source_document.csv"
GENERATED_DIR = ROOT / "data" / "generated"
MANIFEST_DIR = ROOT / "data" / "manifests"


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")]


def seed_source_ids() -> set[int]:
    if not SEED_SOURCE.exists():
        return set()
    with SEED_SOURCE.open("r", encoding="utf-8", newline="") as handle:
        return {int(row["id"]) for row in csv.DictReader(handle) if row.get("id")}


def export_query(
    conn: sqlite3.Connection,
    query: str,
    csv_path: Path,
    json_path: Path | None = None,
    params: tuple[object, ...] = (),
) -> int:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    conn.row_factory = sqlite3.Row
    rows = [dict(row) for row in conn.execute(query, params).fetchall()]
    fieldnames = list(rows[0].keys()) if rows else []
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    if json_path:
        json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(rows)


def export_table(conn: sqlite3.Connection, table: str, csv_path: Path, json_path: Path | None = None) -> int:
    columns = table_columns(conn, table)
    column_sql = ", ".join(columns)
    return export_query(conn, f"SELECT {column_sql} FROM {table} ORDER BY id", csv_path, json_path)


def source_priority(source_type: str) -> str:
    if source_type in {
        "nar_guideline",
        "nar_editorial",
        "challenge_notice",
        "closest_work",
        "database_reference",
        "industry_guidance",
        "tool_reference",
    }:
        return "core"
    if source_type == "review_reference":
        return "context"
    return "candidate_pool"


def export_source_candidates_v6(conn: sqlite3.Connection) -> int:
    path = MANIFEST_DIR / "source_candidates_v6.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = conn.execute(
        """
        SELECT id, source_type, source_url, pmid, doi, title, journal_or_agency,
               publication_year, license_status, reuse_category
        FROM source_document
        ORDER BY id
        """
    ).fetchall()
    fieldnames = [
        "source_key",
        "pmid",
        "source_type",
        "reuse_category",
        "license_status",
        "priority",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            source_type = str(row["source_type"] or "")
            pmid = str(row["pmid"] or "")
            source_key = f"pmid_{pmid}" if pmid else f"source_{row['id']}"
            title = str(row["title"] or "").replace("\n", " ").strip()
            journal = str(row["journal_or_agency"] or "").strip()
            year = str(row["publication_year"] or "").strip()
            writer.writerow(
                {
                    "source_key": source_key,
                    "pmid": pmid,
                    "source_type": source_type,
                    "reuse_category": row["reuse_category"] or "",
                    "license_status": row["license_status"] or "",
                    "priority": source_priority(source_type),
                    "notes": "; ".join(part for part in [title, journal, year] if part)[:600],
                }
            )
    return len(rows)


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        seed_ids = seed_source_ids()
        placeholders = ",".join("?" for _ in seed_ids) or "NULL"
        source_query = (
            "SELECT "
            + ", ".join(table_columns(conn, "source_document"))
            + f" FROM source_document WHERE id NOT IN ({placeholders}) ORDER BY id"
        )
        source_rows = export_query(
            conn,
            source_query,
            GENERATED_DIR / "source_document_pubmed_v1.csv",
            GENERATED_DIR / "source_document_pubmed_v1.json",
            tuple(sorted(seed_ids)),
        )
        queue_rows = export_table(conn, "curation_queue", GENERATED_DIR / "curation_queue_v1.csv")
        candidate_rows = export_table(
            conn,
            "curation_candidate",
            GENERATED_DIR / "curation_candidate_v1.csv",
            GENERATED_DIR / "curation_candidate_v1.json",
        )
        source_manifest_rows = export_source_candidates_v6(conn)
    finally:
        conn.close()
    print(f"source_document_pubmed_v1_rows={source_rows}")
    print(f"curation_queue_v1_rows={queue_rows}")
    print(f"curation_candidate_v1_rows={candidate_rows}")
    print(f"source_candidates_v6_rows={source_manifest_rows}")


if __name__ == "__main__":
    main()
