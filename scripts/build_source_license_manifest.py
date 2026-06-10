from __future__ import annotations

import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "oligosafety.db"
OUTPUT_PATH = ROOT / "data" / "manifests" / "source_license_manifest_v1.csv"

COLUMNS = [
    "source_document_id",
    "source_type",
    "pmid",
    "pmcid",
    "doi",
    "source_url",
    "journal_or_agency",
    "publication_year",
    "license_status",
    "reuse_category",
    "release_evidence_rows",
    "candidate_rows",
    "article_license",
    "oa_subset_status",
    "raw_text_used",
    "raw_text_stored",
    "raw_redistribution_allowed",
    "derived_annotation_allowed",
    "commercial_reuse_allowed",
    "license_review_status",
    "reviewed_at",
    "restriction_note",
]


def source_policy(row: sqlite3.Row) -> dict[str, str]:
    license_status = str(row["license_status"] or "")
    reuse_category = str(row["reuse_category"] or "")
    source_type = str(row["source_type"] or "")
    has_pmcid = bool(row["pmcid"])
    open_like = license_status in {"open_access", "official_guideline", "official_notice"}
    query_only = reuse_category == "query_linkout_only"
    article_license = license_status or "not_recorded"
    oa_subset_status = "pmcid_present_license_not_verified" if has_pmcid else "not_applicable"
    if open_like and has_pmcid:
        oa_subset_status = "open_or_official_source_recorded"
    if query_only:
        raw_allowed = "false"
        derived_allowed = "external_linkout_only"
        commercial = "unknown"
        review_status = "restricted_linkout"
    elif open_like:
        raw_allowed = "not_claimed"
        derived_allowed = "true"
        commercial = "unknown"
        review_status = "source_class_reviewed"
    else:
        raw_allowed = "false"
        derived_allowed = "true"
        commercial = "unknown"
        review_status = "conservative_source_metadata_review"
    note = (
        "OligoVigil redistributes source identifiers, source locations, matched terms, and curator "
        "decisions; raw article text and PDFs are not redistributed."
    )
    if source_type in {"regulatory", "official"}:
        note = (
            "Official/regulatory source metadata and derived annotations are linked; users should "
            "consult the source URL for original document terms."
        )
    return {
        "article_license": article_license,
        "oa_subset_status": oa_subset_status,
        "raw_text_used": "not_stored; source-localized derived annotation only",
        "raw_text_stored": "false",
        "raw_redistribution_allowed": raw_allowed,
        "derived_annotation_allowed": derived_allowed,
        "commercial_reuse_allowed": commercial,
        "license_review_status": review_status,
        "restriction_note": note,
    }


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    release_counts = {
        row["source_document_id"]: row["n"]
        for row in conn.execute(
            """
            SELECT source_document_id, SUM(n) AS n
            FROM (
                SELECT source_document_id, COUNT(*) AS n
                FROM toxicity_endpoint
                GROUP BY source_document_id
                UNION ALL
                SELECT source_document_id, COUNT(*) AS n
                FROM offtarget_evidence
                GROUP BY source_document_id
            )
            GROUP BY source_document_id
            """
        )
    }
    candidate_counts = {
        row["source_document_id"]: row["n"]
        for row in conn.execute(
            """
            SELECT source_document_id, COUNT(*) AS n
            FROM curation_candidate
            GROUP BY source_document_id
            """
        )
    }
    rows = conn.execute(
        """
        SELECT source_document.id, source_document.source_type, source_document.pmid,
               source_document.pmcid, source_document.doi, source_document.source_url,
               source_document.journal_or_agency, source_document.publication_year,
               source_document.license_status, source_document.reuse_category
        FROM source_document
        ORDER BY source_document.id
        """
    ).fetchall()
    reviewed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            policy = source_policy(row)
            writer.writerow(
                {
                    "source_document_id": row["id"],
                    "source_type": row["source_type"],
                    "pmid": row["pmid"],
                    "pmcid": row["pmcid"],
                    "doi": row["doi"],
                    "source_url": row["source_url"],
                    "journal_or_agency": row["journal_or_agency"],
                    "publication_year": row["publication_year"],
                    "license_status": row["license_status"],
                    "reuse_category": row["reuse_category"],
                    "release_evidence_rows": release_counts.get(row["id"], 0),
                    "candidate_rows": candidate_counts.get(row["id"], 0),
                    "reviewed_at": reviewed_at,
                    **policy,
                }
            )
    print(f"source_license_manifest={OUTPUT_PATH}")
    print(f"rows={len(rows)}")


if __name__ == "__main__":
    main()
