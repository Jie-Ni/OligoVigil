from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "oligosafety.db"
GENERATED_DIR = ROOT / "data" / "generated"
CORE_PACKET = GENERATED_DIR / "core_oligo_field_curation_packet_v1.csv"
CORE_SUMMARY = GENERATED_DIR / "core_oligo_field_curation_packet_v1_summary.json"
VALIDATION_PACKET = GENERATED_DIR / "independent_curation_validation_template_v1.csv"
VALIDATION_SUMMARY = GENERATED_DIR / "independent_curation_validation_template_v1_summary.json"

CORE_FIELDS = [
    "packet_row_id",
    "priority",
    "evidence_domain",
    "entity_table",
    "evidence_id",
    "benchmark_eligible",
    "evidence_grade",
    "molecule_id",
    "canonical_name",
    "modality",
    "target_gene_symbol",
    "disease_context",
    "evidence_label",
    "source_document_id",
    "pmid",
    "pmcid",
    "doi",
    "source_title",
    "source_url",
    "source_location",
    "assay_id",
    "organism",
    "model_system",
    "cell_line_or_tissue",
    "dose_value",
    "dose_unit",
    "exposure_time_value",
    "exposure_time_unit",
    "replicate_count",
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
    "missing_sequence",
    "missing_seed",
    "missing_modification",
    "missing_delivery",
    "missing_dose",
    "missing_exposure",
    "missing_model",
    "field_source_location",
    "field_source_quote_or_table_id",
    "source_location_verified",
    "curator_decision",
    "field_curator_id",
    "independent_reviewer_id",
    "review_status",
    "audit_note",
    "do_not_fill_without_source",
    "updated_at",
]

VALIDATION_FIELDS = [
    "validation_sample_id",
    "item_type",
    "stratum",
    "evidence_domain",
    "entity_table",
    "entity_id",
    "evidence_grade",
    "benchmark_eligible",
    "molecule_id",
    "canonical_name",
    "modality",
    "target_gene_symbol",
    "evidence_label",
    "source_document_id",
    "pmid",
    "pmcid",
    "doi",
    "source_title",
    "source_url",
    "source_location",
    "matched_terms",
    "original_curator_decision",
    "original_validation_status",
    "original_audit_note",
    "reviewer2_decision",
    "reviewer2_evidence_grade",
    "reviewer2_source_location_verified",
    "reviewer2_error_type",
    "reviewer2_note",
    "adjudication_decision",
    "adjudicator_note",
    "do_not_change_release_until_adjudicated",
]


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def has_value(value: object) -> bool:
    return text(value).lower() not in {"", "na", "n/a", "nan", "none", "null"}


def bool_text(value: bool) -> str:
    return "TRUE" if value else "FALSE"


def hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fetch_release_rows(conn: sqlite3.Connection) -> list[dict[str, object]]:
    conn.row_factory = sqlite3.Row
    query = """
        SELECT *
        FROM (
            SELECT 'toxicity' AS evidence_domain,
                   'toxicity_endpoint' AS entity_table,
                   tox.id AS evidence_id,
                   tox.evidence_grade,
                   CASE WHEN EXISTS (
                        SELECT 1 FROM benchmark_split AS split
                        WHERE split.entity_table = 'toxicity_endpoint'
                          AND split.entity_id = tox.id
                   ) THEN 'yes' ELSE 'no' END AS benchmark_eligible,
                   mol.id AS molecule_id,
                   mol.canonical_name,
                   modality.name AS modality,
                   mol.target_gene_symbol,
                   mol.disease_context,
                   tox.endpoint_category || ': ' || tox.endpoint_name AS evidence_label,
                   tox.source_document_id,
                   source.pmid,
                   source.pmcid,
                   source.doi,
                   source.title AS source_title,
                   source.source_url,
                   tox.source_location,
                   tox.assay_id,
                   assay.organism,
                   assay.model_system,
                   assay.cell_line_or_tissue,
                   assay.dose_value,
                   assay.dose_unit,
                   assay.exposure_time_value,
                   assay.exposure_time_unit,
                   assay.replicate_count,
                   mol.sense_sequence,
                   mol.antisense_sequence,
                   mol.guide_sequence,
                   mol.passenger_sequence,
                   mol.seed_region,
                   mol.backbone_chemistry,
                   mol.sugar_modification,
                   mol.base_modification,
                   mol.conjugate_delivery,
                   mol.sequence_annotation_status,
                   mol.modification_annotation_status,
                   (
                        SELECT validation_status
                        FROM curation_audit AS audit
                        WHERE audit.entity_table = 'toxicity_endpoint'
                          AND audit.entity_id = tox.id
                          AND audit.curator_decision = 'accept'
                        ORDER BY audit.id
                        LIMIT 1
                   ) AS original_validation_status,
                   (
                        SELECT curator_decision
                        FROM curation_audit AS audit
                        WHERE audit.entity_table = 'toxicity_endpoint'
                          AND audit.entity_id = tox.id
                          AND audit.curator_decision = 'accept'
                        ORDER BY audit.id
                        LIMIT 1
                   ) AS original_curator_decision,
                   (
                        SELECT audit_note
                        FROM curation_audit AS audit
                        WHERE audit.entity_table = 'toxicity_endpoint'
                          AND audit.entity_id = tox.id
                          AND audit.curator_decision = 'accept'
                        ORDER BY audit.id
                        LIMIT 1
                   ) AS original_audit_note
            FROM toxicity_endpoint AS tox
            JOIN molecule AS mol ON mol.id = tox.molecule_id
            JOIN modality ON modality.id = mol.modality_id
            JOIN source_document AS source ON source.id = tox.source_document_id
            LEFT JOIN assay ON assay.id = tox.assay_id
            UNION ALL
            SELECT 'offtarget' AS evidence_domain,
                   'offtarget_evidence' AS entity_table,
                   off.id AS evidence_id,
                   off.evidence_grade,
                   CASE WHEN EXISTS (
                        SELECT 1 FROM benchmark_split AS split
                        WHERE split.entity_table = 'offtarget_evidence'
                          AND split.entity_id = off.id
                   ) THEN 'yes' ELSE 'no' END AS benchmark_eligible,
                   mol.id AS molecule_id,
                   mol.canonical_name,
                   modality.name AS modality,
                   mol.target_gene_symbol,
                   mol.disease_context,
                   off.evidence_type AS evidence_label,
                   off.source_document_id,
                   source.pmid,
                   source.pmcid,
                   source.doi,
                   source.title AS source_title,
                   source.source_url,
                   off.source_location,
                   off.assay_id,
                   assay.organism,
                   assay.model_system,
                   assay.cell_line_or_tissue,
                   assay.dose_value,
                   assay.dose_unit,
                   assay.exposure_time_value,
                   assay.exposure_time_unit,
                   assay.replicate_count,
                   mol.sense_sequence,
                   mol.antisense_sequence,
                   mol.guide_sequence,
                   mol.passenger_sequence,
                   mol.seed_region,
                   mol.backbone_chemistry,
                   mol.sugar_modification,
                   mol.base_modification,
                   mol.conjugate_delivery,
                   mol.sequence_annotation_status,
                   mol.modification_annotation_status,
                   (
                        SELECT validation_status
                        FROM curation_audit AS audit
                        WHERE audit.entity_table = 'offtarget_evidence'
                          AND audit.entity_id = off.id
                          AND audit.curator_decision = 'accept'
                        ORDER BY audit.id
                        LIMIT 1
                   ) AS original_validation_status,
                   (
                        SELECT curator_decision
                        FROM curation_audit AS audit
                        WHERE audit.entity_table = 'offtarget_evidence'
                          AND audit.entity_id = off.id
                          AND audit.curator_decision = 'accept'
                        ORDER BY audit.id
                        LIMIT 1
                   ) AS original_curator_decision,
                   (
                        SELECT audit_note
                        FROM curation_audit AS audit
                        WHERE audit.entity_table = 'offtarget_evidence'
                          AND audit.entity_id = off.id
                          AND audit.curator_decision = 'accept'
                        ORDER BY audit.id
                        LIMIT 1
                   ) AS original_audit_note
            FROM offtarget_evidence AS off
            JOIN molecule AS mol ON mol.id = off.molecule_id
            JOIN modality ON modality.id = mol.modality_id
            JOIN source_document AS source ON source.id = off.source_document_id
            LEFT JOIN assay ON assay.id = off.assay_id
        )
        ORDER BY CASE benchmark_eligible WHEN 'yes' THEN 0 ELSE 1 END,
                 CASE evidence_grade WHEN 'A' THEN 0 WHEN 'B' THEN 1 ELSE 2 END,
                 evidence_domain,
                 evidence_id
    """
    return [dict(row) for row in conn.execute(query).fetchall()]


