from __future__ import annotations

import csv
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "oligosafety.db"
PACKET_CSV = ROOT / "data" / "generated" / "release_scale_3000_prequest.csv"
SUMMARY_JSON = ROOT / "data" / "generated" / "release_scale_3000_summary.json"


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> None:
    if not PACKET_CSV.exists():
        fail(f"missing packet CSV: {PACKET_CSV}")
    with PACKET_CSV.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) < 3000:
        fail(f"release-scale packet has fewer than 3000 rows: {len(rows)}")

    candidate_ids = [row["candidate_id"] for row in rows]
    if len(candidate_ids) != len(set(candidate_ids)):
        fail("release-scale packet contains duplicate candidate_id values")
    accepted = [row for row in rows if row.get("curator_decision") == "accept"]
    if accepted:
        fail("release-scale packet must not contain pre-accepted rows")
    verified = [row for row in rows if row.get("validation_status") == "curator_verified"]
    if verified:
        fail("release-scale packet must not contain pre-verified rows")
    invalid_domain = [row for row in rows if row.get("evidence_domain") not in {"toxicity", "offtarget"}]
    if invalid_domain:
        fail("release-scale packet contains non toxicity/offtarget domains")
    missing_source = [
        row
        for row in rows
        if not (row.get("pmid") or row.get("doi"))
        or not (row.get("candidate_source_location") or row.get("proposed_source_location"))
    ]
    if missing_source:
        fail("release-scale packet contains rows without source identifiers or source locations")

    domains = Counter(row["evidence_domain"] for row in rows)
    if domains["offtarget"] < 500:
        fail(f"offtarget coverage too low for release-scale packet: {domains['offtarget']}")
    priorities = Counter(row["review_priority"] for row in rows)
    full_text_anchor_rows = sum(1 for row in rows if row.get("source_anchor_hash"))

    conn = sqlite3.connect(DB_PATH)
    try:
        release_count = conn.execute(
            "SELECT (SELECT COUNT(*) FROM toxicity_endpoint) + (SELECT COUNT(*) FROM offtarget_evidence)"
        ).fetchone()[0]
        accepted_release_audits = conn.execute(
            """
            SELECT COUNT(*)
            FROM curation_audit
            WHERE entity_table IN ('toxicity_endpoint', 'offtarget_evidence')
              AND validation_status = 'curator_verified'
              AND curator_decision = 'accept'
            """
        ).fetchone()[0]
    finally:
        conn.close()
    if release_count != accepted_release_audits:
        fail("existing release evidence count does not match accepted release audits")

    if SUMMARY_JSON.exists():
        summary = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
        if int(summary.get("rows") or 0) != len(rows):
            fail("summary JSON row count does not match packet CSV")

    print(
        " ".join(
            [
                "release_scale_packet_check=pass",
                f"rows={len(rows)}",
                f"toxicity={domains['toxicity']}",
                f"offtarget={domains['offtarget']}",
                f"full_text_anchor_rows={full_text_anchor_rows}",
                f"p0={priorities.get('P0_full_text_high_confidence', 0)}",
                f"existing_release_rows={release_count}",
            ]
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"release_scale_packet_check=fail reason={exc}", file=sys.stderr)
        raise
