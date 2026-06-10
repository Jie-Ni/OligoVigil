from __future__ import annotations

import csv
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "oligosafety.db"
GENERATED_DIR = ROOT / "data" / "generated"
REVIEW_TEMPLATE = GENERATED_DIR / "curator_review_template_v1.csv"

FIELDS = [
    "candidate_id",
    "queue_id",
    "pmid",
    "doi",
    "evidence_domain",
    "candidate_modality",
    "source_location",
    "matched_terms",
    "confidence_label",
    "curator_decision",
    "verified_entity_table",
    "molecule_id",
    "assay_id",
    "endpoint_name",
    "endpoint_category",
    "evidence_type",
    "source_location_verified",
    "evidence_grade",
    "validation_status",
    "audit_note",
]


def rows() -> list[dict[str, object]]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        candidates = conn.execute(
            """
            SELECT id AS candidate_id, queue_id, pmid, doi, evidence_domain,
                   candidate_modality, source_location, matched_terms, confidence_label
            FROM curation_candidate
            ORDER BY CASE confidence_label
                WHEN 'high_candidate' THEN 0
                WHEN 'medium_candidate' THEN 1
                ELSE 2
            END, id
            """
        ).fetchall()
    finally:
        conn.close()

    output: list[dict[str, object]] = []
    for row in candidates:
        item = {field: "" for field in FIELDS}
        for key in row.keys():
            item[key] = row[key] or ""
        item["curator_decision"] = "pending"
        item["validation_status"] = "candidate_needs_curator_review"
        if row["evidence_domain"] == "toxicity":
            item["verified_entity_table"] = "toxicity_endpoint"
        elif row["evidence_domain"] == "offtarget":
            item["verified_entity_table"] = "offtarget_evidence"
        else:
            item["verified_entity_table"] = "curation_audit_only"
        output.append(item)
    return output


def main() -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    output = rows()
    with REVIEW_TEMPLATE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output)
    print(f"curator_review_rows={len(output)} generated={REVIEW_TEMPLATE}")


if __name__ == "__main__":
    main()