def fetch_rejected_candidate_rows(conn: sqlite3.Connection) -> list[dict[str, object]]:
    conn.row_factory = sqlite3.Row
    query = """
        SELECT 'candidate_reject_control' AS item_type,
               candidate.evidence_domain,
               'curation_candidate' AS entity_table,
               candidate.id AS entity_id,
               candidate.suggested_evidence_grade AS evidence_grade,
               'no' AS benchmark_eligible,
               '' AS molecule_id,
               '' AS canonical_name,
               candidate.candidate_modality AS modality,
               '' AS target_gene_symbol,
               candidate.candidate_signal AS evidence_label,
               candidate.source_document_id,
               source.pmid,
               source.pmcid,
               source.doi,
               source.title AS source_title,
               source.source_url,
               candidate.source_location,
               candidate.matched_terms,
               candidate.curator_decision AS original_curator_decision,
               candidate.validation_status AS original_validation_status,
               (
                    SELECT audit_note
                    FROM curation_audit AS audit
                    WHERE audit.entity_table = 'curation_candidate'
                      AND audit.entity_id = candidate.id
                    ORDER BY audit.id
                    LIMIT 1
               ) AS original_audit_note
        FROM curation_candidate AS candidate
        JOIN source_document AS source ON source.id = candidate.source_document_id
        WHERE candidate.curator_decision = 'reject'
           OR candidate.validation_status = 'curator_rejected'
        ORDER BY candidate.evidence_domain, candidate.id
    """
    return [dict(row) for row in conn.execute(query).fetchall()]


def core_priority(row: dict[str, object]) -> str:
    if text(row.get("benchmark_eligible")) == "yes":
        return "P0"
    if text(row.get("evidence_grade")) in {"A", "B"}:
        return "P1"
    return "P2"


