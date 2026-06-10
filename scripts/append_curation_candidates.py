from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from build_curation_candidates import (
    TARGET_DOMAINS,
    best_location,
    candidate_signal,
    confidence_label,
    matched_terms,
    pubmed_records,
)


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "oligosafety.db"
GENERATED_DIR = ROOT / "data" / "generated"


def queue_rows(domains: set[str]) -> list[sqlite3.Row]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ", ".join("?" for _ in domains)
        return list(
            conn.execute(
                f"""
                SELECT q.id, q.source_document_id, q.pmid, q.doi, q.source_title,
                       q.evidence_domain, q.candidate_modality, q.suggested_evidence_grade
                FROM curation_queue AS q
                LEFT JOIN curation_candidate AS c ON c.queue_id = q.id
                WHERE c.id IS NULL
                  AND q.evidence_domain IN ({placeholders})
                ORDER BY q.id
                """,
                sorted(domains),
            )
        )
    finally:
        conn.close()


def next_candidate_id() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        value = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM curation_candidate").fetchone()[0]
        return int(value)
    finally:
        conn.close()


def build_rows(queue: list[sqlite3.Row], domains: set[str]) -> list[dict[str, object]]:
    pmids = sorted({str(row["pmid"]) for row in queue if row["pmid"]})
    records = pubmed_records(pmids)
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    output: list[dict[str, object]] = []
    current_id = next_candidate_id()

    for row in queue:
        domain = str(row["evidence_domain"])
        if domain not in domains:
            continue
        pmid = str(row["pmid"] or "")
        record = records.get(pmid, {})
        title = str(record.get("title") or row["source_title"] or "")
        sentences = list(record.get("sentences") or [])
        location, terms, _ = best_location(domain, title, sentences)
        if not pmid:
            location = "external source title"
        if not terms:
            terms = matched_terms(str(row["source_title"]), domain)
        output.append(
            {
                "id": current_id,
                "queue_id": row["id"],
                "source_document_id": row["source_document_id"],
                "pmid": pmid,
                "doi": row["doi"] or "",
                "evidence_domain": domain,
                "candidate_modality": row["candidate_modality"],
                "source_location": location,
                "matched_terms": ";".join(terms),
                "candidate_signal": candidate_signal(domain, terms, str(row["source_title"])),
                "suggested_evidence_grade": row["suggested_evidence_grade"],
                "confidence_label": confidence_label(location, terms),
                "extraction_method": "rule_based_pubmed_metadata_append_v1",
                "validation_status": "candidate_needs_curator_review",
                "curator_decision": "pending",
                "redistribution_level": "derived_annotations_only",
                "created_at": created_at,
            }
        )
        current_id += 1
    return output


def write_rows(rows: list[dict[str, object]], label: str) -> tuple[Path, Path]:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = GENERATED_DIR / f"curation_candidate_append_{label}.csv"
    json_path = GENERATED_DIR / f"curation_candidate_append_{label}.json"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    if rows:
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    return csv_path, json_path


def load_rows(rows: list[dict[str, object]], dry_run: bool) -> None:
    if dry_run or not rows:
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        columns = list(rows[0].keys())
        placeholders = ", ".join(["?"] * len(columns))
        conn.executemany(
            f"INSERT INTO curation_candidate ({', '.join(columns)}) VALUES ({placeholders})",
            [[row[column] for column in columns] for row in rows],
        )
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--domains",
        default=",".join(sorted(TARGET_DOMAINS)),
        help="Comma-separated evidence domains to append from new curation_queue rows.",
    )
    args = parser.parse_args()

    domains = {item.strip() for item in args.domains.split(",") if item.strip()}
    unknown = domains - TARGET_DOMAINS
    if unknown:
        raise SystemExit(f"unknown domains: {sorted(unknown)}")

    queue = queue_rows(domains)
    rows = build_rows(queue, domains)
    csv_path, json_path = write_rows(rows, args.label)
    load_rows(rows, args.dry_run)
    print(
        " ".join(
            [
                f"append_candidates={len(rows)}",
                f"dry_run={args.dry_run}",
                f"csv={csv_path}",
                f"json={json_path}",
            ]
        )
    )


if __name__ == "__main__":
    main()
