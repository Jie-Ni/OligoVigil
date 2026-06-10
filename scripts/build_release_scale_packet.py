from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from build_verified_batch1_packet import (
    FIELDNAMES as PRECURATION_FIELDNAMES,
    Candidate,
    build_record,
    fetch_pmc_xml,
    infer_endpoint,
)


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "oligosafety.db"
GENERATED_DIR = ROOT / "data" / "generated"
DELIVERY_DIR = ROOT.parent / "04_delivery"
DEFAULT_OUTPUT_CSV = GENERATED_DIR / "release_scale_3000_prequest.csv"
DEFAULT_CHECKPOINT_CSV = GENERATED_DIR / "release_scale_3000_prequest.checkpoint.csv"
DEFAULT_PROGRESS_JSON = GENERATED_DIR / "release_scale_3000_progress.json"
DEFAULT_SUMMARY_JSON = GENERATED_DIR / "release_scale_3000_summary.json"
DEFAULT_CARDS = DELIVERY_DIR / "RELEASE_SCALE_3000_PRECURATION.md"

EXTRA_FIELDS = [
    "release_scale_batch",
    "selection_rank",
    "review_priority",
    "candidate_confidence_label",
    "pmc_full_text_available",
    "manual_review_required_reason",
]
FIELDNAMES = [*EXTRA_FIELDS, *PRECURATION_FIELDNAMES]

CONFIDENCE_SCORE = {
    "high_candidate": 300,
    "medium_candidate": 200,
    "low_candidate": 100,
}


def candidate_rows() -> list[sqlite3.Row]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            """
            SELECT c.id AS candidate_id, c.queue_id, c.source_document_id, c.pmid,
                   s.pmcid, c.doi, c.evidence_domain, c.candidate_modality,
                   c.source_location, c.matched_terms, c.candidate_signal,
                   c.suggested_evidence_grade, c.confidence_label,
                   s.title, s.journal_or_agency, s.publication_year, s.source_url,
                   s.license_status, s.reuse_category
            FROM curation_candidate AS c
            JOIN source_document AS s ON s.id = c.source_document_id
            WHERE c.evidence_domain IN ('toxicity', 'offtarget')
              AND c.validation_status = 'candidate_needs_curator_review'
              AND c.curator_decision = 'pending'
              AND c.source_location IS NOT NULL
              AND c.source_location != ''
              AND (COALESCE(c.pmid, '') != '' OR COALESCE(c.doi, '') != '')
            ORDER BY c.id
            """
        ).fetchall()
    finally:
        conn.close()


def rank_row(row: sqlite3.Row) -> tuple[int, int, int, int]:
    confidence = CONFIDENCE_SCORE.get(str(row["confidence_label"]), 0)
    pmc_bonus = 50 if row["pmcid"] else 0
    year = int(row["publication_year"] or 0)
    return confidence + pmc_bonus, year, -int(row["candidate_id"]), 0


def select_candidates(target: int, max_offtarget: int) -> list[sqlite3.Row]:
    rows = candidate_rows()
    by_domain = {
        "offtarget": [row for row in rows if row["evidence_domain"] == "offtarget"],
        "toxicity": [row for row in rows if row["evidence_domain"] == "toxicity"],
    }
    for domain in by_domain:
        by_domain[domain].sort(key=rank_row, reverse=True)

    offtarget_take = min(len(by_domain["offtarget"]), max_offtarget, target)
    selected = [*by_domain["offtarget"][:offtarget_take]]
    remaining = target - len(selected)
    selected.extend(by_domain["toxicity"][:remaining])
    if len(selected) < target:
        used = {row["candidate_id"] for row in selected}
        rest = [row for row in rows if row["candidate_id"] not in used]
        rest.sort(key=rank_row, reverse=True)
        selected.extend(rest[: target - len(selected)])
    return selected[:target]


def to_candidate(row: sqlite3.Row) -> Candidate:
    payload = dict(row)
    payload.pop("confidence_label", None)
    return Candidate(**payload)


def review_priority(row: sqlite3.Row, record: dict[str, str]) -> str:
    if record.get("risk_flags") == "none" and row["confidence_label"] == "high_candidate":
        return "P0_full_text_high_confidence"
    if record.get("proposed_source_location") and row["confidence_label"] in {
        "high_candidate",
        "medium_candidate",
    }:
        return "P1_full_text_review"
    if row["confidence_label"] in {"high_candidate", "medium_candidate"}:
        return "P2_source_location_review"
    return "P3_low_confidence_backfill"