def build_core_packet(rows: list[dict[str, object]]) -> dict[str, object]:
    now = iso_now()
    output: list[dict[str, object]] = []
    missing_counts: Counter[str] = Counter()
    priority_counts: Counter[str] = Counter()

    for index, row in enumerate(rows, start=1):
        sequence_missing = not any(
            has_value(row.get(field))
            for field in ["sense_sequence", "antisense_sequence", "guide_sequence", "passenger_sequence"]
        )
        seed_missing = not has_value(row.get("seed_region"))
        modification_missing = not any(
            has_value(row.get(field))
            for field in ["backbone_chemistry", "sugar_modification", "base_modification"]
        )
        delivery_missing = not has_value(row.get("conjugate_delivery"))
        dose_missing = not (has_value(row.get("dose_value")) or has_value(row.get("dose_unit")))
        exposure_missing = not (
            has_value(row.get("exposure_time_value")) or has_value(row.get("exposure_time_unit"))
        )
        model_missing = not any(
            has_value(row.get(field))
            for field in ["organism", "model_system", "cell_line_or_tissue"]
        )
        flags = {
            "missing_sequence": sequence_missing,
            "missing_seed": seed_missing,
            "missing_modification": modification_missing,
            "missing_delivery": delivery_missing,
            "missing_dose": dose_missing,
            "missing_exposure": exposure_missing,
            "missing_model": model_missing,
        }
        for key, value in flags.items():
            if value:
                missing_counts[key] += 1
        priority = core_priority(row)
        priority_counts[priority] += 1
        item = {field: "" for field in CORE_FIELDS}
        for field in CORE_FIELDS:
            if field in row:
                item[field] = text(row[field])
        item.update(
            {
                "packet_row_id": f"core-field-{index:05d}",
                "priority": priority,
                "missing_sequence": bool_text(sequence_missing),
                "missing_seed": bool_text(seed_missing),
                "missing_modification": bool_text(modification_missing),
                "missing_delivery": bool_text(delivery_missing),
                "missing_dose": bool_text(dose_missing),
                "missing_exposure": bool_text(exposure_missing),
                "missing_model": bool_text(model_missing),
                "field_source_location": "",
                "field_source_quote_or_table_id": "",
                "source_location_verified": "",
                "curator_decision": "pending",
                "field_curator_id": "",
                "independent_reviewer_id": "",
                "review_status": "needs_core_field_curation",
                "audit_note": "",
                "do_not_fill_without_source": "TRUE",
                "updated_at": now,
            }
        )
        output.append(item)

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    with CORE_PACKET.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CORE_FIELDS)
        writer.writeheader()
        writer.writerows(output)

    summary = {
        "generated_at": now,
        "packet": str(CORE_PACKET),
        "rows": len(output),
        "priority_counts": dict(sorted(priority_counts.items())),
        "missing_counts": dict(sorted(missing_counts.items())),
        "policy": "This packet is a curation worklist. Empty sequence, modification, dose, exposure, or model fields must not be inferred without an exact source location.",
        "public_claim_boundary": "Until P0 rows are source-verified, the portal should claim verified safety/off-target evidence with provenance, not complete oligo sequence/modification coverage.",
    }
    CORE_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def existing_validation_decisions() -> dict[str, dict[str, str]]:
    if not VALIDATION_PACKET.exists():
        return {}
    with VALIDATION_PACKET.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            text(row.get("validation_sample_id")): {
                field: text(row.get(field))
                for field in [
                    "reviewer2_decision",
                    "reviewer2_evidence_grade",
                    "reviewer2_source_location_verified",
                    "reviewer2_error_type",
                    "reviewer2_note",
                    "adjudication_decision",
                    "adjudicator_note",
                ]
            }
            for row in reader
            if text(row.get("validation_sample_id"))
        }


def stratified_sample(
    rows: list[dict[str, object]],
    target: int,
    stratum_key,
    stable_id,
) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[stratum_key(row)].append(row)
    selected: list[dict[str, object]] = []
    for key in sorted(groups):
        group = sorted(groups[key], key=lambda row: hash_key(f"{key}:{stable_id(row)}"))
        quota = min(len(group), max(3, round((len(group) / max(len(rows), 1)) * target)))
        selected.extend(group[:quota])
    if len(selected) < target:
        selected_ids = {stable_id(row) for row in selected}
        remaining = [
            row
            for row in sorted(rows, key=lambda item: hash_key(f"fill:{stable_id(item)}"))
            if stable_id(row) not in selected_ids
        ]
        selected.extend(remaining[: target - len(selected)])
    return selected[:target]


