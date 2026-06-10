from __future__ import annotations

import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "oligosafety.db"
OUTPUT_PATH = ROOT / "data" / "generated" / "sequence_modification_curation_template_v1.csv"

SEQUENCE_COLUMNS = [
    ("sense_sequence", "TEXT"),
    ("antisense_sequence", "TEXT"),
    ("guide_sequence", "TEXT"),
    ("passenger_sequence", "TEXT"),
    ("seed_region", "TEXT"),
    ("backbone_chemistry", "TEXT"),
    ("sugar_modification", "TEXT"),
    ("base_modification", "TEXT"),
    ("conjugate_delivery", "TEXT"),
    ("sequence_annotation_status", "TEXT NOT NULL DEFAULT 'needs_curator_sequence_curation'"),
    ("modification_annotation_status", "TEXT NOT NULL DEFAULT 'needs_curator_modification_curation'"),
]

TEMPLATE_COLUMNS = [
    "molecule_id",
    "canonical_name",
    "modality",
    "target_gene_symbol",
    "disease_context",
    "therapeutic_status",
    "sense_sequence",
    "antisense_sequence",
    "guide_sequence",
    "passenger_sequence",
    "seed_region",
    "backbone_chemistry",
    "sugar_modification",
    "base_modification",
    "conjugate_delivery",
    "sequence_annotation_status",
    "modification_annotation_status",
    "source_pmid",
    "source_doi",
    "source_url",
    "source_location_verified",
    "curator_decision",
    "validation_status",
    "reviewer_note",
    "updated_at",
]


def existing_columns(conn: sqlite3.Connection) -> set[str]:
    return {str(row[1]) for row in conn.execute("PRAGMA table_info(molecule)").fetchall()}


def migrate(conn: sqlite3.Connection) -> list[str]:
    present = existing_columns(conn)
    added: list[str] = []
    for name, definition in SEQUENCE_COLUMNS:
        if name in present:
            continue
        conn.execute(f"ALTER TABLE molecule ADD COLUMN {name} {definition}")
        added.append(name)
    conn.commit()
    return added


def export_template(conn: sqlite3.Connection) -> int:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = conn.execute(
        """
        SELECT molecule.id AS molecule_id,
               molecule.canonical_name,
               modality.name AS modality,
               molecule.target_gene_symbol,
               molecule.disease_context,
               molecule.therapeutic_status,
               molecule.sense_sequence,
               molecule.antisense_sequence,
               molecule.guide_sequence,
               molecule.passenger_sequence,
               molecule.seed_region,
               molecule.backbone_chemistry,
               molecule.sugar_modification,
               molecule.base_modification,
               molecule.conjugate_delivery,
               molecule.sequence_annotation_status,
               molecule.modification_annotation_status
        FROM molecule
        JOIN modality ON molecule.modality_id = modality.id
        ORDER BY molecule.id
        """
    ).fetchall()
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TEMPLATE_COLUMNS)
        writer.writeheader()
        for row in rows:
            payload = dict(zip(TEMPLATE_COLUMNS[:17], row))
            payload.update(
                {
                    "source_pmid": "",
                    "source_doi": "",
                    "source_url": "",
                    "source_location_verified": "",
                    "curator_decision": "",
                    "validation_status": "needs_curator_verification",
                    "reviewer_note": "",
                    "updated_at": now,
                }
            )
            writer.writerow(payload)
    return len(rows)


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        added = migrate(conn)
        rows_written = export_template(conn)
    finally:
        conn.close()
    print(f"db={DB_PATH}")
    print(f"added_columns={','.join(added) if added else 'none'}")
    print(f"template={OUTPUT_PATH}")
    print(f"rows_written={rows_written}")


if __name__ == "__main__":
    main()