def fallback_record(candidate: Candidate, confidence_label: str, reason: str) -> dict[str, str]:
    record = build_record(candidate, "", reason)
    text = f"{candidate.title} {candidate.candidate_signal} {candidate.matched_terms}"
    endpoint_name, endpoint_category_or_type = infer_endpoint(candidate, text)
    grade = candidate.suggested_evidence_grade if candidate.suggested_evidence_grade in {"A", "B", "C"} else "C"
    if confidence_label == "low_candidate":
        grade = "C"
    record["proposed_source_location"] = candidate.source_location
    record["source_location_verified"] = ""
    record["machine_matched_terms"] = candidate.matched_terms
    record["evidence_grade_proposed"] = grade
    record["evidence_grade"] = grade
    record["modality_name"] = (
        candidate.candidate_modality
        if candidate.candidate_modality != "ASO/siRNA"
        else "ASO/siRNA mixed context"
    )
    record["verified_entity_table"] = (
        "toxicity_endpoint" if candidate.evidence_domain == "toxicity" else "offtarget_evidence"
    )
    if candidate.evidence_domain == "toxicity":
        record["endpoint_name_proposed"] = endpoint_name
        record["endpoint_name"] = endpoint_name
        record["endpoint_category_proposed"] = endpoint_category_or_type
        record["endpoint_category"] = endpoint_category_or_type
    else:
        record["evidence_type_proposed"] = endpoint_category_or_type
        record["evidence_type"] = endpoint_category_or_type
    record["curator_decision"] = "pending"
    record["validation_status"] = "candidate_needs_curator_review"
    record["risk_flags"] = "; ".join(
        [
            "no_machine_full_text_anchor",
            "source_location_not_verified",
            reason,
        ]
    )
    record["audit_note_proposed"] = (
        "Release-scale precuration only. Human curator must verify the source location, "
        "molecule identity, assay context, endpoint label, and evidence grade before promotion."
    )
    record["audit_note"] = ""
    return record


def enrich_record(
    row: sqlite3.Row,
    record: dict[str, str],
    rank: int,
    batch: str,
    manual_reason: str,
) -> dict[str, str]:
    output = {field: record.get(field, "") for field in PRECURATION_FIELDNAMES}
    output.update(
        {
            "release_scale_batch": batch,
            "selection_rank": str(rank),
            "review_priority": review_priority(row, output),
            "candidate_confidence_label": str(row["confidence_label"]),
            "pmc_full_text_available": "true" if row["pmcid"] else "false",
            "manual_review_required_reason": manual_reason,
        }
    )
    return {field: output.get(field, "") for field in FIELDNAMES}