def build_validation_packet(
    release_rows: list[dict[str, object]],
    rejected_rows: list[dict[str, object]],
) -> dict[str, object]:
    now = iso_now()
    existing = existing_validation_decisions()
    release_sample = stratified_sample(
        release_rows,
        target=min(250, len(release_rows)),
        stratum_key=lambda row: (
            f"release_accept/{text(row.get('entity_table'))}/"
            f"{text(row.get('evidence_grade'))}/{text(row.get('benchmark_eligible'))}"
        ),
        stable_id=lambda row: f"{text(row.get('entity_table'))}:{text(row.get('evidence_id'))}",
    )
    reject_sample = stratified_sample(
        rejected_rows,
        target=min(250, len(rejected_rows)),
        stratum_key=lambda row: (
            f"candidate_reject_control/{text(row.get('evidence_domain'))}/"
            f"{text(row.get('evidence_grade'))}/{text(row.get('modality'))}"
        ),
        stable_id=lambda row: f"curation_candidate:{text(row.get('entity_id'))}",
    )

    output: list[dict[str, str]] = []
    for index, row in enumerate(release_sample, start=1):
        sample_id = f"iv-release-{index:04d}"
        item = {field: "" for field in VALIDATION_FIELDS}
        item.update(
            {
                "validation_sample_id": sample_id,
                "item_type": "release_accept",
                "stratum": (
                    f"release_accept/{text(row.get('entity_table'))}/"
                    f"{text(row.get('evidence_grade'))}/{text(row.get('benchmark_eligible'))}"
                ),
                "entity_id": text(row.get("evidence_id")),
                "matched_terms": "",
                "do_not_change_release_until_adjudicated": "TRUE",
            }
        )
        for field in VALIDATION_FIELDS:
            if field in row:
                item[field] = text(row[field])
        item["original_curator_decision"] = text(row.get("original_curator_decision")) or "accept"
        item["original_validation_status"] = text(row.get("original_validation_status")) or "curator_verified"
        item.update(existing.get(sample_id, {}))
        output.append(item)

    for index, row in enumerate(reject_sample, start=1):
        sample_id = f"iv-reject-{index:04d}"
        item = {field: "" for field in VALIDATION_FIELDS}
        item.update(
            {
                "validation_sample_id": sample_id,
                "item_type": "candidate_reject_control",
                "stratum": (
                    f"candidate_reject_control/{text(row.get('evidence_domain'))}/"
                    f"{text(row.get('evidence_grade'))}/{text(row.get('modality'))}"
                ),
                "do_not_change_release_until_adjudicated": "TRUE",
            }
        )
        for field in VALIDATION_FIELDS:
            if field in row:
                item[field] = text(row[field])
        item.update(existing.get(sample_id, {}))
        output.append(item)

    with VALIDATION_PACKET.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=VALIDATION_FIELDS)
        writer.writeheader()
        writer.writerows(output)

    reviewed = [row for row in output if has_value(row.get("reviewer2_decision"))]
    comparable = [
        row
        for row in reviewed
        if text(row.get("reviewer2_decision")).lower() in {"accept", "reject"}
        and text(row.get("original_curator_decision")).lower() in {"accept", "reject"}
    ]
    agreement = None
    if comparable:
        agree = sum(
            1
            for row in comparable
            if text(row.get("reviewer2_decision")).lower()
            == text(row.get("original_curator_decision")).lower()
        )
        agreement = round(agree / len(comparable), 4)

    summary = {
        "generated_at": now,
        "packet": str(VALIDATION_PACKET),
        "sample_rows": len(output),
        "release_accept_rows": len(release_sample),
        "candidate_reject_control_rows": len(reject_sample),
        "reviewed_rows": len(reviewed),
        "comparable_rows": len(comparable),
        "raw_agreement": agreement,
        "claim_status": (
            "claimable_after_independent_review"
            if len(comparable) >= len(output) and agreement is not None
            else "not_claimable_until_independent_second_review_completed"
        ),
        "minimum_rule": "Complete reviewer2_decision on all sampled release_accept and candidate_reject_control rows before reporting inter-curator agreement or error rate.",
        "metrics_to_report_after_review": [
            "raw agreement",
            "Cohen kappa on accept/reject decisions",
            "false-accept rate among release_accept rows",
            "false-reject rate among candidate_reject_control rows",
            "grade-change rate among release_accept rows",
            "source-location disagreement rate",
        ],
    }
    VALIDATION_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        release_rows = fetch_release_rows(conn)
        rejected_rows = fetch_rejected_candidate_rows(conn)
    finally:
        conn.close()
    core = build_core_packet(release_rows)
    validation = build_validation_packet(release_rows, rejected_rows)
    print(f"core_rows={core['rows']} core_packet={CORE_PACKET}")
    print(f"validation_rows={validation['sample_rows']} validation_packet={VALIDATION_PACKET}")


if __name__ == "__main__":
    main()
