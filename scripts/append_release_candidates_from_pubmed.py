from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from build_curation_candidates import (
    KEYWORDS,
    best_location,
    candidate_signal,
    confidence_label,
    matched_terms,
    pubmed_records,
)
from generate_curation_queue import infer_modality


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "oligosafety.db"

DOMAINS = {"toxicity", "offtarget"}
CORE_OLIGO_TERMS = [
    "oligonucleotide",
    "antisense",
    "aso",
    "sirna",
    "rnai",
    "shrna",
    "gapmer",
    "galnac",
    "lnp",
    "lipid nanoparticle",
    "rna interference",
    "small interfering rna",
    "nucleic acid",
    "morpholino",
]


def source_rows(min_source_id: int | None) -> list[sqlite3.Row]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        clause = "AND id >= ?" if min_source_id is not None else ""
        params = (min_source_id,) if min_source_id is not None else ()
        return list(
            conn.execute(
                f"""
                SELECT id, source_type, pmid, doi, title
                FROM source_document
                WHERE source_type NOT IN ('nar_guideline', 'nar_editorial', 'closest_work')
                  AND pmid IS NOT NULL
                  AND pmid != ''
                  {clause}
                ORDER BY id
                """,
                params,
            )
        )
    finally:
        conn.close()


def existing_source_domains() -> set[tuple[int, str]]:
    conn = sqlite3.connect(DB_PATH)
    try:
        return {
            (int(row[0]), str(row[1]))
            for row in conn.execute(
                """
                SELECT source_document_id, evidence_domain
                FROM curation_candidate
                WHERE evidence_domain IN ('toxicity', 'offtarget')
                """
            )
        }
    finally:
        conn.close()


def max_ids() -> tuple[int, int]:
    conn = sqlite3.connect(DB_PATH)
    try:
        queue_id = int(conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM curation_queue").fetchone()[0])
        candidate_id = int(
            conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM curation_candidate").fetchone()[0]
        )
        return queue_id, candidate_id
    finally:
        conn.close()


def has_core_oligo_context(text: str) -> bool:
    lower = text.lower()
    return any(term in lower for term in CORE_OLIGO_TERMS)


def domain_has_terms(domain: str, title: str, sentences: list[str]) -> bool:
    if matched_terms(title, domain):
        return True
    return any(matched_terms(sentence, domain) for sentence in sentences)


def build_rows(
    sources: list[sqlite3.Row],
    domains: set[str],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    existing = existing_source_domains()
    records = pubmed_records(sorted({str(row["pmid"]) for row in sources if row["pmid"]}))
    next_queue_id, next_candidate_id = max_ids()
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    queue_rows: list[dict[str, object]] = []
    candidate_rows: list[dict[str, object]] = []

    for source in sources:
        pmid = str(source["pmid"] or "")
        record = records.get(pmid, {})
        title = str(record.get("title") or source["title"] or "")
        sentences = list(record.get("sentences") or [])
        context = " ".join([title, *sentences])
        if not has_core_oligo_context(context):
            continue
        modality = infer_modality(context)
        for domain in sorted(domains):
            source_id = int(source["id"])
            if (source_id, domain) in existing:
                continue
            if not domain_has_terms(domain, title, sentences):
                continue
            location, terms, _ = best_location(domain, title, sentences)
            if not terms:
                terms = matched_terms(context, domain)
            if not terms:
                continue
            grade = "B" if domain == "offtarget" or confidence_label(location, terms) != "low_candidate" else "C"
            queue_rows.append(
                {
                    "id": next_queue_id,
                    "source_document_id": source_id,
                    "pmid": pmid,
                    "doi": source["doi"] or "",
                    "source_title": title,
                    "source_type": source["source_type"],
                    "candidate_modality": modality,
                    "evidence_domain": domain,
                    "extraction_target": (
                        "toxicity_endpoint_and_direction"
                        if domain == "toxicity"
                        else "transcriptome_or_seed_offtarget_evidence"
                    ),
                    "suggested_evidence_grade": grade,
                    "priority": "high" if confidence_label(location, terms) == "high_candidate" else "medium",
                    "queue_status": "candidate",
                    "curator_id": "",
                    "created_at": created_at,
                }
            )
            candidate_rows.append(
                {
                    "id": next_candidate_id,
                    "queue_id": next_queue_id,
                    "source_document_id": source_id,
                    "pmid": pmid,
                    "doi": source["doi"] or "",
                    "evidence_domain": domain,
                    "candidate_modality": modality,
                    "source_location": location,
                    "matched_terms": ";".join(terms),
                    "candidate_signal": candidate_signal(domain, terms, title),
                    "suggested_evidence_grade": grade,
                    "confidence_label": confidence_label(location, terms),
                    "extraction_method": "rule_based_pubmed_abstract_release_append_v1",
                    "validation_status": "candidate_needs_curator_review",
                    "curator_decision": "pending",
                    "redistribution_level": "derived_annotations_only",
                    "created_at": created_at,
                }
            )
            next_queue_id += 1
            next_candidate_id += 1
    return queue_rows, candidate_rows


def load_rows(
    queue_rows: list[dict[str, object]],
    candidate_rows: list[dict[str, object]],
    dry_run: bool,
) -> None:
    if dry_run or not candidate_rows:
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        queue_columns = list(queue_rows[0].keys())
        candidate_columns = list(candidate_rows[0].keys())
        conn.executemany(
            f"INSERT INTO curation_queue ({', '.join(queue_columns)}) VALUES ({', '.join('?' for _ in queue_columns)})",
            [[row[column] for column in queue_columns] for row in queue_rows],
        )
        conn.executemany(
            f"INSERT INTO curation_candidate ({', '.join(candidate_columns)}) VALUES ({', '.join('?' for _ in candidate_columns)})",
            [[row[column] for column in candidate_columns] for row in candidate_rows],
        )
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-source-id", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--domains", default="toxicity,offtarget")
    args = parser.parse_args()

    domains = {item.strip() for item in args.domains.split(",") if item.strip()}
    unknown = domains - DOMAINS
    if unknown:
        raise SystemExit(f"unknown domains: {sorted(unknown)}")

    sources = source_rows(args.min_source_id)
    queue_rows, candidate_rows = build_rows(sources, domains)
    load_rows(queue_rows, candidate_rows, args.dry_run)
    toxicity = sum(1 for row in candidate_rows if row["evidence_domain"] == "toxicity")
    offtarget = sum(1 for row in candidate_rows if row["evidence_domain"] == "offtarget")
    print(
        " ".join(
            [
                f"release_candidate_append={len(candidate_rows)}",
                f"toxicity={toxicity}",
                f"offtarget={offtarget}",
                f"dry_run={args.dry_run}",
            ]
        )
    )


if __name__ == "__main__":
    main()