def build_records(
    selected: list[sqlite3.Row],
    batch: str,
    cache_dir: Path,
    pause_seconds: float,
    skip_pmc_fetch: bool,
    checkpoint_csv: Path | None = None,
    progress_json: Path | None = None,
    checkpoint_every: int = 100,
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for rank, row in enumerate(selected, start=1):
        candidate = to_candidate(row)
        manual_reason = "human_curator_required_for_release_promotion"
        if skip_pmc_fetch:
            reason = "pmc_fetch_skipped_for_mega_packet"
            record = fallback_record(candidate, str(row["confidence_label"]), reason)
            manual_reason = reason
        elif candidate.pmcid:
            xml_text, fetch_status = fetch_pmc_xml(candidate.pmcid, cache_dir, pause_seconds)
            if xml_text:
                record = build_record(candidate, xml_text, fetch_status)
                record["curator_decision"] = "pending"
                record["validation_status"] = "candidate_needs_curator_review"
                record["audit_note"] = ""
                if record.get("risk_flags") != "none":
                    manual_reason = f"risk_flags_require_resolution:{record.get('risk_flags')}"
                else:
                    manual_reason = "full_text_anchor_machine_found_human_verification_required"
            else:
                record = fallback_record(candidate, str(row["confidence_label"]), fetch_status)
                manual_reason = fetch_status
        else:
            record = fallback_record(candidate, str(row["confidence_label"]), "no_pmcid")
            manual_reason = "no_pmcid_manual_source_review_required"
        records.append(enrich_record(row, record, rank, batch, manual_reason))
        if rank % checkpoint_every == 0:
            if checkpoint_csv is not None:
                write_csv(records, checkpoint_csv)
            if progress_json is not None:
                write_progress(records, progress_json, rank, len(selected), batch)
            print(f"processed={rank}/{len(selected)}", file=sys.stderr)
    return records


def write_csv(records: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(records)


def write_progress(
    records: list[dict[str, str]],
    path: Path,
    processed: int,
    total: int,
    batch: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    domains = Counter(row["evidence_domain"] for row in records)
    priorities = Counter(row["review_priority"] for row in records)
    payload = {
        "batch": batch,
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "processed": processed,
        "total": total,
        "toxicity": domains.get("toxicity", 0),
        "offtarget": domains.get("offtarget", 0),
        "full_text_anchor_rows": sum(1 for row in records if row["source_anchor_hash"]),
        "priority_counts": dict(priorities),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_cards(records: list[dict[str, str]], path: Path, max_cards: int) -> None:
    counts = Counter(row["evidence_domain"] for row in records)
    priorities = Counter(row["review_priority"] for row in records)
    full_text = sum(1 for row in records if row["proposed_source_location"] and row["source_anchor_hash"])
    lines = [
        "# Release-scale 3000 Precuration Packet",
        "",
        "Status: machine-assisted review packet only; zero rows are curator-verified by this file.",
        "",
        f"- total rows: {len(records)}",
        f"- toxicity rows: {counts.get('toxicity', 0)}",
        f"- off-target rows: {counts.get('offtarget', 0)}",
        f"- rows with machine full-text anchor hashes: {full_text}",
        "",
        "## Review Priority Counts",
        "",
    ]
    for priority, n in sorted(priorities.items()):
        lines.append(f"- {priority}: {n}")
    lines.extend(
        [
            "",
            "## Promotion Rule",
            "",
            "A row may become release evidence only after a human curator sets `curator_decision=accept`, `validation_status=curator_verified`, `curator_id`, `audit_note`, and a verified source location. The promotion script does not promote pending rows.",
            "",
            "## First Review Cards",
            "",
        ]
    )
    for index, row in enumerate(records[:max_cards], start=1):
        lines.extend(
            [
                f"### Card {index}: candidate {row['candidate_id']} / PMID {row['pmid']}",
                "",
                f"- priority: {row['review_priority']}",
                f"- confidence: {row['candidate_confidence_label']}",
                f"- domain: {row['evidence_domain']}",
                f"- title: {row['title']}",
                f"- source: {row['source_url']}",
                f"- candidate location: {row['candidate_source_location']}",
                f"- proposed location: {row['proposed_source_location'] or 'needs manual source review'}",
                f"- anchor hash: `{row['source_anchor_hash'] or 'none'}`",
                f"- endpoint/type: {row['endpoint_name_proposed'] or row['evidence_type_proposed']}",
                f"- proposed grade: {row['evidence_grade_proposed']}",
                f"- risk flags: {row['risk_flags']}",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_summary(records: list[dict[str, str]], path: Path, batch: str) -> None:
    counters = {
        "domain": Counter(row["evidence_domain"] for row in records),
        "confidence": Counter(row["candidate_confidence_label"] for row in records),
        "priority": Counter(row["review_priority"] for row in records),
    }
    payload = {
        "batch": batch,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "rows": len(records),
        "counts": {key: dict(value) for key, value in counters.items()},
        "full_text_anchor_rows": sum(
            1 for row in records if row["proposed_source_location"] and row["source_anchor_hash"]
        ),
        "pending_rows": sum(1 for row in records if row["curator_decision"] == "pending"),
        "accepted_rows": sum(1 for row in records if row["curator_decision"] == "accept"),
        "promotion_policy": "human_curator_verified_accept_required",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=3000)
    parser.add_argument("--max-offtarget", type=int, default=1000)
    parser.add_argument("--batch", default="release_scale_3000_v1")
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--checkpoint-csv", type=Path, default=DEFAULT_CHECKPOINT_CSV)
    parser.add_argument("--progress-json", type=Path, default=DEFAULT_PROGRESS_JSON)
    parser.add_argument("--checkpoint-every", type=int, default=100)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--output-cards", type=Path, default=DEFAULT_CARDS)
    parser.add_argument("--max-cards", type=int, default=120)
    parser.add_argument("--pause-seconds", type=float, default=0.34)
    parser.add_argument("--cache-dir", type=Path, default=GENERATED_DIR / "pmc_xml_cache")
    parser.add_argument("--skip-pmc-fetch", action="store_true")
    args = parser.parse_args()

    selected = select_candidates(args.target, args.max_offtarget)
    if len(selected) < args.target:
        raise SystemExit(f"only {len(selected)} eligible pending candidates available for target={args.target}")

    records = build_records(
        selected,
        args.batch,
        args.cache_dir,
        args.pause_seconds,
        args.skip_pmc_fetch,
        args.checkpoint_csv,
        args.progress_json,
        args.checkpoint_every,
    )
    write_csv(records, args.output_csv)
    write_progress(records, args.progress_json, len(records), len(selected), args.batch)
    write_summary(records, args.summary_json, args.batch)
    write_cards(records, args.output_cards, args.max_cards)

    domains = Counter(row["evidence_domain"] for row in records)
    priorities = Counter(row["review_priority"] for row in records)
    print(
        " ".join(
            [
                f"release_scale_rows={len(records)}",
                f"toxicity={domains.get('toxicity', 0)}",
                f"offtarget={domains.get('offtarget', 0)}",
                f"full_text_anchor_rows={sum(1 for row in records if row['source_anchor_hash'])}",
                f"p0={priorities.get('P0_full_text_high_confidence', 0)}",
                f"csv={args.output_csv}",
                f"summary={args.summary_json}",
                f"cards={args.output_cards}",
            ]
        )
    )


if __name__ == "__main__":
    main()
