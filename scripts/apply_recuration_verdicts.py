"""apply_recuration_verdicts.py — apply HUMAN re-curation verdicts to the release tables.

Consumes a human-reviewed re-curation CSV (the Task A output after a human filled the human_* columns)
and updates the DB for EXISTING release rows (keyed by entity_id):
  - human_decision=reject  -> remove the row from toxicity_endpoint/offtarget_evidence,
                              drop its benchmark_split rows, write a recurated_rejected audit.
  - human_decision=accept  -> keep; write a curator_verified audit with the REAL human curator_id.
  - blank / abstain        -> skip (left non-citable for further review).

RED LINES enforced in code:
  * Acts ONLY on the human `human_decision` column — NEVER on `v2_proposed_decision`
    (the v2/machine proposal must not silently mutate the release).
  * Refuses to act on any accept/reject row whose `human_curator_id` is empty
    (no anonymous human verdicts).

SAFE BY DEFAULT: dry-run (rolls back) unless --commit is passed; takes a timestamped DB backup
before committing. Prints a counts summary.

USAGE:
    python scripts/apply_recuration_verdicts.py --review-csv data/generated/v2_offtarget_review_final.csv          # dry-run
    python scripts/apply_recuration_verdicts.py --review-csv data/generated/v2_offtarget_review_final.csv --commit # write
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "oligosafety.db"
RELEASE_TABLES = {"toxicity_endpoint", "offtarget_evidence"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_audit(conn, entity_table, entity_id, validation_status, decision, curator_id, note):
    conn.execute(
        """
        INSERT INTO curation_audit (
            entity_table, entity_id, extraction_method, extractor_model_or_script,
            validation_status, curator_decision, curator_id, audit_note, audited_at
        ) VALUES (?, ?, 'human_recuration_v2', 'apply_recuration_verdicts.py', ?, ?, ?, ?, ?)
        """,
        (entity_table, entity_id, validation_status, decision, curator_id, note, now_iso()),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--review-csv", required=True, type=Path)
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--commit", action="store_true", help="write to DB (default: dry-run, rolled back)")
    args = ap.parse_args()

    with args.review_csv.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    counts = {"accept_confirmed": 0, "rejected_removed": 0, "benchmark_removed": 0,
              "skipped_no_curator": 0, "skipped_blank_or_abstain": 0, "skipped_bad_table": 0,
              "unknown_entity": 0}
    problems: list[str] = []

    if args.commit:
        bak = args.db.with_suffix(args.db.suffix + f".pre_recuration_demote_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.bak")
        shutil.copy2(args.db, bak)
        print(f"DB backup: {bak}", file=sys.stderr)

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        for r in rows:
            decision = (r.get("human_decision") or "").strip().lower()
            if decision not in ("accept", "reject"):
                counts["skipped_blank_or_abstain"] += 1
                continue
            table = (r.get("entity_table") or "").strip()
            if table not in RELEASE_TABLES:
                counts["skipped_bad_table"] += 1
                problems.append(f"entity_id={r.get('entity_id')} bad entity_table={table!r}")
                continue
            try:
                entity_id = int(r.get("entity_id"))
            except (TypeError, ValueError):
                counts["unknown_entity"] += 1
                continue
            curator_id = (r.get("human_curator_id") or "").strip()
            if not curator_id:
                counts["skipped_no_curator"] += 1
                problems.append(f"entity_id={entity_id} {decision} has empty human_curator_id -> skipped")
                continue
            exists = conn.execute(f"SELECT 1 FROM {table} WHERE id=?", (entity_id,)).fetchone()
            if exists is None:
                counts["unknown_entity"] += 1
                problems.append(f"entity_id={entity_id} not found in {table}")
                continue
            note = (r.get("human_note") or "").strip() or (r.get("v2_grounding_quote") or "").strip()

            if decision == "reject":
                conn.execute(f"DELETE FROM {table} WHERE id=?", (entity_id,))
                bm = conn.execute(
                    "DELETE FROM benchmark_split WHERE entity_table=? AND entity_id=?", (table, entity_id)
                ).rowcount
                counts["benchmark_removed"] += max(bm, 0)
                write_audit(conn, table, entity_id, "recurated_rejected", "reject", curator_id, note)
                counts["rejected_removed"] += 1
            else:  # accept
                write_audit(conn, table, entity_id, "curator_verified", "accept", curator_id, note)
                counts["accept_confirmed"] += 1

        if args.commit:
            conn.commit()
        else:
            conn.rollback()
    finally:
        conn.close()

    print(json.dumps({
        "review_csv": str(args.review_csv),
        "committed": bool(args.commit),
        "counts": counts,
        "problems_sample": problems[:20],
        "note": "dry-run rolled back; pass --commit to write. Acts only on human_decision, never v2_proposed_decision.",
    }, indent=2))


if __name__ == "__main__":
    main()
