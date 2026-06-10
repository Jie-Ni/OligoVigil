from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "oligosafety.db"
DEFAULT_REVIEW_CSV = ROOT / "data" / "generated" / "curator_review_template_v1.csv"
ALLOWED_GRADES = {"A", "B", "C"}


def required(row: dict[str, str], field: str) -> str:
    value = (row.get(field) or "").strip()
    if not value:
        raise ValueError(f"accepted row {row.get('candidate_id')} is missing {field}")
    return value


def optional_int(value: str) -> int | None:
    value = (value or "").strip()
    return int(value) if value else None


def optional_float(value: str) -> float | None:
    value = (value or "").strip()
    return float(value) if value else None


def truthy(value: str, default: bool) -> int:
    value = (value or "").strip().lower()
    if not value:
        return int(default)
    if value in {"1", "true", "yes", "y"}:
        return 1
    if value in {"0", "false", "no", "n"}:
        return 0
    raise ValueError(f"invalid boolean value: {value}")


def optional_text(row: dict[str, str], field: str) -> str | None:
    return (row.get(field) or "").strip() or None


def source_document_id(conn: sqlite3.Connection, candidate_id: str) -> int:
    row = conn.execute(
        "SELECT source_document_id FROM curation_candidate WHERE id = ?",
        (candidate_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"unknown candidate_id: {candidate_id}")
    return int(row[0])


def candidate_state(conn: sqlite3.Connection, candidate_id: str) -> tuple[str, str] | None:
    row = conn.execute(
        "SELECT validation_status, curator_decision FROM curation_candidate WHERE id = ?",
        (candidate_id,),
    ).fetchone()
    if row is None:
        return None
    return str(row[0]), str(row[1])


def already_synced(conn: sqlite3.Connection, row: dict[str, str]) -> bool:
    state = candidate_state(conn, required(row, "candidate_id"))
    if state is None:
        raise ValueError(f"unknown candidate_id: {row.get('candidate_id')}")
    return state == (required(row, "validation_status"), required(row, "curator_decision"))


def modality_id(conn: sqlite3.Connection, row: dict[str, str]) -> int:
    modality = (
        row.get("modality_name")
        or row.get("molecule_modality")
        or row.get("candidate_modality")
        or ""
    ).strip()
    if modality == "ASO/siRNA":
        modality = "ASO/siRNA mixed context"
    if not modality:
        raise ValueError(f"accepted row {row.get('candidate_id')} is missing modality")
    existing = conn.execute("SELECT id FROM modality WHERE name = ?", (modality,)).fetchone()
    if existing:
        return int(existing[0])
    cursor = conn.execute(
        """
        INSERT INTO modality (name, in_core_scope, scope_note)
        VALUES (?, 1, 'Created during curator-verified release promotion')
        """,
        (modality,),
    )
    return int(cursor.lastrowid)


def ensure_molecule(conn: sqlite3.Connection, row: dict[str, str]) -> int:
    molecule_id = optional_int(row.get("molecule_id", ""))
    if molecule_id:
        existing = conn.execute("SELECT id FROM molecule WHERE id = ?", (molecule_id,)).fetchone()
        if existing is None:
            raise ValueError(f"unknown molecule_id: {molecule_id}")
        return molecule_id

    canonical_name = (
        row.get("molecule_canonical_name")
        or row.get("molecule_name")
        or row.get("molecule_name_verified")
        or ""
    ).strip()
    if not canonical_name:
        raise ValueError(
            f"accepted row {row.get('candidate_id')} needs molecule_id or molecule_canonical_name"
        )
    mod_id = modality_id(conn, row)
    target = (row.get("target_gene_symbol") or row.get("target_gene_symbol_verified") or "").strip()
    disease = (row.get("disease_context") or "").strip()
    status = (row.get("therapeutic_status") or "").strip()
    external_ids = (row.get("external_ids") or "").strip() or "{}"
    try:
        json.loads(external_ids)
    except json.JSONDecodeError as exc:
        raise ValueError(f"external_ids must be JSON for candidate {row.get('candidate_id')}") from exc

    existing = conn.execute(
        """
        SELECT id
        FROM molecule
        WHERE canonical_name = ?
          AND modality_id = ?
          AND COALESCE(target_gene_symbol, '') = COALESCE(?, '')
        """,
        (canonical_name, mod_id, target),
    ).fetchone()
    if existing:
        return int(existing[0])

    cursor = conn.execute(
        """
        INSERT INTO molecule (
            canonical_name, modality_id, target_gene_symbol, disease_context,
            therapeutic_status, external_ids, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            canonical_name,
            mod_id,
            target or None,
            disease or None,
            status or None,
            external_ids,
            datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        ),
    )
    return int(cursor.lastrowid)


def ensure_assay(conn: sqlite3.Connection, row: dict[str, str], source_id: int) -> int | None:
    assay_id = optional_int(row.get("assay_id", ""))
    if assay_id:
        existing = conn.execute("SELECT id FROM assay WHERE id = ?", (assay_id,)).fetchone()
        if existing is None:
            raise ValueError(f"unknown assay_id: {assay_id}")
        return assay_id

    assay_type = (row.get("assay_type") or row.get("assay_type_verified") or "").strip()
    if not assay_type:
        return None

    cursor = conn.execute(
        """
        INSERT INTO assay (
            assay_type, organism, model_system, cell_line_or_tissue, dose_value,
            dose_unit, exposure_time_value, exposure_time_unit, replicate_count,
            source_document_id, source_location
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            assay_type,
            (row.get("organism") or "").strip() or None,
            (row.get("model_system") or row.get("model_context") or "").strip() or None,
            (row.get("cell_line_or_tissue") or "").strip() or None,
            optional_float(row.get("dose_value", "")),
            (row.get("dose_unit") or "").strip() or None,
            optional_float(row.get("exposure_time_value", "")),
            (row.get("exposure_time_unit") or "").strip() or None,
            optional_int(row.get("replicate_count", "")),
            source_id,
            (row.get("assay_source_location") or row.get("source_location_verified") or "").strip()
            or None,
        ),
    )
    return int(cursor.lastrowid)


def validate_accept(row: dict[str, str]) -> None:
    grade = required(row, "evidence_grade")
    if grade not in ALLOWED_GRADES:
        raise ValueError(f"accepted row {row.get('candidate_id')} has invalid evidence_grade {grade}")
    if row.get("validation_status") != "curator_verified":
        raise ValueError(f"accepted row {row.get('candidate_id')} must be curator_verified")
    audit_note = required(row, "audit_note")
    if "machine pre-curation only" in audit_note.lower() or "precuration only" in audit_note.lower():
        raise ValueError(
            f"accepted row {row.get('candidate_id')} still has machine-only audit_note"
        )
    if not row.get("molecule_id") and not (
        row.get("molecule_canonical_name")
        or row.get("molecule_name")
        or row.get("molecule_name_verified")
    ):
        raise ValueError(
            f"accepted row {row.get('candidate_id')} needs molecule_id or molecule_canonical_name"
        )
    if row.get("verified_entity_table") == "toxicity_endpoint":
        required(row, "endpoint_name")
        required(row, "endpoint_category")
        required(row, "source_location_verified")
    elif row.get("verified_entity_table") == "offtarget_evidence":
        required(row, "evidence_type")
        required(row, "source_location_verified")
    else:
        raise ValueError(
            f"accepted row {row.get('candidate_id')} must target toxicity_endpoint or offtarget_evidence"
        )


def validate_reject(row: dict[str, str]) -> None:
    required(row, "candidate_id")
    if row.get("validation_status") != "curator_rejected":
        raise ValueError(f"rejected row {row.get('candidate_id')} must be curator_rejected")
    if row.get("curator_decision") != "reject":
        raise ValueError(f"rejected row {row.get('candidate_id')} must have curator_decision=reject")
    required(row, "audit_note")


def benchmark_split_name(leakage_group: str) -> str:
    bucket = int(hashlib.sha256(leakage_group.encode("utf-8")).hexdigest()[:8], 16) % 100
    if bucket < 70:
        return "train"
    if bucket < 85:
        return "validation"
    return "test"


def benchmark_task_name(entity_table: str) -> str:
    if entity_table == "offtarget_evidence":
        return "offtarget_safety_v0_1"
    return "toxicity_safety_v0_1"


def benchmark_version(row: dict[str, str]) -> str:
    batch = optional_text(row, "release_scale_batch") or "curator_review"
    return f"{batch}_manual_benchmark_v1"


def benchmark_leakage_group(source_id: int, molecule_id: int) -> str:
    return f"source:{source_id}|molecule:{molecule_id}"


def insert_benchmark_split(
    conn: sqlite3.Connection,
    row: dict[str, str],
    entity_table: str,
    entity_id: int,
    source_id: int,
    molecule_id: int,
) -> bool:
    if not truthy(row.get("benchmark_eligible_proposed", ""), False):
        return False
    if required(row, "evidence_grade") not in {"A", "B"}:
        return False
    leakage_group = benchmark_leakage_group(source_id, molecule_id)
    existing = conn.execute(
        """
        SELECT id
        FROM benchmark_split
        WHERE entity_table = ? AND entity_id = ?
        """,
        (entity_table, entity_id),
    ).fetchone()
    if existing:
        return False
    conn.execute(
        """
        INSERT INTO benchmark_split (
            task_name, split_name, entity_table, entity_id,
            split_strategy, leakage_group, version, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            benchmark_task_name(entity_table),
            benchmark_split_name(leakage_group),
            entity_table,
            entity_id,
            "source_plus_molecule_grouped_hash_v1",
            leakage_group,
            benchmark_version(row),
            datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        ),
    )
    return True


def sync_reject_row(conn: sqlite3.Connection, row: dict[str, str]) -> int:
    validate_reject(row)
    candidate_id = int(required(row, "candidate_id"))
    conn.execute(
        """
        UPDATE curation_candidate
        SET validation_status = ?, curator_decision = ?
        WHERE id = ?
        """,
        (
            required(row, "validation_status"),
            required(row, "curator_decision"),
            candidate_id,
        ),
    )
    conn.execute(
        """
        INSERT INTO curation_audit (
            entity_table, entity_id, extraction_method, extractor_model_or_script,
            validation_status, curator_decision, curator_id, audit_note, audited_at
        )
        VALUES ('curation_candidate', ?, 'curator_review_v1', 'promote_curator_review.py',
                ?, ?, ?, ?, ?)
        """,
        (
            candidate_id,
            required(row, "validation_status"),
            required(row, "curator_decision"),
            optional_text(row, "curator_id"),
            row.get("audit_note") or "",
            datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        ),
    )
    return candidate_id


def promote_row(conn: sqlite3.Connection, row: dict[str, str]) -> tuple[str, int, bool]:
    validate_accept(row)
    source_id = source_document_id(conn, required(row, "candidate_id"))
    entity_table = required(row, "verified_entity_table")
    molecule_id = ensure_molecule(conn, row)
    assay_id = ensure_assay(conn, row, source_id)
    grade = required(row, "evidence_grade")
    location = required(row, "source_location_verified")

    if entity_table == "toxicity_endpoint":
        cursor = conn.execute(
            """
            INSERT INTO toxicity_endpoint (
                molecule_id, assay_id, endpoint_name, endpoint_category,
                measured_value, measured_unit, direction, significance_label,
                is_observed_experimental, source_document_id, source_location,
                evidence_grade
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                molecule_id,
                assay_id,
                required(row, "endpoint_name"),
                required(row, "endpoint_category"),
                optional_float(row.get("measured_value", "")),
                (row.get("measured_unit") or "").strip() or None,
                (row.get("direction") or "").strip() or None,
                (row.get("significance_label") or "").strip() or None,
                truthy(row.get("is_observed_experimental", ""), True),
                source_id,
                location,
                grade,
            ),
        )
    else:
        cursor = conn.execute(
            """
            INSERT INTO offtarget_evidence (
                molecule_id, assay_id, offtarget_gene_symbol, offtarget_transcript_id,
                evidence_type, measured_effect, effect_unit, match_type,
                seed_match_length, is_observed_experimental, is_computational_prediction,
                source_document_id, source_location, evidence_grade
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                molecule_id,
                assay_id,
                (row.get("offtarget_gene_symbol") or "").strip() or None,
                (row.get("offtarget_transcript_id") or "").strip() or None,
                required(row, "evidence_type"),
                optional_float(row.get("measured_effect", "")),
                (row.get("effect_unit") or "").strip() or None,
                (row.get("match_type") or "").strip() or None,
                optional_int(row.get("seed_match_length", "")),
                truthy(row.get("is_observed_experimental", ""), True),
                truthy(row.get("is_computational_prediction", ""), False),
                source_id,
                location,
                grade,
            ),
        )

    entity_id = int(cursor.lastrowid)
    conn.execute(
        """
        INSERT INTO curation_audit (
            entity_table, entity_id, extraction_method, extractor_model_or_script,
            validation_status, curator_decision, curator_id, audit_note, audited_at
        )
        VALUES (?, ?, 'curator_review_v1', 'promote_curator_review.py',
                ?, ?, ?, ?, ?)
        """,
        (
            entity_table,
            entity_id,
            required(row, "validation_status"),
            required(row, "curator_decision"),
            optional_text(row, "curator_id"),
            row.get("audit_note") or "",
            datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        ),
    )
    conn.execute(
        """
        UPDATE curation_candidate
        SET validation_status = ?, curator_decision = ?
        WHERE id = ?
        """,
        (
            required(row, "validation_status"),
            required(row, "curator_decision"),
            required(row, "candidate_id"),
        ),
    )
    benchmark_inserted = insert_benchmark_split(
        conn, row, entity_table, entity_id, source_id, molecule_id
    )
    return entity_table, entity_id, benchmark_inserted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-csv", type=Path, default=DEFAULT_REVIEW_CSV)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with args.review_csv.open("r", encoding="utf-8", newline="") as handle:
        review_rows = list(csv.DictReader(handle))
    accepted = [row for row in review_rows if row.get("curator_decision") == "accept"]
    rejected = [row for row in review_rows if row.get("curator_decision") == "reject"]

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        promoted: list[tuple[str, int, bool]] = []
        synced_rejects: list[int] = []
        skipped_accepts = 0
        skipped_rejects = 0
        for row in accepted:
            validate_accept(row)
            if already_synced(conn, row):
                skipped_accepts += 1
                continue
            promoted.append(promote_row(conn, row))
        for row in rejected:
            validate_reject(row)
            if already_synced(conn, row):
                skipped_rejects += 1
                continue
            synced_rejects.append(sync_reject_row(conn, row))
        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
    finally:
        conn.close()

    print(
        " ".join(
            [
                f"accepted_rows={len(accepted)}",
                f"promoted_rows={0 if args.dry_run else len(promoted)}",
                f"skipped_accepts={skipped_accepts}",
                f"benchmark_rows={0 if args.dry_run else sum(1 for _, _, inserted in promoted if inserted)}",
                f"rejected_rows={len(rejected)}",
                f"synced_rejects={0 if args.dry_run else len(synced_rejects)}",
                f"skipped_rejects={skipped_rejects}",
            ]
        )
    )


if __name__ == "__main__":
    main()
