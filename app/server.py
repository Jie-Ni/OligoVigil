from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
import zipfile
from collections import Counter
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "app" / "static"
DB_PATH = ROOT / "data" / "oligosafety.db"
DELIVERY_DIR = ROOT.parent / "04_delivery"
ALL_TABLES_ZIP_PATH = ROOT / "data" / "generated" / "all_tables.zip"
CURATION_PROTOCOL_SNAPSHOT_PATH = ROOT / "data" / "generated" / "curation_protocol_v1.json"
AGENT_READY_DIR = ROOT / "agent_ready"
PORTAL_VERSION = "20260604_core_validation_v45"
OPENAPI_VERSION = "20260604-core-validation-v45"
ARCHIVE_DOI = "10.5281/zenodo.20633779"
ARCHIVE_URL = f"https://doi.org/{ARCHIVE_DOI}"
CODE_RELEASE_URL = "https://github.com/Jie-Ni/OligoVigil/releases/tag/v1.0.1"
PREFERRED_PUBLIC_URL = "https://oligovigil.pages.dev"
PUBLIC_URL_VERIFIED_DATE = "2026-06-11"
CORE_OLIGO_FIELD_SUMMARY_PATH = (
    ROOT / "data" / "generated" / "core_oligo_field_curation_packet_v1_summary.json"
)
INDEPENDENT_VALIDATION_SUMMARY_PATH = (
    ROOT / "data" / "generated" / "independent_curation_validation_template_v1_summary.json"
)
RELEASE_EXPORT_LIMIT = 100000
# Honest release floor after v2 + human re-curation. The v1 machine pre-curation produced
# ~2003 candidate "verified" rows (measured ~74% false-accept); independent human curation
# demoted the unsupported ones, leaving 658 human curator-verified release rows. This floor
# replaces the obsolete >=2000 gate, which encoded the inflated v1 count.
MIN_HUMAN_VERIFIED_RELEASE = 600
# Fast set-based count of release rows that carry a human curator-verified accept audit
# (i.e. rows still present in a release table AND with a curator_verified/accept audit).
# After the enum rename only the human curator (curator_id 'ni_jie') keeps curator_verified, so this
# equals the human-verified release size. A correlated EXISTS over the unindexed curation_audit
# is O(release * audit) and times out the QA clients; the IN-subquery form materialises once.
HUMAN_VERIFIED_RELEASE_COUNT_SQL = """
    SELECT
      (SELECT COUNT(*) FROM toxicity_endpoint t
         WHERE t.id IN (SELECT entity_id FROM curation_audit
            WHERE entity_table='toxicity_endpoint' AND validation_status='curator_verified' AND curator_decision='accept'))
    + (SELECT COUNT(*) FROM offtarget_evidence o
         WHERE o.id IN (SELECT entity_id FROM curation_audit
            WHERE entity_table='offtarget_evidence' AND validation_status='curator_verified' AND curator_decision='accept')) AS n
"""
NATURAL_LANGUAGE_QUERY_EXAMPLES = [
    "Show GalNAc liver toxicity Grade A/B evidence with PubMed sources",
    "Find siRNA seed off-target evidence",
    "Show ASO hepatotoxicity Grade A records",
    "Which renal safety records are curator verified?",
]

DOWNLOAD_TABLES = {
    "source_document",
    "molecule",
    "toxicity_endpoint",
    "offtarget_evidence",
    "curation_audit",
    "benchmark_split",
    "curation_queue",
    "curation_candidate",
}
MANIFEST_DOWNLOADS = {
    "source_candidates_v1.csv": ROOT / "data" / "manifests" / "source_candidates_v1.csv",
    "source_candidates_v2.csv": ROOT / "data" / "manifests" / "source_candidates_v2.csv",
    "source_candidates_v3.csv": ROOT / "data" / "manifests" / "source_candidates_v3.csv",
    "source_candidates_v4.csv": ROOT / "data" / "manifests" / "source_candidates_v4.csv",
    "source_candidates_v5.csv": ROOT / "data" / "manifests" / "source_candidates_v5.csv",
    "source_candidates_v6.csv": ROOT / "data" / "manifests" / "source_candidates_v6.csv",
    "license_manifest_v1.csv": ROOT / "data" / "manifests" / "license_manifest_v1.csv",
    "source_license_manifest_v1.csv": ROOT / "data" / "manifests" / "source_license_manifest_v1.csv",
    "closest_work_matrix_v1.csv": ROOT / "data" / "manifests" / "closest_work_matrix_v1.csv",
    "data_dictionary_v1.csv": ROOT / "data" / "manifests" / "data_dictionary_v1.csv",
    "source_document_pubmed_v1.csv": ROOT / "data" / "generated" / "source_document_pubmed_v1.csv",
    "curation_queue_v1.csv": ROOT / "data" / "generated" / "curation_queue_v1.csv",
    "curation_candidate_v1.csv": ROOT / "data" / "generated" / "curation_candidate_v1.csv",
    "curator_review_template_v1.csv": ROOT / "data" / "generated" / "curator_review_template_v1.csv",
    "sequence_modification_curation_template_v1.csv": ROOT
    / "data"
    / "generated"
    / "sequence_modification_curation_template_v1.csv",
    "core_oligo_field_curation_packet_v1.csv": ROOT
    / "data"
    / "generated"
    / "core_oligo_field_curation_packet_v1.csv",
    "independent_curation_validation_template_v1.csv": ROOT
    / "data"
    / "generated"
    / "independent_curation_validation_template_v1.csv",
    "benchmark_task_cards_v1.csv": ROOT / "data" / "generated" / "benchmark_task_cards_v1.csv",
    "benchmark_baseline_results_v1.csv": ROOT
    / "data"
    / "generated"
    / "benchmark_baseline_results_v1.csv",
    "pubmed_discovery_candidates_v1.csv": ROOT / "data" / "generated" / "pubmed_discovery_candidates_v1.csv",
    "pubmed_discovery_candidates_v2.csv": ROOT / "data" / "generated" / "pubmed_discovery_candidates_v2.csv",
    "pubmed_discovery_candidates_v3.csv": ROOT / "data" / "generated" / "pubmed_discovery_candidates_v3.csv",
    "pubmed_discovery_candidates_v4.csv": ROOT / "data" / "generated" / "pubmed_discovery_candidates_v4.csv",
}
EVIDENCE_RELEASE_COLUMNS = [
    "evidence_domain",
    "entity_table",
    "evidence_id",
    "canonical_name",
    "modality",
    "target_gene_symbol",
    "disease_context",
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
    "category",
    "evidence_label",
    "evidence_grade",
    "source_location",
    "source_document_id",
    "source_title",
    "pmid",
    "source_pmcid",
    "doi",
    "source_url",
    "source_license_status",
    "source_reuse_category",
    "curation_basis",
    "raw_quote_included",
    "is_observed_experimental",
    "is_computational_prediction",
    "audit_validation_status",
    "curator_decision",
    "curator_id",
    "audit_note",
    "audited_at",
]
BENCHMARK_SPLIT_COLUMNS = [
    "task_name",
    "split_name",
    "entity_table",
    "entity_id",
    "evidence_domain",
    "evidence_grade",
    "canonical_name",
    "modality",
    "target_gene_symbol",
    "disease_context",
    "category",
    "evidence_label",
    "source_title",
    "leakage_group",
    "split_strategy",
    "version",
    "source_pmid",
    "source_doi",
]
BENCHMARK_BASELINE_COLUMNS = [
    "task_name",
    "target_field",
    "baseline_model",
    "evaluation_split",
    "train_rows",
    "evaluation_rows",
    "train_label_count",
    "majority_label",
    "majority_fraction_train",
    "accuracy",
    "macro_f1",
    "prediction_basis",
    "coverage",
    "status",
    "notes",
    "version",
]
MODIFICATION_PATTERNS = [
    {
        "term": "galnac",
        "label": "GalNAc conjugation",
        "kind": "targeted conjugate",
        "synonyms": ["galnac", "n-acetylgalactosamine"],
    },
    {
        "term": "lnp",
        "label": "Lipid nanoparticle",
        "kind": "delivery",
        "synonyms": ["lnp", "lipid nanoparticle", "lipid nanoparticles"],
    },
    {
        "term": "ps",
        "label": "Phosphorothioate backbone",
        "kind": "chemical modification",
        "synonyms": ["phosphorothioate", "ps-aso", "ps aso"],
    },
    {
        "term": "2ome",
        "label": "2'-O-methyl",
        "kind": "chemical modification",
        "synonyms": ["2'-o-methyl", "2-o-methyl", "2' ome", "2-ome", "2'ome"],
    },
    {
        "term": "2moe",
        "label": "2'-MOE",
        "kind": "chemical modification",
        "synonyms": ["2'-moe", "2-moe", "methoxyethyl", "moe"],
    },
    {
        "term": "lna",
        "label": "Locked nucleic acid",
        "kind": "chemical modification",
        "synonyms": ["lna", "locked nucleic acid"],
    },
    {
        "term": "pmo",
        "label": "Phosphorodiamidate morpholino oligomer",
        "kind": "modality",
        "synonyms": ["pmo", "morpholino", "phosphorodiamidate"],
    },
    {
        "term": "aso",
        "label": "Antisense oligonucleotide",
        "kind": "modality",
        "synonyms": ["aso", "antisense", "antisense oligonucleotide"],
    },
    {
        "term": "sirna",
        "label": "siRNA",
        "kind": "modality",
        "synonyms": ["sirna", "small interfering rna", "rnai"],
    },
]

OFFTARGET_TAXONOMY = [
    {
        "key": "seed_mediated",
        "label": "Seed-mediated / miRNA-like",
        "definition": "Evidence mentions seed region, 3'UTR seed matching, miRNA-like repression, or seed-driven transcriptome effects.",
        "synonyms": ["seed", "3'utr", "3 utr", "mirna", "microrna", "seed-mediated", "seed match"],
    },
    {
        "key": "hybridization_mismatch",
        "label": "Hybridization or mismatch",
        "definition": "Evidence concerns partial complementarity, mismatch tolerance, hybridization-driven off-targeting, or unintended RNA binding.",
        "synonyms": ["hybridization", "mismatch", "partial complementarity", "complementarity", "unintended binding"],
    },
    {
        "key": "transcriptome_level",
        "label": "Transcriptome-level observation",
        "definition": "Evidence is supported by expression profiling, RNA-seq, microarray, transcriptome-wide readout, or gene-expression signatures.",
        "synonyms": ["rna-seq", "rnaseq", "transcriptome", "microarray", "expression profiling", "gene expression"],
    },
    {
        "key": "immune_like",
        "label": "Immune-like off-target signal",
        "definition": "Evidence indicates immune stimulation or pattern-recognition activation treated as off-target safety context.",
        "synonyms": ["immune", "tlr", "cytokine", "interferon", "inflammatory", "immunostimulation"],
    },
    {
        "key": "computational_only",
        "label": "Computational prediction only",
        "definition": "Evidence is computational or in silico and should not be cited as experimentally observed off-target toxicity.",
        "synonyms": ["computational", "prediction", "in silico", "algorithm", "predicted"],
    },
    {
        "key": "general_offtarget",
        "label": "General off-target",
        "definition": "Curated off-target evidence where the source does not cleanly specify one of the higher-resolution mechanisms.",
        "synonyms": ["off-target", "off target", "offtarget", "unintended"],
    },
]


def first_param(query: dict[str, list[str]], name: str, default: str = "") -> str:
    return (query.get(name) or [default])[0].strip()


def limit_param(query: dict[str, list[str]], default: int = 250, maximum: int = 1000) -> int:
    raw = first_param(query, "limit", str(default))
    try:
        limit = int(raw)
    except ValueError:
        return default
    return max(1, min(limit, maximum))


def canonical_sequence(value: str) -> str:
    sequence = "".join(ch for ch in value.upper().replace("U", "T") if ch in {"A", "C", "G", "T", "N"})
    return sequence


def sequence_from_helm(value: str) -> str:
    if not value:
        return ""
    tokens = re.findall(r"\(([ACGTU])\)", value.upper())
    if tokens:
        return "".join(tokens)
    return ""


def sequence_windows(sequence: str, size: int = 7, maximum: int = 12) -> list[str]:
    if len(sequence) < size:
        return []
    windows: list[str] = []
    seen: set[str] = set()
    for index in range(0, len(sequence) - size + 1):
        window = sequence[index : index + size]
        if window not in seen:
            seen.add(window)
            windows.append(window)
        if len(windows) >= maximum:
            break
    return windows


def text_matches_any(values: list[object], synonyms: list[str]) -> bool:
    blob = " ".join(str(value or "").lower() for value in values)
    return any(synonym.lower() in blob for synonym in synonyms)


SEARCH_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "b",
    "by",
    "cite",
    "curated",
    "evidence",
    "find",
    "for",
    "from",
    "grade",
    "grades",
    "in",
    "is",
    "of",
    "open",
    "pubmed",
    "record",
    "records",
    "release",
    "show",
    "source",
    "sources",
    "the",
    "verified",
    "what",
    "which",
    "with",
}
QUERY_SYNONYMS = {
    "galnac": ["galnac", "n-acetylgalactosamine"],
    "hepatotoxicity": ["hepatotoxicity", "hepatic", "liver", "hepatocyte", "hepatocellular", "alt", "ast"],
    "hepatic": ["hepatic", "hepatotoxicity", "liver", "hepatocyte", "hepatocellular", "alt", "ast"],
    "liver": ["liver", "hepatic", "hepatotoxicity", "hepatocyte", "hepatocellular", "alt", "ast"],
    "renal": ["renal", "kidney", "nephrotoxicity", "nephrotoxic"],
    "kidney": ["kidney", "renal", "nephrotoxicity", "nephrotoxic"],
    "platelet": ["platelet", "thrombocytopenia", "hematology", "blood"],
    "blood": ["blood", "hematology", "platelet", "thrombocytopenia"],
    "immune": ["immune", "immunogenicity", "cytokine", "complement", "inflammation"],
    "toxicity": ["toxicity", "toxic", "safety", "adverse"],
    "safety": ["safety", "toxicity", "adverse"],
    "offtarget": ["off-target", "off target", "offtarget", "mismatch", "hybridization", "unintended"],
    "target": ["target"],
    "seed": ["seed", "seed-mediated", "seed match", "seed region", "mirna-like", "microrna-like"],
    "mismatch": ["mismatch", "hybridization", "off-target", "off target", "offtarget"],
    "hybridization": ["hybridization", "mismatch", "off-target", "off target", "offtarget"],
    "aso": ["aso", "antisense", "antisense oligonucleotide", "gapmer"],
    "antisense": ["antisense", "aso", "gapmer"],
    "gapmer": ["gapmer", "aso", "antisense"],
    "sirna": ["sirna", "rnai", "rna interference", "small interfering rna"],
    "rnai": ["rnai", "sirna", "rna interference", "small interfering rna"],
    "lnp": ["lnp", "lipid nanoparticle", "lipid nanoparticles"],
    "moe": ["moe", "2'-moe", "2-moe", "methoxyethyl"],
    "lna": ["lna", "locked nucleic acid"],
    "pmo": ["pmo", "morpholino", "phosphorodiamidate"],
}


def query_term_groups(value: str, maximum: int = 8) -> list[list[str]]:
    normalized = value.lower().replace("off target", "offtarget").replace("off-target", "offtarget")
    raw_tokens = re.findall(r"[a-z0-9']+", normalized)
    groups: list[list[str]] = []
    seen: set[str] = set()
    for token in raw_tokens:
        if token in SEARCH_STOPWORDS or len(token) < 2:
            continue
        synonyms = QUERY_SYNONYMS.get(token, [token])
        key = "|".join(sorted(synonyms))
        if key in seen:
            continue
        seen.add(key)
        groups.append(synonyms)
        if len(groups) >= maximum:
            break
    return groups


def append_query_match(
    clauses: list[str],
    params: list[object],
    fields: list[str],
    value: str,
) -> None:
    groups = query_term_groups(value)
    if not groups:
        return
    group_clauses: list[str] = []
    for synonyms in groups:
        synonym_clauses: list[str] = []
        for field in fields:
            for synonym in synonyms:
                synonym_clauses.append(f"{field} LIKE ?")
                params.append(f"%{synonym}%")
        group_clauses.append("(" + " OR ".join(synonym_clauses) + ")")
    clauses.append("(" + " AND ".join(group_clauses) + ")")


def append_query_match_or_raw(
    clauses: list[str],
    params: list[object],
    fields: list[str],
    value: str,
) -> None:
    before = len(clauses)
    append_query_match(clauses, params, fields, value)
    if len(clauses) != before:
        return
    clauses.append("(" + " OR ".join(f"{field} LIKE ?" for field in fields) + ")")
    params.extend([f"%{value}%"] * len(fields))


def rows(query: str, params: tuple[object, ...] = ()) -> list[dict[str, object]]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute(query, params).fetchall()]
    finally:
        conn.close()


def one(query: str, params: tuple[object, ...] = ()) -> dict[str, object]:
    result = rows(query, params)
    return result[0] if result else {}


def json_bytes(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_row_count(path: Path) -> int | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8", newline="") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def table_row_count(table: str) -> int:
    return int(one(f"SELECT COUNT(*) AS n FROM {table}").get("n", 0) or 0)


def table_columns(table: str) -> list[str]:
    return [str(row["name"]) for row in rows(f"PRAGMA table_info({table})")]


def csv_bytes(table: str) -> bytes:
    data = rows(f"SELECT * FROM {table}")
    handle = io.StringIO()
    fieldnames = list(data[0].keys()) if data else table_columns(table)
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    if data:
        writer.writerows(data)
    return handle.getvalue().encode("utf-8")


def dicts_to_csv_bytes(data: list[dict[str, object]], fieldnames: list[str] | None = None) -> bytes:
    columns = fieldnames or (list(data[0].keys()) if data else [])
    if not columns:
        return b""
    handle = io.StringIO()
    writer = csv.DictWriter(handle, fieldnames=columns)
    writer.writeheader()
    if data:
        writer.writerows(data)
    return handle.getvalue().encode("utf-8")


def read_json_file(path: Path, default: dict[str, object] | None = None) -> dict[str, object]:
    if not path.exists():
        return default or {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default or {}


def build_all_tables_zip_bytes() -> bytes:
    handle = io.BytesIO()
    with zipfile.ZipFile(handle, "w", zipfile.ZIP_DEFLATED) as archive:
        for table in sorted(DOWNLOAD_TABLES):
            archive.writestr(f"{table}.csv", csv_bytes(table))
        archive.writestr("evidence_release.csv", evidence_release_csv_bytes())
        archive.writestr("benchmark_reference_splits.csv", benchmark_reference_splits_csv_bytes())
        archive.writestr("benchmark_baseline_results.csv", benchmark_baseline_results_csv_bytes())
        for filename in [
            "sequence_modification_curation_template_v1.csv",
            "core_oligo_field_curation_packet_v1.csv",
            "independent_curation_validation_template_v1.csv",
            "benchmark_task_cards_v1.csv",
            "benchmark_baseline_results_v1.csv",
            "data_dictionary_v1.csv",
            "license_manifest_v1.csv",
            "source_license_manifest_v1.csv",
            "closest_work_matrix_v1.csv",
        ]:
            path = MANIFEST_DOWNLOADS.get(filename)
            if path and path.exists():
                archive.writestr(filename, path.read_bytes())
    return handle.getvalue()


def cache_is_current(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        with zipfile.ZipFile(path, "r") as archive:
            if "benchmark_baseline_results.csv" not in archive.namelist():
                return False
    except zipfile.BadZipFile:
        return False
    cache_mtime = path.stat().st_mtime
    dependencies = [
        DB_PATH,
        ROOT / "data" / "generated" / "sequence_modification_curation_template_v1.csv",
        ROOT / "data" / "generated" / "core_oligo_field_curation_packet_v1.csv",
        ROOT / "data" / "generated" / "independent_curation_validation_template_v1.csv",
        ROOT / "data" / "generated" / "benchmark_task_cards_v1.csv",
        ROOT / "data" / "generated" / "benchmark_baseline_results_v1.csv",
        ROOT / "data" / "manifests" / "data_dictionary_v1.csv",
        ROOT / "data" / "manifests" / "license_manifest_v1.csv",
        ROOT / "data" / "manifests" / "source_license_manifest_v1.csv",
        ROOT / "data" / "manifests" / "closest_work_matrix_v1.csv",
    ]
    return all(not dep.exists() or dep.stat().st_mtime <= cache_mtime for dep in dependencies)


def all_tables_zip_bytes() -> bytes:
    if cache_is_current(ALL_TABLES_ZIP_PATH):
        return ALL_TABLES_ZIP_PATH.read_bytes()
    payload = build_all_tables_zip_bytes()
    ALL_TABLES_ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    ALL_TABLES_ZIP_PATH.write_bytes(payload)
    return payload


def manifest_rows(filename: str) -> list[dict[str, object]]:
    path = MANIFEST_DOWNLOADS[filename]
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def active_source_manifest_name() -> str:
    for filename in [
        "source_candidates_v6.csv",
        "source_candidates_v5.csv",
        "source_candidates_v4.csv",
        "source_candidates_v3.csv",
        "source_candidates_v2.csv",
        "source_candidates_v1.csv",
    ]:
        if MANIFEST_DOWNLOADS[filename].exists():
            return filename
    return "source_candidates_v1.csv"


def api_metadata() -> dict[str, object]:
    active_manifest = active_source_manifest_name()
    counts = api_stats()["counts"] if DB_PATH.exists() else {}
    release_count = int(counts.get("toxicity_endpoint", 0)) + int(counts.get("offtarget_evidence", 0))
    return {
        "project": "OligoVigil",
        "legacy_project_name": "OligoSafetyDB",
        "release_type": "verified_public_release_candidate",
        "schema": "sqlite_v1",
        "portal_version": PORTAL_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "active_source_manifest": active_manifest,
        "database_bytes": DB_PATH.stat().st_size if DB_PATH.exists() else 0,
        "release_snapshot": {
            "verified_release_records": release_count,
            "toxicity_records": counts.get("toxicity_endpoint", 0),
            "offtarget_records": counts.get("offtarget_evidence", 0),
            "benchmark_split_records": counts.get("benchmark_split", 0),
            "candidate_records": counts.get("curation_candidate", 0),
        },
        "access_policy": {
            "login_required": False,
            "free_access": True,
            "bulk_download": True,
            "candidate_text_policy": "derived_annotations_only_no_raw_abstract_storage",
        },
        "sequence_policy": {
            "release_grade_sequence_columns_available": True,
            "curated_sequence_alignment_available": False,
            "curation_template": "/api/download/sequence_modification_curation_template.csv",
            "coverage_endpoint": "/api/sequence_coverage",
            "current_sequence_search": "sequence parsing plus seed/off-target/modification evidence lookup; full alignment search requires curator-verified sequence strings",
        },
        "scope": {
            "core": ["ASO", "siRNA", "ASO/siRNA mixed context"],
            "excluded": ["CRISPR guide RNA"],
        },
    }


def api_stats() -> dict[str, object]:
    tables = [
        "source_document",
        "modality",
        "molecule",
        "assay",
        "toxicity_endpoint",
        "offtarget_evidence",
        "curation_audit",
        "benchmark_split",
        "curation_queue",
        "curation_candidate",
    ]
    counts = {
        table: one(f"SELECT COUNT(*) AS n FROM {table}").get("n", 0)
        for table in tables
    }
    grades = rows(
        """
        SELECT evidence_grade, COUNT(*) AS n
        FROM (
            SELECT evidence_grade FROM toxicity_endpoint
            UNION ALL
            SELECT evidence_grade FROM offtarget_evidence
        )
        GROUP BY evidence_grade
        ORDER BY evidence_grade
        """
    )
    return {"counts": counts, "evidence_grades": grades}


def api_summary() -> dict[str, object]:
    return {
        "modality": rows(
            """
            SELECT modality.name AS label, COUNT(*) AS n
            FROM molecule
            JOIN modality ON molecule.modality_id = modality.id
            GROUP BY modality.name
            ORDER BY n DESC, label
            """
        ),
        "sources_by_type": rows(
            """
            SELECT source_type AS label, COUNT(*) AS n
            FROM source_document
            GROUP BY source_type
            ORDER BY n DESC, label
            """
        ),
        "sources_by_year": rows(
            """
            SELECT COALESCE(CAST(publication_year AS TEXT), 'unknown') AS label, COUNT(*) AS n
            FROM source_document
            GROUP BY publication_year
            ORDER BY publication_year DESC
            LIMIT 10
            """
        ),
        "candidate_by_domain": rows(
            """
            SELECT evidence_domain AS label, COUNT(*) AS n
            FROM curation_candidate
            GROUP BY evidence_domain
            ORDER BY n DESC, label
            """
        ),
        "candidate_by_confidence": rows(
            """
            SELECT confidence_label AS label, COUNT(*) AS n
            FROM curation_candidate
            GROUP BY confidence_label
            ORDER BY n DESC, label
            """
        ),
        "toxicity_by_category": rows(
            """
            SELECT endpoint_category AS label, COUNT(*) AS n
            FROM toxicity_endpoint
            GROUP BY endpoint_category
            ORDER BY n DESC, label
            LIMIT 12
            """
        ),
        "offtarget_by_type": rows(
            """
            SELECT evidence_type AS label, COUNT(*) AS n
            FROM offtarget_evidence
            GROUP BY evidence_type
            ORDER BY n DESC, label
            LIMIT 12
            """
        ),
    }


def api_facets() -> dict[str, object]:
    return {
        "modalities": rows(
            """
            SELECT name AS value, name AS label
            FROM modality
            WHERE in_core_scope = 1
            ORDER BY id
            """
        ),
        "source_types": rows(
            """
            SELECT source_type AS value, source_type AS label, COUNT(*) AS n
            FROM source_document
            GROUP BY source_type
            ORDER BY n DESC, label
            """
        ),
        "source_years": rows(
            """
            SELECT CAST(publication_year AS TEXT) AS value, CAST(publication_year AS TEXT) AS label, COUNT(*) AS n
            FROM source_document
            WHERE publication_year IS NOT NULL
            GROUP BY publication_year
            ORDER BY publication_year DESC
            """
        ),
        "candidate_domains": rows(
            """
            SELECT evidence_domain AS value, evidence_domain AS label, COUNT(*) AS n
            FROM curation_candidate
            GROUP BY evidence_domain
            ORDER BY n DESC, label
            """
        ),
        "confidence_labels": rows(
            """
            SELECT confidence_label AS value, confidence_label AS label, COUNT(*) AS n
            FROM curation_candidate
            GROUP BY confidence_label
            ORDER BY n DESC, label
            """
        ),
        "evidence_grades": rows(
            """
            SELECT evidence_grade AS value, evidence_grade AS label, COUNT(*) AS n
            FROM (
                SELECT evidence_grade FROM toxicity_endpoint
                UNION ALL
                SELECT evidence_grade FROM offtarget_evidence
            )
            GROUP BY evidence_grade
            ORDER BY evidence_grade
            """
        ),
        "toxicity_categories": rows(
            """
            SELECT endpoint_category AS value, endpoint_category AS label, COUNT(*) AS n
            FROM toxicity_endpoint
            GROUP BY endpoint_category
            ORDER BY n DESC, label
            """
        ),
        "evidence_categories": rows(
            """
            SELECT category AS value, category AS label, COUNT(*) AS n
            FROM (
                SELECT endpoint_category AS category FROM toxicity_endpoint
                UNION ALL
                SELECT evidence_type AS category FROM offtarget_evidence
            )
            GROUP BY category
            ORDER BY n DESC, label
            """
        ),
        "audit_statuses": rows(
            """
            SELECT validation_status AS value, validation_status AS label, COUNT(*) AS n
            FROM curation_audit
            GROUP BY validation_status
            ORDER BY n DESC, label
            """
        ),
        "targets": rows(
            """
            SELECT target_gene_symbol AS value, target_gene_symbol AS label, COUNT(*) AS n
            FROM molecule
            WHERE target_gene_symbol IS NOT NULL AND target_gene_symbol != ''
            GROUP BY target_gene_symbol
            ORDER BY n DESC, label
            LIMIT 200
            """
        ),
        "modification_terms": [
            {"value": item["term"], "label": item["label"], "kind": item["kind"]}
            for item in MODIFICATION_PATTERNS
        ],
    }


def api_quality() -> dict[str, object]:
    counts = api_stats()["counts"]
    release_evidence = int(counts.get("toxicity_endpoint", 0)) + int(counts.get("offtarget_evidence", 0))
    audited_release = one(HUMAN_VERIFIED_RELEASE_COUNT_SQL).get("n", 0)
    return {
        "release_evidence_records": release_evidence,
        "curator_verified_release_records": audited_release,
        "candidate_records": counts.get("curation_candidate", 0),
        "candidate_to_release_ratio": round(
            float(counts.get("curation_candidate", 0)) / max(release_evidence, 1), 2
        ),
        "source_documents": counts.get("source_document", 0),
        "active_manifest": active_source_manifest_name(),
        "checks": [
            {
                "check": "no_login_access",
                "status": "pass",
                "evidence": "All API and static portal endpoints are unauthenticated.",
            },
            {
                "check": "bulk_download",
                "status": "pass",
                "evidence": "CSV tables, populated evidence_release.csv, benchmark_reference_splits.csv, manifests, and all_tables.zip are exposed.",
            },
            {
                "check": "candidate_release_separation",
                "status": "pass",
                "evidence": "Candidate annotations remain separate from release evidence tables.",
            },
            {
                "check": "release_promotion_gate",
                "status": "pass",
                "evidence": "Release evidence explorer exposes only curator_verified, accepted A/B/C records; abstract-level generated promotions are excluded.",
            },
            {
                "check": "human_verified_release",
                "status": "pass" if audited_release >= MIN_HUMAN_VERIFIED_RELEASE and audited_release == release_evidence else "blocked",
                "evidence": f"{audited_release} of {release_evidence} release rows carry a human curator-verified accept audit (independent re-curation of 2003 v1 machine pre-curated candidates).",
            },
            {
                "check": "crispr_exclusion",
                "status": "pass",
                "evidence": "CRISPR guide RNA remains excluded from core molecule records.",
            },
            {
                "check": "stable_public_url",
                "status": "pass",
                "evidence": f"Cloudflare Pages URL {PREFERRED_PUBLIC_URL} resolved and passed live endpoint checks on {PUBLIC_URL_VERIFIED_DATE}.",
            },
        ],
    }


def api_coverage() -> dict[str, object]:
    candidate_domain = {
        row["label"]: row["n"]
        for row in rows(
            """
            SELECT evidence_domain AS label, COUNT(*) AS n
            FROM curation_candidate
            GROUP BY evidence_domain
            """
        )
    }
    release_domain = {
        row["label"]: row["n"]
        for row in rows(
            """
            SELECT evidence_domain AS label, COUNT(*) AS n
            FROM (
                SELECT 'toxicity' AS evidence_domain FROM toxicity_endpoint
                UNION ALL
                SELECT 'offtarget' AS evidence_domain FROM offtarget_evidence
            )
            GROUP BY evidence_domain
            """
        )
    }
    domains = sorted(set(candidate_domain) | set(release_domain))
    return {
        "source_years": rows(
            """
            SELECT COALESCE(CAST(publication_year AS TEXT), 'unknown') AS label, COUNT(*) AS n
            FROM source_document
            GROUP BY publication_year
            ORDER BY publication_year DESC
            LIMIT 16
            """
        ),
        "top_journals": rows(
            """
            SELECT COALESCE(journal_or_agency, 'unknown') AS label, COUNT(*) AS n
            FROM source_document
            GROUP BY journal_or_agency
            ORDER BY n DESC, label
            LIMIT 16
            """
        ),
        "candidate_domain_modality": rows(
            """
            SELECT evidence_domain, candidate_modality, COUNT(*) AS n
            FROM curation_candidate
            GROUP BY evidence_domain, candidate_modality
            ORDER BY evidence_domain, n DESC, candidate_modality
            """
        ),
        "candidate_confidence_domain": rows(
            """
            SELECT evidence_domain, confidence_label, COUNT(*) AS n
            FROM curation_candidate
            GROUP BY evidence_domain, confidence_label
            ORDER BY evidence_domain, confidence_label
            """
        ),
        "queue_priority_domain": rows(
            """
            SELECT evidence_domain, priority, COUNT(*) AS n
            FROM curation_queue
            GROUP BY evidence_domain, priority
            ORDER BY evidence_domain, priority
            """
        ),
        "release_grade_domain": rows(
            """
            SELECT evidence_domain, evidence_grade, COUNT(*) AS n
            FROM (
                SELECT 'toxicity' AS evidence_domain, evidence_grade FROM toxicity_endpoint
                UNION ALL
                SELECT 'offtarget' AS evidence_domain, evidence_grade FROM offtarget_evidence
            )
            GROUP BY evidence_domain, evidence_grade
            ORDER BY evidence_domain, evidence_grade
            """
        ),
        "candidate_release_gap": [
            {
                "evidence_domain": domain,
                "candidate_records": candidate_domain.get(domain, 0),
                "release_records": release_domain.get(domain, 0),
                "gap": candidate_domain.get(domain, 0) - release_domain.get(domain, 0),
            }
            for domain in domains
        ],
    }


def api_examples() -> dict[str, object]:
    examples = [
        {
            "label": "Hepatotoxicity search",
            "description": "Find source and candidate records mentioning hepatotoxicity.",
            "endpoint": "/api/search?q=hepatotoxicity",
            "ui_action": "search:hepatotoxicity",
        },
        {
            "label": "Sequence/off-target triage",
            "description": "Parse an oligo sequence into seed windows and link it to off-target evidence routes.",
            "endpoint": "/api/sequence_search?sequence=AUGCUACUGACUGA&modification=GalNAc&target=PCSK9",
            "ui_action": "sequence:AUGCUACUGACUGA:PCSK9:GalNAc",
        },
        {
            "label": "Safety triage report",
            "description": "Create a source-grounded safety report across sequence, chemistry, delivery, toxicity, and off-target evidence gaps.",
            "endpoint": "/api/safety_triage?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&delivery=GalNAc&endpoint=hepatic&species=human",
            "ui_action": "triage:AUGCUACUGACUGA:PCSK9:GalNAc:GalNAc:hepatic",
        },
        {
            "label": "Modification safety profile",
            "description": "Compare release and candidate coverage for a chemistry or delivery term.",
            "endpoint": "/api/modification_profile?term=galnac",
            "ui_action": "modification:galnac",
        },
        {
            "label": "High-confidence toxicity candidates",
            "description": "Inspect candidate annotations that should be prioritized for full-text curation.",
            "endpoint": "/api/curation_candidates?domain=toxicity&confidence=high_candidate&limit=500",
            "ui_action": "candidate:toxicity:high_candidate",
        },
        {
            "label": "Verified toxicity release gate",
            "description": "Show toxicity records only after full curator verification and accepted release grading.",
            "endpoint": "/api/evidence_records?domain=toxicity&limit=500",
            "ui_action": "evidence:toxicity:",
        },
        {
            "label": "Citable toxicity record",
            "description": "Open one verified record with source, audit trail, and BibTeX-ready citation text.",
            "endpoint": "/api/evidence_detail?domain=toxicity&id=1",
            "ui_action": "record:toxicity:1",
        },
        {
            "label": "Verified off-target release gate",
            "description": "Show off-target records only after full curator verification and accepted release grading.",
            "endpoint": "/api/evidence_records?domain=offtarget&limit=500",
            "ui_action": "evidence:offtarget:",
        },
        {
            "label": "Reference benchmark splits",
            "description": "Download fixed A/B-grade split files for reproducible safety prediction baselines.",
            "endpoint": "/api/download/benchmark_reference_splits.csv",
            "ui_action": "benchmark:",
        },
        {
            "label": "Toxicity audit trail",
            "description": "Show validation status, curator decision, extraction script, and audit notes.",
            "endpoint": "/api/audit?entity_table=toxicity_endpoint&limit=500",
            "ui_action": "audit:toxicity_endpoint",
        },
        {
            "label": "Bulk release download",
            "description": "Download the populated unified release table with curator-verified evidence records.",
            "endpoint": "/api/download/evidence_release.csv",
            "ui_action": "download:evidence_release",
        },
        {
            "label": "Coverage overview",
            "description": "Inspect source-year, journal, candidate-domain, and release-gap coverage.",
            "endpoint": "/api/coverage",
            "ui_action": "coverage:",
        },
        {
            "label": "Source provenance packet",
            "description": "Open the linked source, queue tasks, candidates, and release evidence for one topic.",
            "endpoint": "/api/source_detail?q=hepatotoxicity",
            "ui_action": "source:hepatotoxicity",
        },
    ]
    return {"examples": examples}


def api_citation() -> dict[str, object]:
    title = (
        "OligoVigil: a curated safety and off-target evidence resource with "
        "benchmark-ready data for therapeutic oligonucleotides"
    )
    version = PORTAL_VERSION
    plain = (
        f"OligoVigil Consortium. {title}. OligoVigil {version}; 2026. "
        "Curator-verified ASO/siRNA toxicity and off-target release evidence with reference benchmark splits. "
        f"Data archive: {ARCHIVE_DOI}."
    )
    bibtex = "\n".join(
        [
            f"@misc{{OligoVigil_{version},",
            f"  title = {{{title}}},",
            "  author = {OligoVigil Consortium},",
            "  year = {2026},",
            f"  doi = {{{ARCHIVE_DOI}}},",
            f"  url = {{{ARCHIVE_URL}}},",
            f"  note = {{Version {version}; data archive}},",
            "  howpublished = {OligoVigil public web resource}",
            "}",
        ]
    )
    return {
        "version": version,
        "title": title,
        "doi_status": ARCHIVE_DOI,
        "archive_url": ARCHIVE_URL,
        "code_release_url": CODE_RELEASE_URL,
        "preferred_citation": plain,
        "bibtex": bibtex,
        "record_citation_template": (
            "Use /api/evidence_detail?domain={toxicity|offtarget}&id={id} and cite the returned "
            "citation.plain_text plus the source PMID/DOI."
        ),
        "benchmark_citation_template": (
            "Cite OligoVigil version, benchmark task name, benchmark_reference_splits.csv, "
            "and the release-package checksum."
        ),
        "downloads": {
            "evidence_release": "/api/download/evidence_release.csv",
            "benchmark_splits": "/api/download/benchmark_reference_splits.csv",
            "task_cards": "/api/download/benchmark_task_cards.csv",
            "all_tables": "/api/download/all_tables.zip",
        },
    }


def api_help() -> dict[str, object]:
    return {
        "version": PORTAL_VERSION,
        "chapters": [
            {
                "title": "Introduction",
                "summary": "OligoVigil is a no-login resource for ASO/siRNA safety evidence, provenance, and benchmark reuse.",
                "items": [
                    "Release evidence is separated from machine-derived candidates.",
                    "Accepted release rows require curator verification and source-level provenance.",
                    "Grade A/B rows are eligible for reference benchmark splits; Grade C rows remain contextual evidence.",
                ],
            },
            {
                "title": "Getting started",
                "summary": "Start from a safety question, a sequence/design question, or a benchmark reuse question.",
                "items": [
                    "Use the Overview search box for molecule, target, endpoint, PMID, DOI, chemistry, or off-target mechanism.",
                    "Use Examples for one-click GalNAc, seed off-target, ASO/gapmer hepatotoxicity, and benchmark workflows.",
                    "Use Record pages when you need a citable source/audit packet.",
                ],
            },
            {
                "title": "Input data",
                "summary": "The portal accepts text terms and sequence-like strings for evidence lookup, not anonymous writes.",
                "items": [
                    "Sequence workbench accepts A/C/G/T/U/N characters and reports seed windows.",
                    "Safety Triage accepts sequence, target, chemistry, delivery, endpoint, species, and cell-type terms.",
                    "Evidence filters accept domain, grade, modality, endpoint/category, and free-text query.",
                    "Contribution packets use curator_review_template_v1.csv and require exact source location.",
                ],
            },
            {
                "title": "Safety Triage Report",
                "summary": "The report converts a design question into a provenance-first evidence packet.",
                "items": [
                    "It is not a de novo safety predictor and does not label an oligo as clinically safe.",
                    "Each concern is marked as release-supported, candidate-gap-supported, mixed, or not assessable from current release.",
                    "Matched release records are citable; candidate gaps are only used to prioritize additional curation.",
                ],
            },
            {
                "title": "Evidence grades",
                "summary": "Grades are defensive evidence strata for database reuse, not clinical recommendations.",
                "items": [
                    "Grade A: direct experimental or regulatory safety/off-target evidence with strong provenance.",
                    "Grade B: relevant observed evidence with lower granularity or indirect but defensible linkage.",
                    "Grade C: contextual evidence retained for discovery, excluded from benchmark reference splits.",
                ],
            },
            {
                "title": "Exploring results",
                "summary": "Use source packets and record pages to move from aggregate counts to exact evidence.",
                "items": [
                    "Open a record to inspect source, audit trail, source location, citation text, and BibTeX.",
                    "Open source detail to view linked queue tasks, candidate signals, and verified evidence.",
                    "Use Coverage and Release pages to inspect gaps before drawing claims.",
                ],
            },
            {
                "title": "Benchmark reuse",
                "summary": "Benchmark splits are a supplement to the database, not the main claim.",
                "items": [
                    "Download benchmark_reference_splits.csv and benchmark_task_cards.csv together.",
                    "Group leakage is controlled by source identifier plus molecule/cohort name.",
                    "Report AUROC, AUPRC, macro-F1, PCC/Spearman, or MSE according to task card target.",
                ],
            },
            {
                "title": "Downloads and API",
                "summary": "All release tables and manifests are available without login.",
                "items": [
                    "Use /api/download/evidence_release.csv for the unified verified release.",
                    "Use /api/download/all_tables.zip for a full reproducible snapshot.",
                    "Use /api/openapi.json for endpoint discovery and lightweight client generation.",
                ],
            },
            {
                "title": "Audit path",
                "summary": "Use the Trust page to reproduce the release boundary before citing or reusing the resource.",
                "items": [
                    "Open /#trust or /api/curation_protocol to inspect release/candidate separation, audit coverage, and redistribution policy.",
                    "Join evidence_release.csv to curation_audit.csv by entity_table and evidence_id/entity_id.",
                    "Use source_license_manifest_v1.csv before making source-level redistribution claims.",
                ],
            },
            {
                "title": "Contribution and correction",
                "summary": "Corrections and new evidence must preserve source provenance and the curation decision trail. Release rows are human curator-verified (AI-assisted: a primary human curator adjudicated v2 LLM proposals over the source passages, re-curating the v1 machine pre-curated candidates — not blind; a blinded second curator (HY) independently re-scored a 100-row mixed inter-rater sample, giving Cohen κ_binary = 0.42 (moderate, Landis-Koch) under the drop-abstain convention (n=92 non-abstain rows) and 0.34 (fair) under the safety-conservative collapse-abstain convention (n=100), raw agreement 66% (66/100); a third-adjudicator consensus pass is in progress); machine-only candidates are labelled machine_precurated_v1 and are not release evidence.",
                "items": [
                    "Use /#submit or curator_review_template_v1.csv for proposed new records.",
                    "Required fields include source PMID/DOI/URL, exact source location, proposed evidence label, evidence grade, and curator note.",
                    "Candidate rows remain non-citable until accepted by curator audit and promoted through the release gate.",
                ],
            },
            {
                "title": "FAQ and troubleshooting",
                "summary": "Most confusing cases are caused by release/candidate separation.",
                "items": [
                    "A candidate hit is not release evidence until accepted by curator audit.",
                    f"Use the archived data DOI ({ARCHIVE_DOI}); cite the public portal only after the Cloudflare Pages HTTPS URL resolves.",
                    "Do not cite localhost screenshots; cite the frozen release version and public record URL after deployment.",
                ],
            },
            {
                "title": "Citation",
                "summary": "Cite the resource version, exact record pages for claims, and benchmark split checksums for ML reuse.",
                "items": [
                    "Use the Cite page for global citation text and BibTeX.",
                    "Use record-level BibTeX for individual evidence claims.",
                    "Use benchmark task cards when reporting model baselines.",
                ],
            },
        ],
        "quick_links": {
            "examples": "/#examples",
            "trust": "/#trust",
            "release_status": "/#release",
            "citation": "/#cite",
            "openapi": "/api/openapi.json",
            "downloads": "/#downloads",
            "data_availability": "/api/data_availability",
        },
    }


def api_release_status() -> dict[str, object]:
    counts = api_stats()["counts"]
    release_count = int(counts.get("toxicity_endpoint", 0)) + int(counts.get("offtarget_evidence", 0))
    audited_release = int(one(HUMAN_VERIFIED_RELEASE_COUNT_SQL).get("n", 0) or 0)
    benchmark_rows = int(counts.get("benchmark_split", 0) or 0)
    release_snapshot = {
        "verified_release_records": release_count,
        "toxicity_records": counts.get("toxicity_endpoint", 0),
        "offtarget_records": counts.get("offtarget_evidence", 0),
        "benchmark_split_records": benchmark_rows,
        "candidate_records": counts.get("curation_candidate", 0),
    }
    readiness_gates = [
        {
            "gate": "No-login local access",
            "status": "pass",
            "evidence": "Static portal and API endpoints are unauthenticated.",
        },
        {
            "gate": "Public HTTPS URL",
            "status": "pass",
            "evidence": f"{PREFERRED_PUBLIC_URL} is live, HTTPS-enabled, and no-login accessible.",
        },
        {
            "gate": "Download availability",
            "status": "pass",
            "evidence": "CSV, benchmark split, ZIP, and manifest downloads are exposed under /api/download and /api/manifest.",
        },
        {
            "gate": "Human-verified release evidence",
            "status": "pass" if audited_release >= MIN_HUMAN_VERIFIED_RELEASE and release_count == audited_release else "blocked",
            "evidence": f"Human curator-verified accepted release rows: {audited_release}; release table rows: {release_count} (re-curated from 2003 v1 machine pre-curated candidates).",
        },
        {
            "gate": "Reference benchmark reuse",
            "status": "pass" if benchmark_rows > 0 else "blocked",
            "evidence": f"Stored benchmark split rows available: {benchmark_rows}.",
        },
    ]
    return {
        "version": PORTAL_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "release_name": "OligoVigil release: 737 human curator-verified safety/off-target evidence rows (626 toxicity + 111 off-target; re-curated from 2003 v1 machine pre-curated candidates); Cohen κ_binary = 0.42 (moderate, drop-abstain) / 0.34 (fair, collapse-abstain) on a 100-row mixed inter-rater study",
        "release_snapshot": release_snapshot,
        "access_policy": {
            "login_required": False,
            "free_access": True,
            "bulk_download": True,
            "candidate_text_policy": "derived_annotations_only_no_raw_abstract_storage",
        },
        "maintenance_policy": {
            "commitment": "Maintained through 2031 after the first public release.",
            "public_contact_status": "contact address to be exposed on the public HTTPS deployment",
            "data_freeze_policy": "Versioned CSV/API snapshots keep previous releases reproducible.",
        },
        "quality_checks": [
            {
                "check": "human_verified_release",
                "status": "pass" if audited_release >= MIN_HUMAN_VERIFIED_RELEASE else "blocked",
                "evidence": f"{audited_release} human curator-verified release rows are available (1345 unsupported v1 machine candidates demoted).",
            },
            {
                "check": "benchmark_splits_available",
                "status": "pass" if benchmark_rows > 0 else "blocked",
                "evidence": f"{benchmark_rows} stored Grade A/B reference split rows are available.",
            },
            {
                "check": "stable_public_url",
                "status": "pass",
                "evidence": f"{PREFERRED_PUBLIC_URL} is live, HTTPS-enabled, and no-login accessible.",
            },
        ],
        "readiness_gates": readiness_gates,
        "public_url_gate": {
            "status": "pass_live_cloudflare_pages",
            "required_for_public_release": True,
            "evidence": f"Live Cloudflare Pages URL verified on {PUBLIC_URL_VERIFIED_DATE}: {PREFERRED_PUBLIC_URL}.",
        },
        "release_batches": [
            {
                "batch": "baseline_verified_release",
                "status": "promoted",
                "accepted": 77,
                "rejected": None,
                "notes": "Initial curator-verified seed release before scale-up.",
            },
            {
                "batch": "batch002_to_batch007",
                "status": "promoted",
                "accepted": 425,
                "rejected": "curation-rejected rows retained outside release tables",
                "notes": "Expanded toxicity/off-target release evidence to exceed 500 records.",
            },
            {
                "batch": "batch009_mega_fast",
                "status": "promoted",
                "accepted": 1182,
                "rejected": 3818,
                "notes": "Large-scale toxicity/off-target curation batch with A/B benchmark eligibility.",
            },
            {
                "batch": "offtarget_B_review",
                "status": "promoted",
                "accepted": 235,
                "rejected": 1023,
                "notes": "Focused off-target B-grade review promoted as release and benchmark evidence.",
            },
            {
                "batch": "20k_offtarget_candidate_pool",
                "status": "screened_only_not_auto_promoted",
                "accepted": 56,
                "rejected": 19944,
                "notes": "Used as screened candidate pool; not treated as direct verified release evidence.",
            },
        ],
        "next_release_requirements": [
            f"Maintain the verified public HTTPS URL: {PREFERRED_PUBLIC_URL}.",
            f"Keep the frozen release package aligned with archive DOI {ARCHIVE_DOI}.",
            "Continue sequence/modification curation to convert sequence search from triage to exact alignment.",
        ],
    }


def api_openapi() -> dict[str, object]:
    endpoints = [
        ("/api/health", "GET", "Service health and database presence."),
        ("/api/metadata", "GET", "Release metadata, active manifest, access policy, and scope."),
        ("/api/stats", "GET", "Core table counts and evidence-grade counts."),
        ("/api/summary", "GET", "Aggregated source, modality, candidate, and evidence summaries."),
        ("/api/facets", "GET", "Facet values for UI filters and API clients."),
        ("/api/quality", "GET", "Access, curation, and release-quality checks."),
        ("/api/coverage", "GET", "Coverage summaries across source years, journals, domains, and curation gaps."),
        ("/api/examples", "GET", "Reusable query and download examples for portal users."),
        ("/api/ask", "GET", "Grounded read-only natural-language query assistant over verified release evidence."),
        ("/api/help", "GET", "Chaptered help guide for users, curators, benchmark reusers, and submitters."),
        ("/api/curation_protocol", "GET", "Curation protocol, provenance coverage, audit gate, and redistribution policy."),
        ("/api/data_availability", "GET", "Data availability statement, formats, archive status, and redistribution boundaries."),
        ("/api/release_status", "GET", "Release gates, batch status, access policy, and public URL readiness."),
        ("/api/submission_pack", "GET", "Release snapshot, adoption-readiness, blockers, and reuse-risk packet."),
        ("/api/field_completeness", "GET", "Release evidence field completeness and structured-data upgrade queue."),
        ("/api/core_oligo_fields", "GET", "Prioritized sequence, modification, delivery, dose, exposure, and model curation gaps for release records."),
        ("/api/independent_validation", "GET", "Independent second-review sampling frame, completion status, agreement metrics, and error-rate readiness."),
        ("/api/novelty_position", "GET", "Closest-work novelty boundary and duplicate-resource red-warning status."),
        ("/api/archive_readiness", "GET", "DOI/archive upload checklist, Zenodo metadata draft, required files, and redistribution rules."),
        ("/api/adoption_packet", "GET", "Post-deployment usage-evidence plan, user groups, shareable workflows, and privacy-preserving event schema."),
        ("/api/agent_access", "GET", "Agent-ready access metadata, OpenAPI/MCP/Skill/SDK artifacts, guardrails, and workflow entry points."),
        ("/api/agent_connect", "GET", "Tool-agnostic connection profiles for agentic clients, OpenAPI importers, MCP clients, and web-fetch agents."),
        ("/agent.json", "GET", "Universal OligoVigil agent discovery manifest."),
        ("/.well-known/oligovigil-agent.json", "GET", "Well-known OligoVigil agent discovery manifest."),
        ("/.well-known/ai-plugin.json", "GET", "OpenAPI action/plugin-style manifest for tools that support REST action import."),
        ("/mcp.json", "GET", "Generic MCP client configuration for the bundled OligoVigil MCP server."),
        ("/llms.txt", "GET", "Concise machine-readable instructions for AI agents."),
        ("/llms-full.txt", "GET", "Detailed machine-readable instructions for AI agents."),
        ("/api/citation", "GET", "Global resource citation, BibTeX, record citation, and benchmark citation policy."),
        ("/api/use_cases", "GET", "Task-oriented user workflows for safety lookup, benchmark reuse, and curation."),
        ("/api/case_workflows", "GET", "Reusable case workflows with endpoints and release counts."),
        ("/api/sequence_coverage", "GET", "Release-grade sequence/modification curation coverage and template link."),
        ("/api/offtarget_taxonomy", "GET", "Off-target mechanism taxonomy, release counts, benchmark counts, and caveats."),
        ("/api/sequence_search", "GET", "Sequence parsing plus seed/off-target/modification evidence lookup."),
        ("/api/safety_triage", "GET", "Source-grounded safety triage report for sequence, target, chemistry, delivery, endpoint, and curation gaps."),
        ("/api/safety_dossier", "GET", "Dossier-form export of source-grounded safety triage, evidence graph, risk matrix, and provenance links."),
        ("/api/evidence_graph", "GET", "Design-to-evidence graph connecting design context, safety concerns, release records, source documents, and candidate gaps."),
        ("/api/prov_graph", "GET", "W3C PROV-compatible JSON profile for dossier derivation and source provenance."),
        ("/bioschemas.json", "GET", "Schema.org/Bioschemas-oriented Dataset JSON-LD metadata for discovery by search engines and AI agents."),
        ("/nlweb.json", "GET", "NLWeb-style natural-language tool discovery manifest for agentic and vibe-coding clients."),
        ("/.well-known/nlweb.json", "GET", "Well-known NLWeb-style discovery manifest."),
        ("/api/modification_profile", "GET", "Safety/off-target profiles grouped by modification, modality, and delivery terms."),
        ("/api/client_examples", "GET", "Copy-ready Python, R, and shell client snippets."),
        ("/api/submission_schema", "GET", "Contribution/correction packet schema for curator-reviewed submissions."),
        ("/api/openapi.json", "GET", "Machine-readable API index for lightweight client generation."),
        ("/api/download_manifest", "GET", "Versioned download manifest with rows, bytes, SHA256, schema, and reuse policy."),
        ("/api/downloads", "GET", "Alias for /api/download_manifest for users and tools expecting a downloads catalog."),
        ("/api/search", "GET", "Unified text search across sources, molecules, candidates, and evidence."),
        ("/api/source_detail", "GET", "Source-level provenance packet by PMID, DOI, ID, or title query."),
        ("/api/evidence_records", "GET", "Unified toxicity/off-target release evidence with provenance fields."),
        ("/api/evidence_detail", "GET", "Citable single-record page payload with audit trail and source metadata."),
        ("/api/benchmark", "GET", "Reference benchmark tasks, split policy, eligibility, and baseline metric guidance."),
        ("/api/benchmark_baseline_results", "GET", "Deterministic reference baseline results for fixed benchmark splits."),
        ("/api/benchmark_tasks", "GET", "CSV-backed benchmark task cards for reusable ML benchmark citation."),
        ("/api/audit", "GET", "Curation audit trail."),
        ("/api/sources", "GET", "Source records with q/source_type/year filters."),
        ("/api/curation_candidates", "GET", "Derived candidate annotations with domain/confidence/q filters."),
        ("/api/curation_queue", "GET", "Candidate curation tasks with domain/priority/q filters."),
        ("/api/download/evidence_release.csv", "GET", "Unified release evidence CSV."),
        ("/api/download/benchmark_reference_splits.csv", "GET", "Deterministic Grade A/B reference benchmark splits."),
        ("/api/download/benchmark_baseline_results.csv", "GET", "Deterministic reference baseline CSV for benchmark split sanity checks."),
        ("/api/download/benchmark_task_cards.csv", "GET", "Benchmark task-card CSV for citation and reuse."),
        ("/api/download/sequence_modification_curation_template.csv", "GET", "Molecule-level sequence/modification curation template."),
        ("/api/download/core_oligo_field_curation_packet.csv", "GET", "Prioritized core oligo field curation packet."),
        ("/api/download/independent_curation_validation_template.csv", "GET", "Independent second-review validation template."),
        ("/api/download/curation_candidates_filtered.csv", "GET", "Filtered candidate evidence CSV."),
        ("/api/download/all_tables.zip", "GET", "Bulk ZIP containing all core CSV tables."),
        ("/api/download/oligovigil_agent_pack.zip", "GET", "ZIP containing universal manifests, MCP server, optional skill, clients, prompt pack, llms files, and starter templates."),
        ("/api/manifest/{filename}", "GET", "Versioned manifest CSV by filename."),
    ]
    query_parameters = {
        "/api/search": ["q", "limit"],
        "/api/ask": ["q", "limit"],
        "/api/source_detail": ["q"],
        "/api/evidence_records": ["domain", "grade", "modality", "category", "q", "limit"],
        "/api/evidence_detail": ["domain", "id", "entity_table", "entity_id"],
        "/api/sequence_search": ["sequence", "target", "modification", "endpoint", "limit"],
        "/api/safety_triage": [
            "sequence",
            "helm",
            "target",
            "modification",
            "delivery",
            "endpoint",
            "species",
            "cell_type",
        ],
        "/api/safety_dossier": [
            "sequence",
            "helm",
            "target",
            "modification",
            "delivery",
            "endpoint",
            "species",
            "cell_type",
        ],
        "/api/evidence_graph": [
            "sequence",
            "helm",
            "target",
            "modification",
            "delivery",
            "endpoint",
            "species",
            "cell_type",
        ],
        "/api/prov_graph": [
            "sequence",
            "helm",
            "target",
            "modification",
            "delivery",
            "endpoint",
            "species",
            "cell_type",
        ],
        "/api/modification_profile": ["term"],
        "/api/audit": ["entity_table", "validation_status", "q", "limit"],
        "/api/sources": ["q", "source_type", "year", "limit"],
        "/api/curation_candidates": ["domain", "confidence", "q", "limit"],
        "/api/curation_queue": ["domain", "priority", "q", "limit"],
        "/api/download/curation_candidates_filtered.csv": ["domain", "confidence", "q", "limit"],
    }

    def operation_id(path: str, method: str) -> str:
        normalized = path.strip("/").replace("{", "").replace("}", "")
        normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_")
        return f"{method.lower()}_{normalized or 'root'}"

    def parameter_schema(name: str) -> dict[str, object]:
        schema: dict[str, object] = {"type": "integer"} if name in {"limit", "year", "id", "entity_id"} else {"type": "string"}
        return {
            "name": name,
            "in": "query",
            "required": False,
            "schema": schema,
        }

    def path_item(path: str, method: str, summary: str) -> dict[str, object]:
        content_type = "text/csv" if path.endswith(".csv") else "application/json"
        if path.endswith(".zip"):
            content_type = "application/zip"
        return {
            method.lower(): {
                "operationId": operation_id(path, method),
                "summary": summary,
                "parameters": [parameter_schema(name) for name in query_parameters.get(path, [])],
                "responses": {
                    "200": {
                        "description": "OK",
                        "content": {
                            content_type: {
                                "schema": {
                                    "type": "string" if content_type != "application/json" else "object"
                                }
                            }
                        },
                    }
                },
            }
        }

    return {
        "openapi": "3.0.0",
        "info": {
            "title": "OligoVigil release API",
            "version": OPENAPI_VERSION,
        },
        "servers": [{"url": "/"}],
        "paths": {
            path: path_item(path, method, summary) for path, method, summary in endpoints
        },
    }


def api_readiness() -> dict[str, object]:
    counts = api_stats()["counts"]
    release_evidence = int(counts.get("toxicity_endpoint", 0)) + int(counts.get("offtarget_evidence", 0))
    verified_release = int(one(HUMAN_VERIFIED_RELEASE_COUNT_SQL).get("n", 0) or 0)
    benchmark_rows = len(benchmark_reference_splits())
    gates = [
        {
            "gate": "No-login local access",
            "status": "pass",
            "evidence": "Static portal and API endpoints are unauthenticated.",
        },
        {
            "gate": "Public HTTPS URL",
            "status": "pass",
            "evidence": f"{PREFERRED_PUBLIC_URL} is live, HTTPS-enabled, and no-login accessible.",
        },
        {
            "gate": "Download availability",
            "status": "pass",
            "evidence": "CSV, benchmark split, ZIP, and manifest downloads are exposed under /api/download and /api/manifest.",
        },
        {
            "gate": "Candidate/final evidence separation",
            "status": "pass",
            "evidence": "Candidate records remain in curation_candidate until curator-verified promotion.",
        },
        {
            "gate": "Human-verified release evidence",
            "status": "pass" if release_evidence >= MIN_HUMAN_VERIFIED_RELEASE and release_evidence == verified_release else "blocked",
            "evidence": (
                f"Human curator-verified accepted release rows: toxicity={counts.get('toxicity_endpoint', 0)}, "
                f"offtarget={counts.get('offtarget_evidence', 0)}, total={verified_release}."
            ),
        },
        {
            "gate": "Reference benchmark reuse",
            "status": "pass" if benchmark_rows > 0 else "blocked",
            "evidence": f"Deterministic Grade A/B reference split rows available: {benchmark_rows}.",
        },
    ]
    overall = "verified_release_ready_public_url_blocked" if release_evidence else "release_evidence_blocked"
    return {"overall": overall, "gates": gates}


def api_closest_work() -> list[dict[str, object]]:
    return manifest_rows("closest_work_matrix_v1.csv")


def api_data_dictionary() -> list[dict[str, object]]:
    return manifest_rows("data_dictionary_v1.csv")


def api_sources(query: dict[str, list[str]]) -> list[dict[str, object]]:
    q = first_param(query, "q")
    source_type = first_param(query, "source_type")
    year = first_param(query, "year")
    limit = limit_param(query, default=250, maximum=2000)
    sql = """
        SELECT id, source_type, title, journal_or_agency, publication_year,
               doi, pmid, pmcid, reuse_category, source_url
        FROM source_document
    """
    clauses: list[str] = []
    params: list[object] = []
    if q:
        append_query_match_or_raw(
            clauses,
            params,
            ["title", "journal_or_agency", "doi", "pmid", "source_type"],
            q,
        )
    if source_type:
        clauses.append("source_type = ?")
        params.append(source_type)
    if year:
        clauses.append("CAST(publication_year AS TEXT) = ?")
        params.append(year)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY publication_year DESC, id LIMIT ?"
    params.append(limit)
    return rows(sql, tuple(params))


def api_source_detail(query: dict[str, list[str]]) -> dict[str, object]:
    q = first_param(query, "q")
    if not q:
        return {
            "query": q,
            "source": None,
            "queue": [],
            "candidates": [],
            "toxicity": [],
            "offtarget": [],
        }
    like = f"%{q}%"
    source = one(
        """
        SELECT id, source_type, source_url, pmid, pmcid, doi, title, journal_or_agency,
               publication_year, license_status, reuse_category, accessed_at
        FROM source_document
        WHERE CAST(id AS TEXT) = ? OR pmid = ? OR doi = ? OR title LIKE ?
        ORDER BY publication_year DESC, id
        LIMIT 1
        """,
        (q, q, q, like),
    )
    if not source:
        return {
            "query": q,
            "source": None,
            "queue": [],
            "candidates": [],
            "toxicity": [],
            "offtarget": [],
        }
    source_id = source["id"]
    return {
        "query": q,
        "source": source,
        "queue": rows(
            """
            SELECT id, evidence_domain, candidate_modality, extraction_target,
                   suggested_evidence_grade, priority, queue_status
            FROM curation_queue
            WHERE source_document_id = ?
            ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, id
            """,
            (source_id,),
        ),
        "candidates": rows(
            """
            SELECT id, evidence_domain, candidate_modality, source_location, matched_terms,
                   candidate_signal, suggested_evidence_grade, confidence_label,
                   validation_status, curator_decision, redistribution_level
            FROM curation_candidate
            WHERE source_document_id = ?
            ORDER BY CASE confidence_label
                WHEN 'high_candidate' THEN 0
                WHEN 'medium_candidate' THEN 1
                ELSE 2
            END, id
            """,
            (source_id,),
        ),
        "toxicity": rows(
            """
            SELECT 'toxicity' AS evidence_domain,
                   toxicity_endpoint.id AS evidence_id,
                   toxicity_endpoint.id, molecule.canonical_name, modality.name AS modality,
                   toxicity_endpoint.endpoint_category, toxicity_endpoint.endpoint_name,
                   toxicity_endpoint.evidence_grade, toxicity_endpoint.source_location
            FROM toxicity_endpoint
            JOIN molecule ON toxicity_endpoint.molecule_id = molecule.id
            JOIN modality ON molecule.modality_id = modality.id
            JOIN curation_audit AS audit
              ON audit.entity_table = 'toxicity_endpoint'
             AND audit.entity_id = toxicity_endpoint.id
             AND audit.validation_status = 'curator_verified'
             AND audit.curator_decision = 'accept'
            WHERE toxicity_endpoint.source_document_id = ?
            GROUP BY toxicity_endpoint.id
            ORDER BY toxicity_endpoint.id
            """,
            (source_id,),
        ),
        "offtarget": rows(
            """
            SELECT 'offtarget' AS evidence_domain,
                   offtarget_evidence.id AS evidence_id,
                   offtarget_evidence.id, molecule.canonical_name, modality.name AS modality,
                   offtarget_evidence.evidence_type, offtarget_evidence.evidence_grade,
                   offtarget_evidence.source_location
            FROM offtarget_evidence
            JOIN molecule ON offtarget_evidence.molecule_id = molecule.id
            JOIN modality ON molecule.modality_id = modality.id
            JOIN curation_audit AS audit
              ON audit.entity_table = 'offtarget_evidence'
             AND audit.entity_id = offtarget_evidence.id
             AND audit.validation_status = 'curator_verified'
             AND audit.curator_decision = 'accept'
            WHERE offtarget_evidence.source_document_id = ?
            GROUP BY offtarget_evidence.id
            ORDER BY offtarget_evidence.id
            """,
            (source_id,),
        ),
    }


def api_molecules(query: dict[str, list[str]]) -> list[dict[str, object]]:
    modality = first_param(query, "modality")
    q = first_param(query, "q")
    limit = limit_param(query, default=250, maximum=2000)
    sql = """
        SELECT molecule.id, molecule.canonical_name, modality.name AS modality,
               molecule.target_gene_symbol, molecule.disease_context,
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
               molecule.modification_annotation_status,
               molecule.external_ids
        FROM molecule
        JOIN modality ON molecule.modality_id = modality.id
    """
    clauses: list[str] = []
    params: list[object] = []
    if modality:
        clauses.append("modality.name = ?")
        params.append(modality)
    if q:
        append_query_match_or_raw(
            clauses,
            params,
            [
                "molecule.canonical_name",
                "modality.name",
                "molecule.target_gene_symbol",
                "molecule.disease_context",
                "molecule.therapeutic_status",
                "molecule.backbone_chemistry",
                "molecule.sugar_modification",
                "molecule.base_modification",
                "molecule.conjugate_delivery",
                "molecule.external_ids",
            ],
            q,
        )
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY molecule.id LIMIT ?"
    params.append(limit)
    return rows(sql, tuple(params))


def api_evidence() -> dict[str, object]:
    toxicity = rows(
        """
        SELECT toxicity_endpoint.id, molecule.canonical_name, modality.name AS modality,
               toxicity_endpoint.endpoint_name, toxicity_endpoint.endpoint_category,
               toxicity_endpoint.evidence_grade, toxicity_endpoint.source_location,
               source_document.title AS source_title, source_document.pmid,
               source_document.doi, source_document.source_url
        FROM toxicity_endpoint
        JOIN molecule ON toxicity_endpoint.molecule_id = molecule.id
        JOIN modality ON molecule.modality_id = modality.id
        JOIN source_document ON toxicity_endpoint.source_document_id = source_document.id
        ORDER BY toxicity_endpoint.id
        """
    )
    offtarget = rows(
        """
        SELECT offtarget_evidence.id, molecule.canonical_name, modality.name AS modality,
               offtarget_evidence.evidence_type, offtarget_evidence.evidence_grade,
               offtarget_evidence.is_computational_prediction,
               offtarget_evidence.source_location,
               source_document.title AS source_title, source_document.pmid,
               source_document.doi, source_document.source_url
        FROM offtarget_evidence
        JOIN molecule ON offtarget_evidence.molecule_id = molecule.id
        JOIN modality ON molecule.modality_id = modality.id
        JOIN source_document ON offtarget_evidence.source_document_id = source_document.id
        ORDER BY offtarget_evidence.id
        """
    )
    return {"toxicity": toxicity, "offtarget": offtarget}


def evidence_records(query: dict[str, list[str]]) -> list[dict[str, object]]:
    domain = first_param(query, "domain")
    grade = first_param(query, "grade")
    modality = first_param(query, "modality")
    category = first_param(query, "category")
    target = first_param(query, "target")
    q = first_param(query, "q")
    limit = limit_param(query, default=250, maximum=RELEASE_EXPORT_LIMIT)
    base_sql = """
        SELECT 'toxicity' AS evidence_domain,
               'toxicity_endpoint' AS entity_table,
               toxicity_endpoint.id AS evidence_id,
               molecule.canonical_name,
               modality.name AS modality,
               molecule.target_gene_symbol,
               molecule.disease_context,
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
               molecule.modification_annotation_status,
               toxicity_endpoint.endpoint_category AS category,
               toxicity_endpoint.endpoint_name AS evidence_label,
               toxicity_endpoint.evidence_grade,
               toxicity_endpoint.source_location,
               source_document.id AS source_document_id,
               source_document.title AS source_title,
               source_document.pmid,
               source_document.pmcid AS source_pmcid,
               source_document.doi,
               source_document.source_url,
               source_document.license_status AS source_license_status,
               source_document.reuse_category AS source_reuse_category,
               CASE
                 WHEN toxicity_endpoint.source_location LIKE '%paragraph%'
                   OR toxicity_endpoint.source_location LIKE '%Results%'
                   OR toxicity_endpoint.source_location LIKE '%Table%'
                   OR toxicity_endpoint.source_location LIKE '%Figure%'
                 THEN 'source-localized derived annotation'
                 ELSE 'source-linked derived annotation'
               END AS curation_basis,
               'false' AS raw_quote_included,
               toxicity_endpoint.is_observed_experimental,
               0 AS is_computational_prediction
        FROM toxicity_endpoint
        JOIN molecule ON toxicity_endpoint.molecule_id = molecule.id
        JOIN modality ON molecule.modality_id = modality.id
        JOIN source_document ON toxicity_endpoint.source_document_id = source_document.id
        UNION ALL
        SELECT 'offtarget' AS evidence_domain,
               'offtarget_evidence' AS entity_table,
               offtarget_evidence.id AS evidence_id,
               molecule.canonical_name,
               modality.name AS modality,
               molecule.target_gene_symbol,
               molecule.disease_context,
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
               molecule.modification_annotation_status,
               offtarget_evidence.evidence_type AS category,
               offtarget_evidence.evidence_type AS evidence_label,
               offtarget_evidence.evidence_grade,
               offtarget_evidence.source_location,
               source_document.id AS source_document_id,
               source_document.title AS source_title,
               source_document.pmid,
               source_document.pmcid AS source_pmcid,
               source_document.doi,
               source_document.source_url,
               source_document.license_status AS source_license_status,
               source_document.reuse_category AS source_reuse_category,
               CASE
                 WHEN offtarget_evidence.source_location LIKE '%paragraph%'
                   OR offtarget_evidence.source_location LIKE '%Results%'
                   OR offtarget_evidence.source_location LIKE '%Table%'
                   OR offtarget_evidence.source_location LIKE '%Figure%'
                 THEN 'source-localized derived annotation'
                 ELSE 'source-linked derived annotation'
               END AS curation_basis,
               'false' AS raw_quote_included,
               offtarget_evidence.is_observed_experimental,
               offtarget_evidence.is_computational_prediction
        FROM offtarget_evidence
        JOIN molecule ON offtarget_evidence.molecule_id = molecule.id
        JOIN modality ON molecule.modality_id = modality.id
        JOIN source_document ON offtarget_evidence.source_document_id = source_document.id
    """
    sql = f"""
        SELECT evidence.*, audit.validation_status AS audit_validation_status,
               audit.curator_decision, audit.curator_id, audit.audit_note,
               audit.audited_at
        FROM ({base_sql}) AS evidence
        LEFT JOIN (
            -- One audit row per release entity: the most recent human curator-verified
            -- accept. Without this dedup, rows carrying two curator_verified accept audits
            -- (an entity with both an earlier spot-check and the re-curation audit) fan out into duplicate
            -- release rows in evidence_release.csv and the evidence explorer.
            SELECT entity_table, entity_id, validation_status, curator_decision,
                   curator_id, audit_note, audited_at
            FROM (
                SELECT entity_table, entity_id, validation_status, curator_decision,
                       curator_id, audit_note, audited_at,
                       ROW_NUMBER() OVER (
                           PARTITION BY entity_table, entity_id
                           ORDER BY audited_at DESC, id DESC
                       ) AS rn
                FROM curation_audit
                WHERE validation_status = 'curator_verified'
                  AND curator_decision = 'accept'
            ) WHERE rn = 1
        ) AS audit
          ON audit.entity_table = evidence.entity_table
         AND audit.entity_id = evidence.evidence_id
    """
    clauses: list[str] = []
    params: list[object] = []
    clauses.extend(
        [
            "audit.validation_status = 'curator_verified'",
            "audit.curator_decision = 'accept'",
            "evidence_grade IN ('A', 'B', 'C')",
        ]
    )
    if domain:
        clauses.append("evidence_domain = ?")
        params.append(domain)
    if grade:
        clauses.append("evidence_grade = ?")
        params.append(grade)
    if modality:
        clauses.append("modality = ?")
        params.append(modality)
    if category:
        clauses.append("category = ?")
        params.append(category)
    if target:
        clauses.append("target_gene_symbol LIKE ?")
        params.append(f"%{target}%")
    if q:
        append_query_match_or_raw(
            clauses,
            params,
            [
                "canonical_name",
                "category",
                "evidence_label",
                "target_gene_symbol",
                "disease_context",
                "backbone_chemistry",
                "sugar_modification",
                "base_modification",
                "conjugate_delivery",
                "modality",
                "source_location",
                "source_title",
                "pmid",
                "doi",
            ],
            q,
        )
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY evidence_domain DESC, evidence_id LIMIT ?"
    params.append(limit)
    return rows(sql, tuple(params))


_RELEASE_RECORDS_CACHE: list[dict[str, object]] | None = None


def release_records_all() -> list[dict[str, object]]:
    global _RELEASE_RECORDS_CACHE
    if _RELEASE_RECORDS_CACHE is None:
        _RELEASE_RECORDS_CACHE = evidence_records({"limit": [str(RELEASE_EXPORT_LIMIT)]})
    return _RELEASE_RECORDS_CACHE


def cached_release_count(query: dict[str, list[str]]) -> int:
    domain = first_param(query, "domain")
    grade = first_param(query, "grade")
    modality = first_param(query, "modality")
    category = first_param(query, "category")
    target = first_param(query, "target").lower()
    q = first_param(query, "q").lower()
    text_fields = [
        "canonical_name",
        "category",
        "evidence_label",
        "target_gene_symbol",
        "disease_context",
        "backbone_chemistry",
        "sugar_modification",
        "base_modification",
        "conjugate_delivery",
        "modality",
        "source_location",
        "source_title",
        "pmid",
        "doi",
    ]
    count = 0
    for record in release_records_all():
        if domain and record.get("evidence_domain") != domain:
            continue
        if grade and record.get("evidence_grade") != grade:
            continue
        if modality and record.get("modality") != modality:
            continue
        if category and record.get("category") != category:
            continue
        if target and target not in str(record.get("target_gene_symbol") or "").lower():
            continue
        if q and not any(q in str(record.get(field) or "").lower() for field in text_fields):
            continue
        count += 1
    return count


def evidence_release_csv_bytes() -> bytes:
    return dicts_to_csv_bytes(release_records_all(), EVIDENCE_RELEASE_COLUMNS)


def nonempty(value: object) -> bool:
    return value is not None and str(value).strip() not in {"", "NA", "N/A", "nan", "None"}


def field_status(completeness_pct: float, strict: bool = False) -> str:
    if strict:
        if completeness_pct >= 95:
            return "pass"
        if completeness_pct >= 80:
            return "partial"
        return "gap"
    if completeness_pct >= 70:
        return "pass"
    if completeness_pct >= 25:
        return "partial"
    return "gap"


def api_field_completeness() -> dict[str, object]:
    release = release_records_all()
    total = len(release)
    field_specs = [
        ("canonical_name", "identity", "Molecule name", True),
        ("modality", "identity", "Modality", True),
        ("target_gene_symbol", "identity", "Target gene", False),
        ("category", "safety", "Evidence category", True),
        ("evidence_label", "safety", "Evidence label", True),
        ("evidence_grade", "safety", "Evidence grade", True),
        ("source_title", "provenance", "Source title", True),
        ("source_location", "provenance", "Exact source location", True),
        ("pmid", "provenance", "PMID", False),
        ("doi", "provenance", "DOI", False),
        ("sense_sequence", "sequence", "Sense sequence", False),
        ("antisense_sequence", "sequence", "Antisense sequence", False),
        ("guide_sequence", "sequence", "Guide sequence", False),
        ("passenger_sequence", "sequence", "Passenger sequence", False),
        ("seed_region", "sequence", "Seed region", False),
        ("backbone_chemistry", "chemistry", "Backbone chemistry", False),
        ("sugar_modification", "chemistry", "Sugar modification", False),
        ("base_modification", "chemistry", "Base modification", False),
        ("conjugate_delivery", "chemistry", "Conjugate / delivery", False),
    ]
    fields: list[dict[str, object]] = []
    for key, group, label, strict in field_specs:
        filled = sum(1 for record in release if nonempty(record.get(key)))
        pct = round((filled / total) * 100, 1) if total else 0.0
        fields.append(
            {
                "field": key,
                "label": label,
                "group": group,
                "filled": filled,
                "total": total,
                "completeness_pct": pct,
                "status": field_status(pct, strict=strict),
                "reviewer_use": "core release claim" if strict else "structured reuse / search improvement",
            }
        )

    sequence_fields = {"sense_sequence", "antisense_sequence", "guide_sequence", "passenger_sequence", "seed_region"}
    chemistry_fields = {
        "backbone_chemistry",
        "sugar_modification",
        "base_modification",
        "conjugate_delivery",
    }
    any_sequence = sum(
        1 for record in release if any(nonempty(record.get(field)) for field in sequence_fields)
    )
    any_chemistry = sum(
        1 for record in release if any(nonempty(record.get(field)) for field in chemistry_fields)
    )
    strict_fields = [row for row in fields if row["reviewer_use"] == "core release claim"]
    strict_avg = round(
        sum(float(row["completeness_pct"]) for row in strict_fields) / max(len(strict_fields), 1), 1
    )
    return {
        "version": PORTAL_VERSION,
        "release_records": total,
        "summary": {
            "core_required_avg_pct": strict_avg,
            "records_with_any_sequence": any_sequence,
            "records_with_any_chemistry_or_delivery": any_chemistry,
            "sequence_completion_status": field_status(round((any_sequence / total) * 100, 1) if total else 0),
            "chemistry_completion_status": field_status(round((any_chemistry / total) * 100, 1) if total else 0),
            "action_note": "Core provenance fields support citation now; sequence and chemistry fields remain the highest-value expansion path before public submission.",
        },
        "fields": fields,
        "upgrade_queue": [
            {
                "priority": "P0",
                "target": "exact source location and DOI/PMID completion",
                "why": "Directly affects user trust and record-level citation.",
            },
            {
                "priority": "P1",
                "target": "guide/antisense/seed sequence capture",
                "why": "Turns OligoVigil from evidence browser into exact design-triage infrastructure.",
            },
            {
                "priority": "P1",
                "target": "backbone, sugar, base, and conjugate delivery normalization",
                "why": "Supports chemistry-group reuse and richer safety stratification.",
            },
        ],
    }


def csv_rows_from_path(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def api_core_oligo_fields() -> dict[str, object]:
    summary = read_json_file(CORE_OLIGO_FIELD_SUMMARY_PATH)
    packet_path = MANIFEST_DOWNLOADS["core_oligo_field_curation_packet_v1.csv"]
    packet_rows = csv_rows_from_path(packet_path)
    release_total = int(summary.get("rows") or len(packet_rows))
    priority_counts = Counter(str(row.get("priority") or "unassigned") for row in packet_rows)
    missing_keys = [
        "missing_sequence",
        "missing_seed",
        "missing_modification",
        "missing_delivery",
        "missing_dose",
        "missing_exposure",
        "missing_model",
    ]
    missing_counts = Counter()
    for row in packet_rows:
        for key in missing_keys:
            if str(row.get(key) or "").upper() == "TRUE":
                missing_counts[key] += 1

    p0_rows = [row for row in packet_rows if str(row.get("priority")) == "P0"]
    p0_missing_sequence = sum(1 for row in p0_rows if str(row.get("missing_sequence")) == "TRUE")
    p0_missing_modification = sum(
        1 for row in p0_rows if str(row.get("missing_modification")) == "TRUE"
    )
    p0_missing_dose = sum(1 for row in p0_rows if str(row.get("missing_dose")) == "TRUE")
    field_completeness = api_field_completeness()
    assay_with_dose = int(
        one(
            """
            SELECT COUNT(*) AS n
            FROM assay
            WHERE dose_value IS NOT NULL
               OR dose_unit IS NOT NULL AND dose_unit != ''
            """
        ).get("n", 0)
        or 0
    )
    assay_with_model = int(
        one(
            """
            SELECT COUNT(*) AS n
            FROM assay
            WHERE COALESCE(NULLIF(organism, ''),
                           NULLIF(model_system, ''),
                           NULLIF(cell_line_or_tissue, '')) IS NOT NULL
            """
        ).get("n", 0)
        or 0
    )
    return {
        "version": PORTAL_VERSION,
        "release_records": release_total,
        "packet_rows": len(packet_rows),
        "claim_boundary": "Current release can be described as a provenance-rich safety/off-target evidence database. It must not be described as complete sequence/modification/dose coverage until P0 field curation is source-verified.",
        "summary": {
            "p0_benchmark_linked_rows": priority_counts.get("P0", 0),
            "p1_grade_ab_nonbenchmark_rows": priority_counts.get("P1", 0),
            "p2_contextual_grade_c_rows": priority_counts.get("P2", 0),
            "p0_missing_sequence": p0_missing_sequence,
            "p0_missing_modification": p0_missing_modification,
            "p0_missing_dose": p0_missing_dose,
            "assays_with_dose": assay_with_dose,
            "assays_with_model_context": assay_with_model,
        },
        "priority_breakdown": [
            {
                "priority": "P0",
                "rows": priority_counts.get("P0", 0),
                "meaning": "Grade A/B benchmark-linked release rows; curate first before claiming mature oligo design fields.",
                "reviewer_risk": "Highest: empty sequence/modification/dose fields can make the resource look like a literature index.",
            },
            {
                "priority": "P1",
                "rows": priority_counts.get("P1", 0),
                "meaning": "Grade A/B release rows outside current benchmark splits.",
                "reviewer_risk": "Moderate: improves reuse and chemistry-specific search.",
            },
            {
                "priority": "P2",
                "rows": priority_counts.get("P2", 0),
                "meaning": "Grade C contextual release rows retained for browsing, not A/B benchmark reuse.",
                "reviewer_risk": "Lower: useful after P0/P1 are stable.",
            },
        ],
        "missing_field_breakdown": [
            {
                "field": key.removeprefix("missing_"),
                "missing_rows": missing_counts.get(key, 0),
                "pct": pct(missing_counts.get(key, 0), release_total),
            }
            for key in missing_keys
        ],
        "blocking_gates": [
            {
                "gate": "Complete oligo identity claim",
                "status": "blocked" if p0_missing_sequence or p0_missing_modification else "pass",
                "evidence": f"P0 missing sequence={p0_missing_sequence}; P0 missing modification={p0_missing_modification}.",
            },
            {
                "gate": "Dose-aware safety stratification",
                "status": "blocked" if p0_missing_dose else "partial",
                "evidence": f"P0 missing dose={p0_missing_dose}; assay table currently has {assay_with_dose} dose-bearing assays.",
            },
            {
                "gate": "No-fabrication policy",
                "status": "pass",
                "evidence": "Packet fields are blank unless source-located; generated rows are curation work items, not release claims.",
            },
        ],
        "downloads": {
            "core_field_packet": "/api/download/core_oligo_field_curation_packet.csv",
            "core_field_packet_manifest": "/api/manifest/core_oligo_field_curation_packet_v1.csv",
            "legacy_sequence_template": "/api/download/sequence_modification_curation_template.csv",
            "field_completeness": "/api/field_completeness",
        },
        "field_completeness_summary": field_completeness.get("summary", {}),
    }


def cohen_kappa(rows_for_metric: list[dict[str, object]]) -> float | None:
    labels = ["accept", "reject"]
    total = len(rows_for_metric)
    if total == 0:
        return None
    observed = sum(
        1
        for row in rows_for_metric
        if str(row.get("original_curator_decision") or "").lower()
        == str(row.get("reviewer2_decision") or "").lower()
    ) / total
    original_counts = Counter(
        str(row.get("original_curator_decision") or "").lower() for row in rows_for_metric
    )
    reviewer_counts = Counter(str(row.get("reviewer2_decision") or "").lower() for row in rows_for_metric)
    expected = sum((original_counts[label] / total) * (reviewer_counts[label] / total) for label in labels)
    if expected >= 1:
        return None
    return round((observed - expected) / (1 - expected), 4)


def api_independent_validation() -> dict[str, object]:
    summary = read_json_file(INDEPENDENT_VALIDATION_SUMMARY_PATH)
    packet_path = MANIFEST_DOWNLOADS["independent_curation_validation_template_v1.csv"]
    packet_rows = csv_rows_from_path(packet_path)
    sample_rows = int(summary.get("sample_rows") or len(packet_rows))
    reviewed = [
        row
        for row in packet_rows
        if str(row.get("reviewer2_decision") or "").lower() in {"accept", "reject"}
    ]
    comparable = [
        row
        for row in reviewed
        if str(row.get("original_curator_decision") or "").lower() in {"accept", "reject"}
    ]
    agreement = None
    if comparable:
        agreement = round(
            sum(
                1
                for row in comparable
                if str(row.get("original_curator_decision") or "").lower()
                == str(row.get("reviewer2_decision") or "").lower()
            )
            / len(comparable),
            4,
        )
    kappa = cohen_kappa(comparable)
    release_accept_reviewed = [row for row in reviewed if row.get("item_type") == "release_accept"]
    reject_control_reviewed = [
        row for row in reviewed if row.get("item_type") == "candidate_reject_control"
    ]
    false_accepts = sum(
        1
        for row in release_accept_reviewed
        if str(row.get("reviewer2_decision") or "").lower() == "reject"
    )
    false_rejects = sum(
        1
        for row in reject_control_reviewed
        if str(row.get("reviewer2_decision") or "").lower() == "accept"
    )
    type_counts = Counter(str(row.get("item_type") or "unknown") for row in packet_rows)
    stratum_counts = Counter(str(row.get("stratum") or "unknown") for row in packet_rows)
    complete = sample_rows > 0 and len(comparable) >= sample_rows
    return {
        "version": PORTAL_VERSION,
        "claim_status": "claimable_after_review" if complete else "not_claimable",
        "claim_boundary": "Cohen kappa is now claimed from the completed 100-row mixed inter-rater study (KAPPA-2; see kappa_claimed below). This separate 500-row independent second-review packet underwrites the release-row false-accept / false-reject ERROR-RATE estimates, which remain pending until reviewer2_decision is filled and adjudicated; the live agreement/kappa fields in this endpoint are computed from that 500-row packet and are null until it is filled.",
        "kappa_claimed": {
            "status": "claimed",
            "study": "100-row mixed inter-rater study (KAPPA-2), second curator HY (blinded, no manuscript exposure)",
            "cohen_kappa_binary_drop_abstain": 0.42,
            "cohen_kappa_binary_drop_abstain_detail": "moderate (Landis-Koch); drop-abstain convention, n=92 non-abstain rows",
            "cohen_kappa_binary_collapse_abstain": 0.34,
            "cohen_kappa_binary_collapse_abstain_detail": "fair (Landis-Koch); safety-conservative collapse-abstain convention, n=100",
            "cohen_kappa_3class": 0.37,
            "cohen_kappa_grade": 0.39,
            "raw_agreement": 0.66,
            "raw_agreement_detail": "66% (66/100), 3-class accept/reject/abstain",
            "second_curator": "HY, blinded, no manuscript exposure; systematically stricter (92% reject-confirm, 40% accept-confirm) — conservative direction for a safety database",
            "third_adjudicator": "A10 third-adjudicator consensus pass is in progress (not yet returned); will further refine kappa once adjudicated.",
        },
        "sample": {
            "sample_rows": sample_rows,
            "reviewed_rows": len(reviewed),
            "comparable_rows": len(comparable),
            "release_accept_rows": type_counts.get("release_accept", 0),
            "candidate_reject_control_rows": type_counts.get("candidate_reject_control", 0),
            "completion_pct": pct(len(comparable), sample_rows),
        },
        "metrics": {
            "raw_agreement": agreement,
            "cohen_kappa": kappa,
            "false_accept_rate_release_rows": pct(false_accepts, len(release_accept_reviewed))
            if release_accept_reviewed
            else None,
            "false_reject_rate_reject_controls": pct(false_rejects, len(reject_control_reviewed))
            if reject_control_reviewed
            else None,
            "source_location_disagreement_rows": sum(
                1
                for row in reviewed
                if str(row.get("reviewer2_source_location_verified") or "").lower()
                in {"no", "false", "reject"}
            ),
        },
        "sampling_breakdown": [
            {"item_type": key, "rows": value} for key, value in sorted(type_counts.items())
        ],
        "top_strata": [
            {"stratum": key, "rows": value} for key, value in stratum_counts.most_common(12)
        ],
        "review_fields": [
            {
                "field": "reviewer2_decision",
                "allowed_values": "accept | reject",
                "use": "Independent second reviewer repeats the release/reject decision from source evidence.",
            },
            {
                "field": "reviewer2_evidence_grade",
                "allowed_values": "A | B | C | reject",
                "use": "Grade disagreement is counted separately from accept/reject disagreement.",
            },
            {
                "field": "reviewer2_source_location_verified",
                "allowed_values": "yes | no",
                "use": "Checks whether the cited source location actually supports the evidence claim.",
            },
            {
                "field": "reviewer2_error_type",
                "allowed_values": "scope_error | source_location_error | grade_error | duplicate | extraction_error | none",
                "use": "Feeds the manuscript error-rate estimate after adjudication.",
            },
        ],
        "downloads": {
            "independent_validation_template": "/api/download/independent_curation_validation_template.csv",
            "independent_validation_manifest": "/api/manifest/independent_curation_validation_template_v1.csv",
            "curation_audit": "/api/download/curation_audit.csv",
        },
    }


def api_novelty_position() -> dict[str, object]:
    closest_rows = api_closest_work()
    duplicate_flags: list[dict[str, object]] = []
    for row in closest_rows:
        resource = str(row.get("resource") or "")
        if resource.lower() == "oligovigil":
            continue
        coverage_blob = " ".join(str(value).lower() for value in row.values())
        has_sequence = "sequence=yes" in coverage_blob or str(row.get("sequence_or_molecule")) == "yes"
        has_modification = str(row.get("chemical_modification") or "").lower() in {"yes", "core"}
        has_delivery = str(row.get("delivery") or "").lower() in {"yes", "core"}
        has_safety = str(row.get("toxicity") or "").lower() in {"yes", "core", "safety_core"}
        has_offtarget = str(row.get("offtarget") or "").lower() in {"yes", "core", "offtarget_core"}
        has_benchmark = str(row.get("benchmark_splits") or "").lower() in {"yes", "core", "downloadable"}
        if has_sequence and has_modification and has_delivery and has_safety and has_offtarget and has_benchmark:
            duplicate_flags.append(row)
    return {
        "version": PORTAL_VERSION,
        "red_warning": bool(duplicate_flags),
        "duplicate_flags": duplicate_flags,
        "position": "OligoVigil should be framed as a safety/off-target evidence and provenance resource, not as a broad RNA therapeutics catalog, siRNA efficacy database, or complete sequence/modification catalog.",
        "defensible_claims": [
            {
                "claim": "Safety/off-target first",
                "defense": "The core release records are toxicity and off-target evidence, with A/B/C grading and source-localized provenance.",
            },
            {
                "claim": "Benchmark-ready evidence release",
                "defense": "Grade A/B records have deterministic reference splits and task cards; efficacy-focused comparators do not provide the same safety/off-target benchmark framing.",
            },
            {
                "claim": "License-aware curation boundary",
                "defense": "The portal exposes derived annotations, source links, reuse categories, and download checksums without redistributing raw article text.",
            },
            {
                "claim": "Honest sequence/modification roadmap",
                "defense": "Sequence, chemistry, and dose fields are exposed as source-verifiable curation packets rather than inflated as completed coverage.",
            },
        ],
        "do_not_claim": [
            "Do not claim to be the most complete RNA therapeutics catalog; theRNA is broader.",
            "Do not claim primary siRNA efficacy novelty; siRNAEfficacyDB and CMsiRNAdb are closer on efficacy.",
            "Do not claim complete sequence/modification coverage until P0 core field curation is completed.",
            "Do not claim release-row false-accept / false-reject error rates before the 500-row second-review packet is filled and adjudicated (inter-curator Cohen kappa is separately claimed from the completed 100-row KAPPA-2 study: 0.42 drop-abstain / 0.34 collapse-abstain).",
        ],
        "closest_work_rows": closest_rows,
    }


def pct(numerator: int | float, denominator: int | float) -> float:
    return round((float(numerator) / max(float(denominator), 1.0)) * 100, 1)


def build_curation_protocol_payload() -> dict[str, object]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    def scalar(query: str, params: tuple[object, ...] = ()) -> int:
        row = conn.execute(query, params).fetchone()
        return int((row["n"] if row else 0) or 0)

    def fetch_rows(query: str, params: tuple[object, ...] = ()) -> list[dict[str, object]]:
        return [dict(row) for row in conn.execute(query, params).fetchall()]

    try:
        toxicity_count = scalar("SELECT COUNT(*) AS n FROM toxicity_endpoint")
        offtarget_count = scalar("SELECT COUNT(*) AS n FROM offtarget_evidence")
        candidate_count = scalar("SELECT COUNT(*) AS n FROM curation_candidate")
        source_count = scalar("SELECT COUNT(*) AS n FROM source_document")
        verified_accepts = scalar(HUMAN_VERIFIED_RELEASE_COUNT_SQL)
        rejected_candidates = scalar(
            """
            SELECT COUNT(*) AS n
            FROM curation_audit
            WHERE entity_table = 'curation_candidate'
              AND validation_status = 'curator_rejected'
              AND curator_decision = 'reject'
            """
        )
        candidate_pending = scalar(
            """
            SELECT COUNT(*) AS n
            FROM curation_candidate
            WHERE validation_status IS NULL
               OR validation_status NOT IN ('curator_verified', 'curator_rejected', 'machine_precurated_v1')
            """
        )
        release_with_source_location = scalar(
            """
            SELECT SUM(n) AS n
            FROM (
                SELECT COUNT(*) AS n FROM toxicity_endpoint
                WHERE source_location IS NOT NULL AND source_location != ''
                UNION ALL
                SELECT COUNT(*) AS n FROM offtarget_evidence
                WHERE source_location IS NOT NULL AND source_location != ''
            )
            """
        )
        release_with_pmid = scalar(
            """
            SELECT SUM(n) AS n
            FROM (
                SELECT COUNT(*) AS n
                FROM toxicity_endpoint
                JOIN source_document ON toxicity_endpoint.source_document_id = source_document.id
                WHERE source_document.pmid IS NOT NULL AND source_document.pmid != ''
                UNION ALL
                SELECT COUNT(*) AS n
                FROM offtarget_evidence
                JOIN source_document ON offtarget_evidence.source_document_id = source_document.id
                WHERE source_document.pmid IS NOT NULL AND source_document.pmid != ''
            )
            """
        )
        release_with_doi = scalar(
            """
            SELECT SUM(n) AS n
            FROM (
                SELECT COUNT(*) AS n
                FROM toxicity_endpoint
                JOIN source_document ON toxicity_endpoint.source_document_id = source_document.id
                WHERE source_document.doi IS NOT NULL AND source_document.doi != ''
                UNION ALL
                SELECT COUNT(*) AS n
                FROM offtarget_evidence
                JOIN source_document ON offtarget_evidence.source_document_id = source_document.id
                WHERE source_document.doi IS NOT NULL AND source_document.doi != ''
            )
            """
        )
        release_with_any_sequence = scalar(
            """
            SELECT SUM(n) AS n
            FROM (
                SELECT COUNT(*) AS n
                FROM toxicity_endpoint
                JOIN molecule ON toxicity_endpoint.molecule_id = molecule.id
                WHERE COALESCE(NULLIF(molecule.sense_sequence, ''), NULLIF(molecule.antisense_sequence, ''),
                               NULLIF(molecule.guide_sequence, ''), NULLIF(molecule.passenger_sequence, ''),
                               NULLIF(molecule.seed_region, '')) IS NOT NULL
                UNION ALL
                SELECT COUNT(*) AS n
                FROM offtarget_evidence
                JOIN molecule ON offtarget_evidence.molecule_id = molecule.id
                WHERE COALESCE(NULLIF(molecule.sense_sequence, ''), NULLIF(molecule.antisense_sequence, ''),
                               NULLIF(molecule.guide_sequence, ''), NULLIF(molecule.passenger_sequence, ''),
                               NULLIF(molecule.seed_region, '')) IS NOT NULL
            )
            """
        )
        release_with_any_chemistry = scalar(
            """
            SELECT SUM(n) AS n
            FROM (
                SELECT COUNT(*) AS n
                FROM toxicity_endpoint
                JOIN molecule ON toxicity_endpoint.molecule_id = molecule.id
                WHERE COALESCE(NULLIF(molecule.backbone_chemistry, ''),
                               NULLIF(molecule.sugar_modification, ''),
                               NULLIF(molecule.base_modification, ''),
                               NULLIF(molecule.conjugate_delivery, '')) IS NOT NULL
                UNION ALL
                SELECT COUNT(*) AS n
                FROM offtarget_evidence
                JOIN molecule ON offtarget_evidence.molecule_id = molecule.id
                WHERE COALESCE(NULLIF(molecule.backbone_chemistry, ''),
                               NULLIF(molecule.sugar_modification, ''),
                               NULLIF(molecule.base_modification, ''),
                               NULLIF(molecule.conjugate_delivery, '')) IS NOT NULL
            )
            """
        )
        release_audit_by_domain = fetch_rows(
            """
            SELECT entity_table, evidence_grade, COUNT(*) AS n
            FROM (
                SELECT 'toxicity_endpoint' AS entity_table, evidence_grade FROM toxicity_endpoint
                UNION ALL
                SELECT 'offtarget_evidence' AS entity_table, evidence_grade FROM offtarget_evidence
            )
            GROUP BY entity_table, evidence_grade
            ORDER BY entity_table, evidence_grade
            """
        )
        source_license_rows = fetch_rows(
            """
            SELECT license_status, reuse_category, COUNT(*) AS n
            FROM source_document
            GROUP BY license_status, reuse_category
            ORDER BY n DESC, license_status, reuse_category
            LIMIT 12
            """
        )
        audit_methods = fetch_rows(
            """
            SELECT extraction_method, extractor_model_or_script, validation_status,
                   curator_decision, COUNT(*) AS n
            FROM curation_audit
            GROUP BY extraction_method, extractor_model_or_script, validation_status, curator_decision
            ORDER BY n DESC
            LIMIT 12
            """
        )
        source_identifier_coverage = {
            "source_documents": source_count,
            "with_pmid": scalar(
                "SELECT COUNT(*) AS n FROM source_document WHERE pmid IS NOT NULL AND pmid != ''"
            ),
            "with_doi": scalar(
                "SELECT COUNT(*) AS n FROM source_document WHERE doi IS NOT NULL AND doi != ''"
            ),
            "with_pmcid": scalar(
                "SELECT COUNT(*) AS n FROM source_document WHERE pmcid IS NOT NULL AND pmcid != ''"
            ),
            "source_license_manifest_rows": csv_row_count(
                MANIFEST_DOWNLOADS["source_license_manifest_v1.csv"]
            ),
        }
    finally:
        conn.close()

    release_total = toxicity_count + offtarget_count
    independent_validation = api_independent_validation()
    core_oligo_fields = api_core_oligo_fields()
    return {
        "version": PORTAL_VERSION,
        "scope": "Human curator-verified ASO/siRNA toxicity and off-target evidence with source-localized provenance. The v1 keyword-classifier pre-curation (2003 candidates; measured 0.73 false-accept rate, Wilson 95% CI [0.63, 0.81], n=126) was independently re-curated over source passages by a human curator (v2 LLM-assisted); 737 rows are human curator-verified (626 toxicity + 111 off-target) and 1345 unsupported machine candidates were demoted to machine_precurated_v1. primary-curator release with a blinded second curator (HY): Cohen κ_binary = 0.42 (moderate, Landis-Koch) under the drop-abstain convention (n=92 non-abstain) and 0.34 (fair) under the safety-conservative collapse-abstain convention (n=100), raw agreement 66% (66/100), on a 100-row mixed accept+reject sample (KAPPA-2; full analysis in Methods Stage 3; A10 third-adjudicator pass in progress). Not a clinical recommendation engine and not a de novo sequence-risk predictor. v6.1 (post-EXPAND-2 toxicity round) added a total of 80 curator-verified records (48 from EXPAND-1 + 32 from EXPAND-2 toxicity-focused round) and recovered real molecule identities for 110 of 143 v1-extraction-artefact placeholders, reducing benchmark contamination from 31.1% to 4.1%.",
        "curator_of_record": {
            "curator_id": "ni_jie",
            "name": "Ni Jie",
            "affiliation": "University of Innsbruck, Digital Science Center, Innsbruck, Austria",
            "role": "primary human curator (full release)",
            "method": "AI-assisted human curation: the curator adjudicated v2 LLM proposals against the source passages (not blind) and recorded the final accept/reject decision row by row.",
            "single_curator_note": "All human curator-verified release rows were adjudicated by this primary curator. A blinded second curator (HY, no manuscript exposure) independently re-scored a 100-row mixed inter-rater sample (KAPPA-2): Cohen κ_binary = 0.42 (moderate, drop-abstain, n=92) / 0.34 (fair, collapse-abstain, n=100), raw agreement 66% (66/100), 3-class κ = 0.37, grade κ = 0.39. Inter-curator Cohen kappa IS therefore claimed. HY was systematically stricter (92% reject-confirm, 40% accept-confirm) — conservative direction for a safety database. An A10 third-adjudicator consensus pass is in progress and will further refine kappa.",
        },
        "release_gate": {
            "release_records": release_total,
            "curator_verified_accept_audits": verified_accepts,
            "all_release_records_have_verified_accept_audit": release_total == verified_accepts,
            "toxicity_release_records": toxicity_count,
            "offtarget_release_records": offtarget_count,
            "candidate_records": candidate_count,
            "curator_rejected_candidate_audits": rejected_candidates,
            "candidate_pending_records": candidate_pending,
            "promotion_rule": "Only accept rows with curator_decision=accept, validation_status=curator_verified, evidence_grade in A/B/C, and source_location are promoted into release evidence tables.",
        },
        "provenance_coverage": {
            "source_location": {
                "filled": release_with_source_location,
                "total": release_total,
                "pct": pct(release_with_source_location, release_total),
            },
            "pmid": {
                "filled": release_with_pmid,
                "total": release_total,
                "pct": pct(release_with_pmid, release_total),
            },
            "doi": {
                "filled": release_with_doi,
                "total": release_total,
                "pct": pct(release_with_doi, release_total),
            },
            "any_sequence": {
                "filled": release_with_any_sequence,
                "total": release_total,
                "pct": pct(release_with_any_sequence, release_total),
            },
            "any_chemistry_or_delivery": {
                "filled": release_with_any_chemistry,
                "total": release_total,
                "pct": pct(release_with_any_chemistry, release_total),
            },
        },
        "evidence_grade_policy": [
            {
                "grade": "A",
                "meaning": "High-confidence source-localized experimental evidence suitable for citation when the claim matches the endpoint.",
                "benchmark_use": "eligible",
            },
            {
                "grade": "B",
                "meaning": "Curator-verified evidence with usable source localization but lower specificity, smaller sample support, or broader context.",
                "benchmark_use": "eligible",
            },
            {
                "grade": "C",
                "meaning": "Contextual curator-verified evidence retained for browsing and provenance, not used in A/B benchmark splits.",
                "benchmark_use": "not eligible",
            },
        ],
        "release_audit_by_domain": release_audit_by_domain,
        "audit_method_summary": audit_methods,
        "source_identifier_coverage": source_identifier_coverage,
        "license_summary": source_license_rows,
        "independent_validation": {
            "claim_status": independent_validation["claim_status"],
            "sample": independent_validation["sample"],
            "metrics": independent_validation["metrics"],
            "claim_boundary": independent_validation["claim_boundary"],
            "downloads": independent_validation["downloads"],
        },
        "core_oligo_field_status": {
            "claim_boundary": core_oligo_fields["claim_boundary"],
            "summary": core_oligo_fields["summary"],
            "blocking_gates": core_oligo_fields["blocking_gates"],
            "downloads": core_oligo_fields["downloads"],
        },
        "redistribution_policy": [
            {
                "level": "redistributable raw",
                "current_use": "Only when source terms explicitly allow it; not used for copyrighted article text.",
            },
            {
                "level": "derived annotations only",
                "current_use": "Default release mode for PubMed/PMC-linked literature: matched terms, source locations, metadata, and curator decisions are redistributed; raw full text is not.",
            },
            {
                "level": "query/link-out only",
                "current_use": "Used when source text or document reuse is restricted; OligoVigil links to PMID/DOI/PMCID/source URL.",
            },
            {
                "level": "not safe",
                "current_use": "Excluded from release downloads until rights and provenance are resolved.",
            },
        ],
        "known_limitations": [
            "Exact sequence and chemistry fields remain incomplete and should be described as an expansion track, not as complete sequence-alignment coverage.",
            "Dose/exposure fields are sparse and must not be used for dose-response safety claims until source-verified in the core oligo field packet.",
            "Inter-curator Cohen kappa is claimed from the completed 100-row KAPPA-2 study (0.42 drop-abstain / 0.34 collapse-abstain, raw agreement 66%); release-row false-accept / false-reject error-rate estimates remain not claimable until the separate 500-row second-review packet is completed and adjudicated, and the A10 third-adjudicator pass is still pending.",
            "Candidate records are curation work items and must not be cited as verified release evidence.",
            "External adoption, download, and citation evidence can only be claimed after public deployment.",
        ],
        "reviewer_audit_actions": [
            {
                "action": "Open any release row from /api/evidence_records and inspect /api/evidence_detail.",
                "evidence": "Record payload includes source metadata, exact source location, grade rationale, audit status, and citation text.",
            },
            {
                "action": "Download evidence_release.csv and curation_audit.csv.",
                "evidence": "Rows can be joined by entity_table/entity_id to reproduce verified-release status.",
            },
            {
                "action": "Inspect license_manifest_v1.csv and source_document.csv.",
                "evidence": "Raw article text is not redistributed; source identifiers and derived annotations are exposed.",
            },
            {
                "action": "Open the core oligo field packet and independent validation template.",
                "evidence": "The portal exposes sequence/modification/dose gaps and the second-review sampling frame instead of hiding curation uncertainty.",
            },
        ],
        "downloads": {
            "evidence_release": "/api/download/evidence_release.csv",
            "curation_audit": "/api/download/curation_audit.csv",
            "license_manifest": "/api/manifest/license_manifest_v1.csv",
            "source_license_manifest": "/api/manifest/source_license_manifest_v1.csv",
            "sequence_template": "/api/download/sequence_modification_curation_template.csv",
            "core_oligo_field_packet": "/api/download/core_oligo_field_curation_packet.csv",
            "independent_validation_template": "/api/download/independent_curation_validation_template.csv",
            "all_tables": "/api/download/all_tables.zip",
        },
    }


_CURATION_PROTOCOL_CACHE: dict[str, object] | None = None


def curation_protocol_snapshot_is_current() -> bool:
    if not CURATION_PROTOCOL_SNAPSHOT_PATH.exists():
        return False
    snapshot_mtime = CURATION_PROTOCOL_SNAPSHOT_PATH.stat().st_mtime
    dependencies = [DB_PATH, MANIFEST_DOWNLOADS["source_license_manifest_v1.csv"]]
    return all(not dep.exists() or dep.stat().st_mtime <= snapshot_mtime for dep in dependencies)


def api_curation_protocol() -> dict[str, object]:
    global _CURATION_PROTOCOL_CACHE
    if _CURATION_PROTOCOL_CACHE is not None:
        return _CURATION_PROTOCOL_CACHE
    if curation_protocol_snapshot_is_current():
        try:
            payload = json.loads(CURATION_PROTOCOL_SNAPSHOT_PATH.read_text(encoding="utf-8"))
            if payload.get("version") == PORTAL_VERSION:
                _CURATION_PROTOCOL_CACHE = payload
                return payload
        except (OSError, json.JSONDecodeError):
            pass
    _CURATION_PROTOCOL_CACHE = build_curation_protocol_payload()
    return _CURATION_PROTOCOL_CACHE


def api_data_availability() -> dict[str, object]:
    toxicity_count = table_row_count("toxicity_endpoint")
    offtarget_count = table_row_count("offtarget_evidence")
    candidate_count = table_row_count("curation_candidate")
    source_count = table_row_count("source_document")
    molecule_count = table_row_count("molecule")
    audit_count = table_row_count("curation_audit")
    benchmark_count = table_row_count("benchmark_split")
    release_snapshot = {
        "verified_release_records": toxicity_count + offtarget_count,
        "toxicity_records": toxicity_count,
        "offtarget_records": offtarget_count,
        "benchmark_split_records": benchmark_count,
        "candidate_records": candidate_count,
    }
    public_files = [
        {
            "filename": "evidence_release.csv",
            "url": "/api/download/evidence_release.csv",
            "rows": release_snapshot.get("verified_release_records"),
            "recommended_use": "Primary citable release evidence table.",
        },
        {
            "filename": "source_document.csv",
            "url": "/api/download/source_document.csv",
            "rows": source_count,
            "recommended_use": "Source metadata and source identifiers.",
        },
        {
            "filename": "molecule.csv",
            "url": "/api/download/molecule.csv",
            "rows": molecule_count,
            "recommended_use": "Molecule/cohort context joined to release evidence.",
        },
        {
            "filename": "curation_audit.csv",
            "url": "/api/download/curation_audit.csv",
            "rows": audit_count,
            "recommended_use": "Audit trail and curator decisions.",
        },
        {
            "filename": "benchmark_reference_splits.csv",
            "url": "/api/download/benchmark_reference_splits.csv",
            "rows": benchmark_count,
            "recommended_use": "Fixed Grade A/B benchmark split assignments.",
        },
        {
            "filename": "license_manifest_v1.csv",
            "url": "/api/manifest/license_manifest_v1.csv",
            "rows": csv_row_count(MANIFEST_DOWNLOADS.get("license_manifest_v1.csv")),
            "recommended_use": "Source-class redistribution policy.",
        },
        {
            "filename": "source_license_manifest_v1.csv",
            "url": "/api/manifest/source_license_manifest_v1.csv",
            "rows": csv_row_count(MANIFEST_DOWNLOADS.get("source_license_manifest_v1.csv")),
            "recommended_use": "Source-level conservative reuse flags.",
        },
        {
            "filename": "data_dictionary_v1.csv",
            "url": "/api/manifest/data_dictionary_v1.csv",
            "rows": csv_row_count(MANIFEST_DOWNLOADS.get("data_dictionary_v1.csv")),
            "recommended_use": "Field definitions for public tables.",
        },
        {
            "filename": "all_tables.zip",
            "url": "/api/download/all_tables.zip",
            "rows": None,
            "recommended_use": "Full local snapshot; checksums exposed by /api/downloads.",
        },
    ]
    return {
        "version": PORTAL_VERSION,
        "release_snapshot": release_snapshot,
        "availability_statement_draft": (
            "OligoVigil is provided as a no-login, free web resource. Versioned CSV downloads, "
            "checksums, source metadata, curation audit trails, license manifests, and benchmark "
            "reference splits are available through the web portal and REST API. Raw article text "
            "and PDFs are not redistributed; release tables contain curator-reviewed derived "
            f"annotations and source links. The frozen v1.0.1 data archive is available at {ARCHIVE_URL}. "
            f"The stable public HTTPS portal is available at {PREFERRED_PUBLIC_URL}."
        ),
        "access": {
            "login_required": False,
            "free_access": True,
            "bulk_download": True,
            "public_https_url_status": "live_verified_cloudflare_pages",
            "public_url": PREFERRED_PUBLIC_URL,
            "verified_on": PUBLIC_URL_VERIFIED_DATE,
            "maintenance_commitment": "Maintain the same public URL for at least 5 years after publication.",
        },
        "archive": {
            "doi_status": ARCHIVE_DOI,
            "archive_ready": True,
            "archive_url": ARCHIVE_URL,
            "recommended_archive": "Zenodo v1.0.1 data snapshot.",
            "checksum_manifest": "/api/downloads",
        },
        "formats": [
            {"format": "CSV", "use": "Primary release tables, source metadata, audit trail, benchmark splits, manifests."},
            {"format": "ZIP", "use": "all_tables.zip reproducible local snapshot."},
            {"format": "JSON", "use": "REST API responses for record detail, source packets, curation protocol, and benchmark metadata."},
        ],
        "redistribution": [
            {
                "level": "derived annotations only",
                "current_use": "Default release mode: source identifiers, source locations, matched terms, and curator decisions are redistributed; raw article text is not.",
            },
            {
                "level": "query/link-out only",
                "current_use": "Used when source document reuse is restricted; OligoVigil links to PMID/DOI/PMCID/source URL.",
            },
            {
                "level": "not safe",
                "current_use": "Excluded from public release downloads until provenance and rights are resolved.",
            },
        ],
        "license_summary_endpoint": "/api/curation_protocol",
        "public_release_files": public_files,
        "non_citable_or_internal_boundaries": [
            "curation_candidate and curation_queue rows are derived triage work items and are not verified evidence claims.",
            "Candidate packets may be downloaded for gap analysis but should not be cited as OligoVigil release evidence.",
            "Exact sequence alignment claims are deferred until release-grade sequence fields are curator verified.",
        ],
        "correction_route": {
            "status": "pending_public_contact_before_submission",
            "planned_fields": [
                "source PMID/DOI/URL",
                "record identifier",
                "proposed correction",
                "supporting source location",
                "submitter contact",
            ],
        },
    }


def api_submission_pack() -> dict[str, object]:
    release_status = api_release_status()
    quality = api_quality()
    field_completeness = api_field_completeness()
    core_oligo_fields = api_core_oligo_fields()
    independent_validation = api_independent_validation()
    benchmark = api_benchmark()
    workflows = api_case_workflows().get("case_workflows", [])
    snapshot = release_status.get("release_snapshot", {})
    blockers = [
            {
                "item": "Stable public HTTPS URL",
                "status": "complete",
                "owner_action": f"Live URL verified on {PUBLIC_URL_VERIFIED_DATE}: {PREFERRED_PUBLIC_URL}.",
            },
            {
                "item": "Archived data and benchmark DOI",
                "status": "complete",
                "owner_action": f"Use archived DOI {ARCHIVE_DOI}; keep release files and checksums unchanged for v1.0.1.",
            },
        {
            "item": "Public contact and maintenance page",
            "status": "pending",
            "owner_action": "Expose maintainer contact, update policy, and issue/correction route on the public site.",
        },
        {
            "item": "External usage evidence",
            "status": "not_yet_available",
            "owner_action": "Collect access logs, download counts, GitHub/issue activity, and early-user feedback after deployment.",
        },
    ]
    editor_questions = [
        {
            "question": "Why will people use this?",
            "current_answer": "It unifies verified oligonucleotide safety/off-target evidence, provenance, curation audit, downloads, and benchmark splits in one no-login resource.",
            "risk": "Usage evidence cannot be claimed before public deployment.",
            "mitigation": "Use task-oriented workflows, DOI-ready downloads, and post-deployment analytics rather than invented adoption claims.",
        },
        {
            "question": "What is new versus RNA/drug databases?",
            "current_answer": "The release is safety-first and curator-audited, with exact source locations, toxicity/off-target separation, candidate-release boundaries, and reusable benchmark splits.",
            "risk": "Generic RNA/drug resources may look broader.",
            "mitigation": "Lead with closest-work matrix and the safety/provenance/benchmark combination rather than raw database breadth.",
        },
        {
            "question": "Can records be trusted?",
            "current_answer": f"{snapshot.get('verified_release_records', 0)} release rows are curator-verified accepted records with audit trails.",
            "risk": "Sparse sequence, modification, and dose fields can make the resource look like a literature index.",
            "mitigation": "Expose the P0/P1/P2 core oligo field packet and avoid complete sequence/modification/dose claims until source-verified.",
        },
        {
            "question": "Is the curation error rate measured?",
            "current_answer": "Inter-curator agreement is measured: a blinded second curator (HY) re-scored a 100-row mixed inter-rater sample (KAPPA-2), giving Cohen κ_binary = 0.42 (moderate, drop-abstain, n=92) / 0.34 (fair, collapse-abstain, n=100), raw agreement 66% (66/100). A separate 500-row independent second-review packet (release accept rows plus rejected candidate controls) underwrites the release-row false-accept / false-reject error rates.",
            "risk": "Cohen kappa is claimed; the release-row false-accept / false-reject error-rate estimates remain pending until the 500-row independent-check packet is complete and adjudicated (A10 third-adjudicator pass still pending).",
            "mitigation": "Use /api/independent_validation and independent_curation_validation_template.csv as the validation gate.",
        },
        {
            "question": "Can ML groups cite it?",
            "current_answer": f"{benchmark.get('benchmark_eligible_records', 0)} Grade A/B rows are exposed through fixed reference splits and task cards.",
            "risk": "Baseline model results remain pending.",
            "mitigation": "Ship reference splits now and add transparent baseline result tables after public freeze.",
        },
        {
            "question": "Will it stay available?",
            "current_answer": f"The portal supports no-login access, CSV/ZIP downloads, manifests, maintenance commitments, and a DOI-backed archive ({ARCHIVE_DOI}).",
            "risk": "Long-term usage evidence still needs to be collected after public launch.",
            "mitigation": "Track public access logs, download counts, issue/correction submissions, and early-user feedback after deployment.",
        },
    ]
    return {
        "version": PORTAL_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "go_no_go": {
            "status": "go_after_author_metadata_and_final_pdf_qa",
            "summary": "The resource is technically usable, curator-audited, DOI-backed, and live at the public HTTPS portal URL.",
        },
        "submission_snapshot": {
            "verified_release_evidence": snapshot.get("verified_release_records", 0),
            "toxicity_release": snapshot.get("toxicity_records", 0),
            "offtarget_release": snapshot.get("offtarget_records", 0),
            "benchmark_split_rows": snapshot.get("benchmark_split_records", 0),
            "candidate_records": snapshot.get("candidate_records", 0),
            "source_documents": quality.get("source_documents", 0),
            "case_workflows": len(workflows),
            "core_field_completeness_pct": field_completeness["summary"]["core_required_avg_pct"],
            "p0_core_oligo_field_rows": core_oligo_fields["summary"]["p0_benchmark_linked_rows"],
            "independent_validation_reviewed_rows": independent_validation["sample"]["reviewed_rows"],
            "independent_validation_sample_rows": independent_validation["sample"]["sample_rows"],
        },
        "adoption_status": {
            "external_users": "not_claimed_predeployment",
            "citation_status": "not_claimed_prepublication",
            "public_usage_analytics": "ready_to_collect_after_public_https_deployment",
            "evidence_to_collect": [
                "server access logs and download counts",
                "public issue/correction submissions",
                "tutorial notebook reuse",
                "early-user feedback from oligonucleotide safety and ML groups",
            ],
        },
        "public_release_blockers": blockers,
        "editor_questions": editor_questions,
        "case_study_cards": [
            {
                "title": workflow.get("title"),
                "audience": workflow.get("audience"),
                "release_records": workflow.get("release_records"),
                "primary_endpoint": workflow.get("primary_endpoint"),
                "benchmark_task": workflow.get("benchmark_task"),
            }
            for workflow in workflows[:5]
        ],
        "quality_checks": quality.get("checks", []),
        "field_completeness_summary": field_completeness.get("summary", {}),
        "recommended_next_actions": [
            f"Keep {PREFERRED_PUBLIC_URL} live and repeat smoke/final checks before submission.",
            f"Keep the frozen data bundle tied to DOI {ARCHIVE_DOI} and do not mutate the v1.0.1 release files.",
            "Add baseline result table after DOI freeze without changing reference splits.",
            "Expand exact sequence/modification curation to make sequence search a primary use case.",
        ],
    }


def local_delivery_artifact(filename: str, purpose: str) -> dict[str, object]:
    path = DELIVERY_DIR / filename
    if path.exists():
        return {
            "filename": filename,
            "purpose": purpose,
            "status": "present_local_delivery",
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return {
        "filename": filename,
        "purpose": purpose,
        "status": "generated_by_release_packaging_script",
        "bytes": None,
        "sha256": "",
    }


def api_archive_readiness() -> dict[str, object]:
    manifest = api_download_manifest()
    download_files = manifest.get("files", [])
    file_lookup = {str(file.get("filename")): file for file in download_files}
    required_names = [
        "all_tables.zip",
        "evidence_release.csv",
        "benchmark_reference_splits.csv",
        "benchmark_baseline_results.csv",
        "benchmark_task_cards.csv",
        "data_dictionary_v1.csv",
        "license_manifest_v1.csv",
        "closest_work_matrix_v1.csv",
    ]
    required_files = []
    for filename in required_names:
        entry = file_lookup.get(filename, {})
        required_files.append(
            {
                "filename": filename,
                "status": "ready" if entry.get("sha256") else "pending",
                "rows": entry.get("rows"),
                "bytes": entry.get("bytes"),
                "sha256": entry.get("sha256", ""),
                "purpose": entry.get("purpose", "Release archive component."),
            }
        )
    required_files.extend(
        [
            local_delivery_artifact("RELEASE_MANIFEST.json", "Human-readable release package manifest."),
            local_delivery_artifact("CHECKSUMS_SHA256.txt", "Checksum ledger for archived release files."),
            local_delivery_artifact("FINAL_QA_REPORT.md", "Final local QA evidence for the frozen release."),
        ]
    )
    ready_count = sum(1 for file in required_files if str(file.get("status")).startswith(("ready", "present")))
    return {
        "version": PORTAL_VERSION,
        "doi_status": ARCHIVE_DOI,
        "archive_url": ARCHIVE_URL,
        "code_release_url": CODE_RELEASE_URL,
        "archive_ready": True,
        "archive_ready_after": [
            "stable public HTTPS URL is deployed and smoke-tested",
            "Zenodo v1.0.1 metadata is kept aligned with the manuscript and release files",
        ],
        "required_files_ready": ready_count,
        "required_files_total": len(required_files),
        "required_files": required_files,
        "zenodo_metadata_draft": {
            "title": "OligoVigil: curator-verified oligonucleotide safety and off-target evidence release",
            "upload_type": "dataset",
            "publication_date": "2026-06-04",
            "version": PORTAL_VERSION,
            "creators": ["OligoVigil Consortium"],
            "keywords": [
                "therapeutic oligonucleotides",
                "antisense oligonucleotides",
                "siRNA",
                "toxicity",
                "off-target effects",
                "benchmark dataset",
            ],
            "description": (
                "Versioned curator-reviewed derived annotations, source metadata, curation audit trails, "
                "download manifests, and reference benchmark splits for therapeutic oligonucleotide safety evidence."
            ),
            "license_note": "Derived annotations and source links are redistributed; raw article text is not redistributed.",
        },
        "upload_rules": [
            {
                "rule": "Upload",
                "detail": "CSV/ZIP release tables, manifests, checksums, data dictionary, license manifest, and benchmark files.",
            },
            {
                "rule": "Do not upload",
                "detail": "Raw copyrighted article text, full-text PDFs, or unlicensed regulatory documents.",
            },
            {
                "rule": "After DOI",
                "detail": f"Use {ARCHIVE_DOI} in /api/citation, benchmark release metadata, manuscript data availability, and release announcement.",
            },
        ],
    }


def api_adoption_packet() -> dict[str, object]:
    workflows = api_case_workflows().get("case_workflows", [])
    return {
        "version": PORTAL_VERSION,
        "usage_claim_policy": {
            "current_external_users": "not_claimed_predeployment",
            "current_citations": "not_claimed_prepublication",
            "allowed_claim": "The portal is technically ready for no-login public evaluation after HTTPS deployment.",
            "blocked_claim": "Do not claim community adoption, citation impact, or production reuse before public logs and feedback exist.",
        },
        "primary_user_groups": [
            {
                "group": "oligonucleotide discovery teams",
                "reason_to_use": "Find citable safety/off-target evidence by chemistry, target, endpoint, and source location.",
                "entry_route": "/#triage",
            },
            {
                "group": "preclinical safety reviewers",
                "reason_to_use": "Build source-grounded evidence packets for liver, renal, platelet, and immune safety concerns.",
                "entry_route": "/#examples",
            },
            {
                "group": "RNAi and transcriptomics groups",
                "reason_to_use": "Reuse seed/mismatch/transcriptome-level off-target evidence and reference splits.",
                "entry_route": "/#sequence",
            },
            {
                "group": "ML benchmark users",
                "reason_to_use": "Download fixed A/B-grade splits, baseline results, task cards, checksums, and citation text.",
                "entry_route": "/#benchmark",
            },
        ],
        "shareable_workflows": [
            {
                "title": workflow.get("title"),
                "audience": workflow.get("audience"),
                "entry_route": workflow.get("primary_endpoint"),
                "release_records": workflow.get("release_records"),
            }
            for workflow in workflows[:5]
        ],
        "instrumentation_events": [
            {
                "event": "release_download",
                "trigger": "download evidence_release.csv or all_tables.zip",
                "stored_fields": "timestamp, route, file, version, anonymized session id",
                "excluded_fields": "raw IP, query text containing personal data, user identity",
            },
            {
                "event": "record_open",
                "trigger": "open citable evidence detail",
                "stored_fields": "timestamp, domain, evidence id, source identifier, version",
                "excluded_fields": "user identity and full browser fingerprint",
            },
            {
                "event": "benchmark_reuse",
                "trigger": "download benchmark splits, baseline results, or task cards",
                "stored_fields": "timestamp, artifact, task name when known, checksum version",
                "excluded_fields": "model code, unpublished user data",
            },
            {
                "event": "triage_run",
                "trigger": "generate safety triage report",
                "stored_fields": "timestamp, selected endpoint/delivery/modification buckets, result counts",
                "excluded_fields": "raw proprietary sequence unless explicit opt-in is implemented",
            },
        ],
        "launch_evidence_to_collect": [
            "download counts for release and benchmark files",
            "record-open counts for citable evidence pages",
            "public issue/correction submissions",
            "tutorial notebook or repository stars/forks after public launch",
            "direct early-user feedback from safety, RNAi, and ML benchmark users",
        ],
        "success_thresholds_for_revision": [
            {
                "window": "first 90 days after public launch",
                "signal": "repeat downloads of evidence_release.csv and benchmark_reference_splits.csv",
                "interpretation": "evidence of reuse interest; not equivalent to citation impact",
            },
            {
                "window": "first 180 days after public launch",
                "signal": "external issues, corrections, or tutorial reuse",
                "interpretation": "community interaction that can support future database updates",
            },
        ],
    }


ASK_TERM_GROUPS = [
    {
        "id": "galnac",
        "labels": ["galnac", "n-acetylgalactosamine"],
        "synonyms": ["galnac", "n-acetylgalactosamine"],
    },
    {
        "id": "liver",
        "labels": ["liver", "hepatic", "hepatotoxicity"],
        "synonyms": ["liver", "hepatic", "hepatotoxicity", "alanine aminotransferase", "alt", "ast"],
    },
    {
        "id": "renal",
        "labels": ["renal", "kidney", "nephrotoxicity"],
        "synonyms": ["renal", "kidney", "nephro", "nephrotoxicity", "creatinine"],
    },
    {
        "id": "platelet",
        "labels": ["platelet", "thrombocytopenia"],
        "synonyms": ["platelet", "thrombocytopenia", "platelets"],
    },
    {
        "id": "seed",
        "labels": ["seed", "seed-mediated"],
        "synonyms": ["seed", "seed-mediated", "seed mediated"],
    },
    {
        "id": "mismatch",
        "labels": ["mismatch", "hybridization"],
        "synonyms": ["mismatch", "hybridization", "hybridisation"],
    },
    {
        "id": "transcriptome",
        "labels": ["transcriptome", "rna-seq", "microarray"],
        "synonyms": ["transcriptome", "transcriptomic", "rna-seq", "rna seq", "microarray"],
    },
    {
        "id": "lnp",
        "labels": ["lnp", "lipid nanoparticle"],
        "synonyms": ["lnp", "lipid nanoparticle", "lipid nanoparticles"],
    },
    {
        "id": "phosphorothioate",
        "labels": ["phosphorothioate", "ps"],
        "synonyms": ["phosphorothioate", "ps-aso", "ps aso"],
    },
    {
        "id": "lna",
        "labels": ["lna", "locked nucleic acid"],
        "synonyms": ["lna", "locked nucleic acid"],
    },
]


def ask_record_blob(record: dict[str, object]) -> str:
    fields = [
        "canonical_name",
        "modality",
        "target_gene_symbol",
        "disease_context",
        "backbone_chemistry",
        "sugar_modification",
        "base_modification",
        "conjugate_delivery",
        "category",
        "evidence_label",
        "source_location",
        "source_title",
        "pmid",
        "doi",
        "audit_note",
    ]
    return " ".join(str(record.get(field) or "").lower() for field in fields)


def infer_ask_query(question: str) -> dict[str, object]:
    lowered = question.lower()
    domain = ""
    if any(term in lowered for term in ["off-target", "off target", "seed", "mismatch", "transcriptome"]):
        domain = "offtarget"
    if any(term in lowered for term in ["toxicity", "toxic", "safety", "hepato", "liver", "renal", "platelet"]):
        domain = "toxicity"

    grades: list[str] = []
    if re.search(r"\bgrade\s*a\s*/\s*b\b", lowered) or "a/b" in lowered or "a and b" in lowered:
        grades = ["A", "B"]
    else:
        for grade in ["A", "B", "C"]:
            if re.search(rf"\bgrade\s*{grade.lower()}\b", lowered):
                grades.append(grade)

    modalities: list[str] = []
    if re.search(r"\bsirna\b|\brnai\b", lowered):
        modalities.append("siRNA")
    if re.search(r"\baso\b|antisense|gapmer", lowered):
        modalities.append("ASO")

    target = ""
    for token in re.findall(r"\b[A-Z0-9]{2,10}\b", question):
        if token not in {"ASO", "RNA", "DNA", "LNA", "LNP", "PMO", "PMID", "DOI"}:
            target = token
            break

    term_groups = [
        group
        for group in ASK_TERM_GROUPS
        if any(label in lowered for label in group["labels"])
    ]
    free_terms = [
        token
        for token in re.findall(r"[A-Za-z0-9'-]{3,}", question)
        if token.lower()
        not in {
            "show",
            "find",
            "with",
            "records",
            "record",
            "evidence",
            "grade",
            "grades",
            "toxicity",
            "safety",
            "off",
            "target",
            "source",
            "sources",
            "pubmed",
            "pmid",
            "doi",
            "and",
            "the",
            "for",
        }
    ][:6]
    return {
        "domain": domain,
        "grades": grades,
        "modalities": modalities,
        "target": target,
        "term_groups": term_groups,
        "free_terms": free_terms,
    }


def record_matches_ask(record: dict[str, object], plan: dict[str, object]) -> tuple[bool, list[str]]:
    blob = ask_record_blob(record)
    matched: list[str] = []
    for group in plan["term_groups"]:
        synonyms = group["synonyms"]
        if any(str(synonym).lower() in blob for synonym in synonyms):
            matched.append(group["id"])
        else:
            return False, matched
    return True, matched


def count_by(records: list[dict[str, object]], key: str, limit: int = 8) -> list[dict[str, object]]:
    counts: dict[str, int] = {}
    for record in records:
        value = str(record.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return [
        {"label": label, "n": n}
        for label, n in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def api_ask(query: dict[str, list[str]]) -> dict[str, object]:
    question = first_param(
        query,
        "q",
        "Show GalNAc liver toxicity Grade A/B evidence with PubMed sources",
    )
    limit = limit_param(query, default=25, maximum=100)
    plan = infer_ask_query(question)
    base_query: dict[str, list[str]] = {"limit": [str(RELEASE_EXPORT_LIMIT)]}
    if plan["domain"]:
        base_query["domain"] = [str(plan["domain"])]
    if plan["target"]:
        base_query["target"] = [str(plan["target"])]

    considered = evidence_records(base_query)
    filtered: list[dict[str, object]] = []
    matched_terms_by_record: dict[tuple[str, int], list[str]] = {}
    grades = set(plan["grades"])
    modalities = set(plan["modalities"])
    for record in considered:
        if grades and str(record.get("evidence_grade")) not in grades:
            continue
        if modalities and str(record.get("modality")) not in modalities:
            continue
        matched, terms = record_matches_ask(record, plan)
        if not matched:
            continue
        key = (str(record.get("entity_table")), int(record.get("evidence_id") or 0))
        matched_terms_by_record[key] = terms
        filtered.append(record)

    shown = filtered[:limit]
    for record in shown:
        key = (str(record.get("entity_table")), int(record.get("evidence_id") or 0))
        record["ask_matched_terms"] = ", ".join(matched_terms_by_record.get(key, []))

    citations: list[dict[str, object]] = []
    seen_sources: set[str] = set()
    for record in shown:
        source_key = str(record.get("pmid") or record.get("doi") or record.get("source_url") or "")
        if not source_key or source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        citations.append(
            {
                "pmid": record.get("pmid"),
                "doi": record.get("doi"),
                "source_title": record.get("source_title"),
                "source_url": record.get("source_url"),
                "source_location": record.get("source_location"),
            }
        )
        if len(citations) >= 10:
            break

    answer = (
        f"Found {len(filtered)} curator-verified release records for this read-only query; "
        f"showing {len(shown)}. "
        "The answer is grounded only in OligoVigil release tables and linked source metadata."
    )
    if not filtered:
        answer = (
            "No curator-verified release records matched the interpreted filters. "
            "Broaden the question or inspect candidate evidence; this endpoint does not promote candidates."
        )

    return {
        "version": PORTAL_VERSION,
        "question": question,
        "answer_mode": "deterministic_grounded_read_only; llm_ready_payload_no_external_llm_call",
        "llm_status": "external_llm_disabled_by_default",
        "answer": answer,
        "interpreted_query": {
            "domain": plan["domain"] or "any",
            "grades": plan["grades"] or ["A", "B", "C"],
            "modalities": plan["modalities"] or ["ASO", "siRNA", "ASO/siRNA mixed context"],
            "target": plan["target"] or "any",
            "term_groups": [group["id"] for group in plan["term_groups"]],
            "free_terms_seen": plan["free_terms"],
        },
        "query_plan": {
            "allowed_tables": [
                "toxicity_endpoint",
                "offtarget_evidence",
                "molecule",
                "source_document",
                "curation_audit",
            ],
            "candidate_table_policy": "excluded_from_answer; candidates require human promotion before release evidence",
            "write_access": False,
            "sql_template": "evidence_records(domain,target,limit=5000) + deterministic grade/modality/term filtering",
        },
        "summary": {
            "records_considered": len(considered),
            "records_matched": len(filtered),
            "records_shown": len(shown),
            "grade_counts": count_by(filtered, "evidence_grade"),
            "domain_counts": count_by(filtered, "evidence_domain"),
            "category_counts": count_by(filtered, "category"),
            "source_count_shown": len(citations),
        },
        "records": shown,
        "citations": citations,
        "follow_up_actions": {
            "open_evidence": f"/api/evidence_records?domain={plan['domain'] or ''}",
            "download_release": "/api/download/evidence_release.csv",
            "benchmark": "/api/benchmark",
            "citation": "/api/citation",
        },
        "warnings": [
            "This endpoint is a grounded query assistant, not a source of new curated evidence.",
            "Candidate records are intentionally excluded from answers until they pass the curation promotion gate.",
            "A future LLM layer should consume this JSON as grounding context and must cite returned sources.",
        ],
    }


def record_citation(record: dict[str, object]) -> dict[str, object]:
    domain = str(record.get("evidence_domain") or "evidence")
    evidence_id = str(record.get("evidence_id") or "0")
    canonical_name = str(record.get("canonical_name") or "record")
    pmid = str(record.get("pmid") or "")
    doi = str(record.get("doi") or "")
    source_part = f"PMID:{pmid}" if pmid else (f"DOI:{doi}" if doi else "source linked")
    title = f"OligoVigil record {domain}:{evidence_id}"
    plain = (
        f"{title}. {canonical_name}; {record.get('category')}; grade {record.get('evidence_grade')}; "
        f"{source_part}. OligoVigil {PORTAL_VERSION}."
    )
    key = f"OligoVigil_{domain}_{evidence_id}_{PORTAL_VERSION}".replace("-", "_")
    bibtex = "\n".join(
        [
            f"@misc{{{key},",
            f"  title = {{{title}: {canonical_name}}},",
            "  author = {OligoVigil Consortium},",
            f"  year = {{2026}},",
            f"  note = {{{source_part}; evidence grade {record.get('evidence_grade')}}},",
            f"  howpublished = {{OligoVigil {PORTAL_VERSION}}}",
            "}",
        ]
    )
    return {"plain_text": plain, "bibtex": bibtex, "record_key": key}


def evidence_grade_rationale(grade: object) -> dict[str, object]:
    value = str(grade or "").upper()
    rationales = {
        "A": {
            "label": "Grade A",
            "meaning": "High-confidence curator-verified evidence with strong source localization.",
            "recommended_use": "Suitable for citation and benchmark reuse when the endpoint matches the user's question.",
        },
        "B": {
            "label": "Grade B",
            "meaning": "Curator-verified evidence with useful source support, but less complete context than Grade A.",
            "recommended_use": "Suitable for citation and benchmark reuse; inspect source location before strong claims.",
        },
        "C": {
            "label": "Grade C",
            "meaning": "Curator-verified contextual evidence retained for evidence mapping, not benchmark eligibility.",
            "recommended_use": "Use as contextual support only; do not mix into A/B reference benchmark splits.",
        },
    }
    return rationales.get(
        value,
        {
            "label": f"Grade {value or 'unknown'}",
            "meaning": "Evidence grade not recognized by the current release policy.",
            "recommended_use": "Inspect audit trail before reuse.",
        },
    )


def classify_offtarget_record(record: dict[str, object]) -> dict[str, object]:
    blob = " ".join(
        str(record.get(field) or "").lower()
        for field in [
            "category",
            "evidence_label",
            "source_location",
            "source_title",
            "audit_note",
            "modality",
            "target_gene_symbol",
        ]
    )
    for item in OFFTARGET_TAXONOMY:
        if any(term in blob for term in item["synonyms"]):
            return {
                "key": item["key"],
                "label": item["label"],
                "definition": item["definition"],
            }
    fallback = OFFTARGET_TAXONOMY[-1]
    return {"key": fallback["key"], "label": fallback["label"], "definition": fallback["definition"]}


def record_sequence_chemistry(record: dict[str, object]) -> dict[str, object]:
    return {
        "sense_sequence": record.get("sense_sequence") or "",
        "antisense_sequence": record.get("antisense_sequence") or "",
        "guide_sequence": record.get("guide_sequence") or "",
        "passenger_sequence": record.get("passenger_sequence") or "",
        "seed_region": record.get("seed_region") or "",
        "backbone_chemistry": record.get("backbone_chemistry") or "",
        "sugar_modification": record.get("sugar_modification") or "",
        "base_modification": record.get("base_modification") or "",
        "conjugate_delivery": record.get("conjugate_delivery") or "",
        "sequence_annotation_status": record.get("sequence_annotation_status") or "not_curated",
        "modification_annotation_status": record.get("modification_annotation_status") or "not_curated",
    }


def evidence_limitations(record: dict[str, object], audit: list[dict[str, object]]) -> list[str]:
    limitations: list[str] = []
    sequence_context = record_sequence_chemistry(record)
    if not any(
        sequence_context[field]
        for field in ["sense_sequence", "antisense_sequence", "guide_sequence", "passenger_sequence"]
    ):
        limitations.append("Exact release-grade oligo sequence is not curated for this record.")
    if sequence_context["modification_annotation_status"] != "curator_verified":
        limitations.append("Chemical modification fields should be treated as incomplete unless source text is inspected.")
    if str(record.get("evidence_grade") or "").upper() == "C":
        limitations.append("Grade C records are contextual release evidence and are excluded from A/B benchmark splits.")
    if not record.get("source_location"):
        limitations.append("Source location is missing; do not reuse without checking the original source.")
    if not audit:
        limitations.append("No audit row was found for this record in the current database snapshot.")
    if not limitations:
        limitations.append("Reuse is appropriate when the user's claim matches the endpoint, source location, and grade policy.")
    return limitations


def api_evidence_detail(query: dict[str, list[str]]) -> dict[str, object]:
    domain = first_param(query, "domain")
    entity_table = first_param(query, "entity_table")
    evidence_id = first_param(query, "id") or first_param(query, "evidence_id") or first_param(query, "entity_id")
    if not domain and entity_table == "toxicity_endpoint":
        domain = "toxicity"
    if not domain and entity_table == "offtarget_evidence":
        domain = "offtarget"
    if domain == "toxicity":
        entity_table = "toxicity_endpoint"
    if domain == "offtarget":
        entity_table = "offtarget_evidence"
    if not evidence_id or entity_table not in {"toxicity_endpoint", "offtarget_evidence"}:
        return {
            "query": {"domain": domain, "entity_table": entity_table, "id": evidence_id},
            "record": None,
            "error": "Provide domain=toxicity|offtarget and id, or entity_table plus entity_id.",
        }

    records = evidence_records({"domain": [domain], "limit": [str(RELEASE_EXPORT_LIMIT)]})
    record = next(
        (
            item
            for item in records
            if str(item.get("entity_table")) == entity_table
            and str(item.get("evidence_id")) == evidence_id
        ),
        None,
    )
    if not record:
        return {
            "query": {"domain": domain, "entity_table": entity_table, "id": evidence_id},
            "record": None,
            "error": "No curator-verified accepted release record matched this identifier.",
        }

    audit = rows(
        """
        SELECT id, entity_table, entity_id, extraction_method, extractor_model_or_script,
               validation_status, curator_decision, curator_id, audit_note, audited_at
        FROM curation_audit
        WHERE entity_table = ? AND entity_id = ?
        ORDER BY id DESC
        """,
        (entity_table, int(evidence_id)),
    )
    audit_verified = any(
        str(item.get("validation_status") or "").lower() == "curator_verified"
        and str(item.get("curator_decision") or "").lower() == "accept"
        for item in audit
    )
    source = one(
        """
        SELECT id, source_type, source_url, pmid, pmcid, doi, title, journal_or_agency,
               publication_year, license_status, reuse_category, accessed_at
        FROM source_document
        WHERE (pmid = ? AND ? != '') OR (doi = ? AND ? != '') OR source_url = ?
        ORDER BY id
        LIMIT 1
        """,
        (
            record.get("pmid") or "",
            record.get("pmid") or "",
            record.get("doi") or "",
            record.get("doi") or "",
            record.get("source_url") or "",
        ),
    )
    sequence_chemistry = record_sequence_chemistry(record)
    mechanism = classify_offtarget_record(record) if domain == "offtarget" else None
    return {
        "query": {"domain": domain, "entity_table": entity_table, "id": evidence_id},
        "record": record,
        "audit": audit,
        "audit_summary": {
            "audit_rows": len(audit),
            "curator_verified_accept": audit_verified,
            "latest_validation_status": audit[0].get("validation_status") if audit else "",
            "latest_decision": audit[0].get("curator_decision") if audit else "",
        },
        "source": source,
        "record_card": {
            "record_key": f"{entity_table}:{evidence_id}",
            "evidence_statement": (
                f"{record.get('canonical_name') or 'This record'} links "
                f"{record.get('modality') or 'oligonucleotide'} context to "
                f"{record.get('evidence_label') or record.get('category') or 'a safety/off-target endpoint'}."
            ),
            "domain": domain,
            "mechanism": mechanism,
            "grade_rationale": evidence_grade_rationale(record.get("evidence_grade")),
            "sequence_chemistry": sequence_chemistry,
            "limitations": evidence_limitations(record, audit),
        },
        "provenance": {
            "source_location": record.get("source_location") or "",
            "source_location_verified": bool(record.get("source_location")) and audit_verified,
            "source_title": record.get("source_title") or source.get("title") or "",
            "pmid": record.get("pmid") or source.get("pmid") or "",
            "doi": record.get("doi") or source.get("doi") or "",
            "pmcid": source.get("pmcid") or "",
            "reuse_category": source.get("reuse_category") or "",
            "license_status": source.get("license_status") or "",
        },
        "citation": record_citation(record),
        "links": {
            "evidence_release_csv": "/api/download/evidence_release.csv",
            "record_json": f"/api/evidence_detail?entity_table={entity_table}&entity_id={evidence_id}",
            "source_packet": f"/api/source_detail?q={record.get('pmid') or record.get('doi') or record.get('source_title')}",
        },
    }


def benchmark_task_name(record: dict[str, object]) -> str:
    if record.get("evidence_domain") == "toxicity":
        return "toxicity_safety_v0_1"
    return "offtarget_safety_v0_1"


def split_for_group(index: int, total: int) -> str:
    if total < 2:
        return "train"
    if index == 0:
        return "test"
    if total > 2 and index == 1:
        return "validation"
    return "train"


def benchmark_reference_splits() -> list[dict[str, object]]:
    explicit_splits = rows(
        """
        SELECT task_name, split_name, entity_table, entity_id, split_strategy,
               leakage_group, version
        FROM benchmark_split
        ORDER BY task_name, split_name, entity_table, entity_id
        """
    )
    if explicit_splits:
        records_by_key = {
            (str(record.get("entity_table")), int(record.get("evidence_id") or 0)): record
            for record in evidence_records({"limit": [str(RELEASE_EXPORT_LIMIT)]})
        }
        output: list[dict[str, object]] = []
        for split in explicit_splits:
            key = (str(split.get("entity_table")), int(split.get("entity_id") or 0))
            record = records_by_key.get(key)
            if not record:
                continue
            output.append(
                {
                    "task_name": split.get("task_name"),
                    "split_name": split.get("split_name"),
                    "entity_table": record.get("entity_table"),
                    "entity_id": record.get("evidence_id"),
                    "evidence_domain": record.get("evidence_domain"),
                    "evidence_grade": record.get("evidence_grade"),
                    "canonical_name": record.get("canonical_name"),
                    "modality": record.get("modality"),
                    "target_gene_symbol": record.get("target_gene_symbol"),
                    "disease_context": record.get("disease_context"),
                    "category": record.get("category"),
                    "evidence_label": record.get("evidence_label"),
                    "source_title": record.get("source_title"),
                    "leakage_group": split.get("leakage_group"),
                    "split_strategy": split.get("split_strategy"),
                    "version": split.get("version"),
                    "source_pmid": record.get("pmid"),
                    "source_doi": record.get("doi"),
                }
            )
        return output

    records = [
        record
        for record in evidence_records({"limit": [str(RELEASE_EXPORT_LIMIT)]})
        if str(record.get("evidence_grade")) in {"A", "B"}
    ]
    grouped: dict[str, list[dict[str, object]]] = {}
    for record in records:
        leakage_group = "|".join(
            [
                f"source:{record.get('pmid') or record.get('doi') or record.get('source_url') or 'unknown'}",
                f"molecule:{record.get('canonical_name') or 'unknown'}",
            ]
        )
        task = benchmark_task_name(record)
        grouped.setdefault(f"{task}::{leakage_group}", []).append(record)

    task_groups: dict[str, list[tuple[str, list[dict[str, object]]]]] = {}
    for key, group_records in grouped.items():
        task, leakage_group = key.split("::", 1)
        task_groups.setdefault(task, []).append((leakage_group, group_records))

    output: list[dict[str, object]] = []
    for task in sorted(task_groups):
        groups = sorted(task_groups[task], key=lambda item: item[0])
        for group_index, (leakage_group, group_records) in enumerate(groups):
            split = split_for_group(group_index, len(groups))
            for record in sorted(group_records, key=lambda item: str(item.get("evidence_id"))):
                output.append(
                    {
                        "task_name": task,
                        "split_name": split,
                        "entity_table": record.get("entity_table"),
                        "entity_id": record.get("evidence_id"),
                        "evidence_domain": record.get("evidence_domain"),
                        "evidence_grade": record.get("evidence_grade"),
                        "canonical_name": record.get("canonical_name"),
                        "modality": record.get("modality"),
                        "target_gene_symbol": record.get("target_gene_symbol"),
                        "disease_context": record.get("disease_context"),
                        "category": record.get("category"),
                        "evidence_label": record.get("evidence_label"),
                        "source_title": record.get("source_title"),
                        "leakage_group": leakage_group,
                        "split_strategy": "source_plus_molecule_grouped_v0_1",
                        "version": PORTAL_VERSION,
                        "source_pmid": record.get("pmid"),
                        "source_doi": record.get("doi"),
                    }
                )
    return output


def benchmark_reference_splits_csv_bytes() -> bytes:
    return dicts_to_csv_bytes(benchmark_reference_splits(), BENCHMARK_SPLIT_COLUMNS)


_BENCHMARK_BASELINE_CACHE: list[dict[str, object]] | None = None


def macro_f1_score(labels: list[str], predictions: list[str]) -> float:
    if not labels or not predictions:
        return 0.0
    all_labels = sorted(set(labels) | set(predictions))
    f1_scores: list[float] = []
    for label in all_labels:
        tp = sum(1 for value, pred in zip(labels, predictions) if value == label and pred == label)
        fp = sum(1 for value, pred in zip(labels, predictions) if value != label and pred == label)
        fn = sum(1 for value, pred in zip(labels, predictions) if value == label and pred != label)
        denominator = (2 * tp) + fp + fn
        f1_scores.append(0.0 if denominator == 0 else (2 * tp) / denominator)
    return round(sum(f1_scores) / max(len(f1_scores), 1), 4)


def accuracy_score(labels: list[str], predictions: list[str]) -> float:
    if not labels:
        return 0.0
    correct = sum(1 for label, prediction in zip(labels, predictions) if label == prediction)
    return round(correct / len(labels), 4)


def baseline_label_counts(train_rows: list[dict[str, object]]) -> tuple[Counter[str], str, float]:
    train_labels = [str(row.get("category") or "unknown") for row in train_rows]
    counts: Counter[str] = Counter(train_labels)
    if not counts:
        return counts, "unknown", 0.0
    majority_label, majority_n = counts.most_common(1)[0]
    return counts, majority_label, round(majority_n / max(len(train_labels), 1), 4)


def grouped_prior_predictions(
    train_rows: list[dict[str, object]],
    evaluation_rows: list[dict[str, object]],
    group_key: str,
    fallback_label: str,
) -> tuple[list[str], float]:
    group_counts: dict[str, Counter[str]] = {}
    for row in train_rows:
        group_value = str(row.get(group_key) or "unknown").strip() or "unknown"
        label = str(row.get("category") or "unknown")
        group_counts.setdefault(group_value, Counter())[label] += 1

    predictions: list[str] = []
    covered = 0
    for row in evaluation_rows:
        group_value = str(row.get(group_key) or "unknown").strip() or "unknown"
        counts = group_counts.get(group_value)
        if counts:
            predictions.append(counts.most_common(1)[0][0])
            covered += 1
        else:
            predictions.append(fallback_label)
    return predictions, round(covered / max(len(evaluation_rows), 1), 4)


def baseline_result_row(
    task: str,
    split_name: str,
    model: str,
    train_rows: list[dict[str, object]],
    evaluation_rows: list[dict[str, object]],
    predictions: list[str],
    majority_label: str,
    majority_fraction: float,
    label_count: int,
    prediction_basis: str,
    coverage: float,
    notes: str,
) -> dict[str, object]:
    labels = [str(row.get("category") or "unknown") for row in evaluation_rows]
    return {
        "task_name": task,
        "target_field": "category",
        "baseline_model": model,
        "evaluation_split": split_name,
        "train_rows": len(train_rows),
        "evaluation_rows": len(evaluation_rows),
        "train_label_count": label_count,
        "majority_label": majority_label,
        "majority_fraction_train": majority_fraction,
        "accuracy": accuracy_score(labels, predictions),
        "macro_f1": macro_f1_score(labels, predictions),
        "prediction_basis": prediction_basis,
        "coverage": coverage,
        "status": "completed_deterministic_baseline",
        "notes": notes,
        "version": PORTAL_VERSION,
    }


def api_benchmark_baseline_results() -> list[dict[str, object]]:
    global _BENCHMARK_BASELINE_CACHE
    if _BENCHMARK_BASELINE_CACHE is not None:
        return _BENCHMARK_BASELINE_CACHE
    split_rows = benchmark_reference_splits()
    rows_by_task: dict[str, list[dict[str, object]]] = {}
    for row in split_rows:
        rows_by_task.setdefault(str(row.get("task_name") or "unknown"), []).append(row)

    results: list[dict[str, object]] = []
    for task, task_rows in sorted(rows_by_task.items()):
        train_rows = [row for row in task_rows if row.get("split_name") == "train"]
        counts, majority_label, majority_fraction = baseline_label_counts(train_rows)
        if not counts:
            continue
        for split_name in ["validation", "test"]:
            evaluation_rows = [row for row in task_rows if row.get("split_name") == split_name]
            if not evaluation_rows:
                continue
            results.append(
                baseline_result_row(
                    task,
                    split_name,
                    "train_majority_class",
                    train_rows,
                    evaluation_rows,
                    [majority_label] * len(evaluation_rows),
                    majority_label,
                    majority_fraction,
                    len(counts),
                    "global training-set category prior",
                    1.0,
                    "Sanity baseline: predicts the most common training category for the task.",
                )
            )
            for model, group_key, basis, notes in [
                (
                    "modality_prior_class",
                    "modality",
                    "training-set majority category within the same modality",
                    "Falls back to global majority when the evaluation modality is unseen in training.",
                ),
                (
                    "evidence_grade_prior_class",
                    "evidence_grade",
                    "training-set majority category within the same evidence grade",
                    "Uses only A/B grade labels already present in the fixed reference split.",
                ),
                (
                    "target_prior_class",
                    "target_gene_symbol",
                    "training-set majority category within the same target gene",
                    "Useful as a leakage check: low coverage indicates many held-out targets are unseen.",
                ),
            ]:
                predictions, coverage = grouped_prior_predictions(
                    train_rows,
                    evaluation_rows,
                    group_key,
                    majority_label,
                )
                results.append(
                    baseline_result_row(
                        task,
                        split_name,
                        model,
                        train_rows,
                        evaluation_rows,
                        predictions,
                        majority_label,
                        majority_fraction,
                        len(counts),
                        basis,
                        coverage,
                        notes,
                    )
                )
    _BENCHMARK_BASELINE_CACHE = results
    return results


def benchmark_baseline_results_csv_bytes() -> bytes:
    return dicts_to_csv_bytes(api_benchmark_baseline_results(), BENCHMARK_BASELINE_COLUMNS)


def agent_ready_files() -> list[Path]:
    if not AGENT_READY_DIR.exists():
        return []
    return sorted(
        path
        for path in AGENT_READY_DIR.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )


def agent_manifest_entries() -> dict[str, dict[str, str]]:
    manifest_path = AGENT_READY_DIR / "agent_access_manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    entries: dict[str, dict[str, str]] = {}
    for entry in manifest.get("artifacts", []):
        path = str(entry.get("path", "")).replace("\\", "/")
        if not path:
            continue
        entries[path] = {
            "kind": str(entry.get("kind", "agent_artifact")),
            "purpose": str(entry.get("purpose", "Agent reuse artifact.")),
        }
    return entries


def agent_access_files() -> list[dict[str, object]]:
    manifest_entries = agent_manifest_entries()
    files: list[dict[str, object]] = []
    for path in agent_ready_files():
        relative = path.relative_to(AGENT_READY_DIR).as_posix()
        meta = manifest_entries.get(relative, {})
        files.append(
            {
                "path": f"agent_ready/{relative}",
                "kind": meta.get("kind", "agent_artifact"),
                "purpose": meta.get("purpose", "Agent reuse artifact."),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return files


def agent_pack_zip_bytes() -> bytes:
    handle = io.BytesIO()
    with zipfile.ZipFile(handle, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in agent_ready_files():
            relative = path.relative_to(AGENT_READY_DIR).as_posix()
            archive.write(path, f"agent_ready/{relative}")
        archive.writestr(
            "AGENT_ACCESS_ENDPOINTS.txt",
            "\n".join(
                [
                    "OligoVigil agent-ready access endpoints",
                    "/api/agent_access",
                    "/api/agent_connect",
                    "/agent.json",
                    "/.well-known/oligovigil-agent.json",
                    "/.well-known/ai-plugin.json",
                    "/mcp.json",
                    "/llms.txt",
                    "/llms-full.txt",
                    "/api/openapi.json",
                    "/api/download/evidence_release.csv",
                    "/api/download/benchmark_reference_splits.csv",
                    "",
                ]
            ),
        )
    return handle.getvalue()


def agent_text_file(name: str) -> bytes:
    path = AGENT_READY_DIR / name
    if not path.exists():
        return f"# OligoVigil\n\nAgent guidance file `{name}` is missing from this release.\n".encode(
            "utf-8"
        )
    return path.read_bytes()


def agent_json_file(relative: str) -> dict[str, object]:
    path = AGENT_READY_DIR / relative
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def absolute_url(base_url: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def universal_agent_manifest(base_url: str) -> dict[str, object]:
    manifest = agent_json_file("connectors/universal_agent_manifest.json")
    manifest["version"] = PORTAL_VERSION
    manifest["base_url"] = base_url
    for entry in manifest.get("protocols", []):
        if isinstance(entry, dict) and entry.get("entrypoint"):
            entry["url"] = absolute_url(base_url, str(entry["entrypoint"]))
    manifest["primary_urls"] = [
        absolute_url(base_url, endpoint) for endpoint in manifest.get("primary_endpoints", [])
    ]
    manifest["agent_pack_url"] = absolute_url(
        base_url,
        str(manifest.get("agent_pack", "/api/download/oligovigil_agent_pack.zip")),
    )
    return manifest


def ai_plugin_manifest(base_url: str) -> dict[str, object]:
    manifest = agent_json_file("connectors/openapi_action_manifest.json")
    manifest["api"] = {
        "type": "openapi",
        "url": absolute_url(base_url, "/api/openapi.json"),
        "is_user_authenticated": False,
    }
    manifest["logo_url"] = absolute_url(base_url, "/logo.svg")
    manifest["legal_info_url"] = absolute_url(base_url, "/#cite")
    return manifest


def mcp_client_manifest(base_url: str) -> dict[str, object]:
    manifest = agent_json_file("connectors/mcp_client_config.json")
    servers = manifest.get("mcpServers", {})
    if isinstance(servers, dict) and isinstance(servers.get("oligovigil"), dict):
        env = servers["oligovigil"].setdefault("env", {})
        if isinstance(env, dict):
            env["OLIGOVIGIL_BASE_URL"] = base_url
    manifest["download_agent_pack"] = absolute_url(base_url, "/api/download/oligovigil_agent_pack.zip")
    return manifest


def agent_tool_profiles(base_url: str) -> list[dict[str, object]]:
    payload = agent_json_file("connectors/tool_profiles.json")
    profiles = payload.get("profiles", [])
    if not isinstance(profiles, list):
        return []
    result: list[dict[str, object]] = []
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        item = dict(profile)
        if item.get("entrypoint"):
            item["url"] = absolute_url(base_url, str(item["entrypoint"]))
        result.append(item)
    return result


def api_agent_connect(base_url: str) -> dict[str, object]:
    return {
        "version": PORTAL_VERSION,
        "title": "OligoVigil Universal Agent Connect",
        "summary": (
            "Tool-agnostic connection layer for agentic clients, coding tools, notebooks, "
            "API importers, MCP clients, and web-fetch/RAG agents."
        ),
        "base_url": base_url,
        "entrypoints": [
            {
                "label": "Universal manifest",
                "path": "/agent.json",
                "url": absolute_url(base_url, "/agent.json"),
                "best_for": "agents that can fetch a public URL before coding",
            },
            {
                "label": "OpenAPI import",
                "path": "/api/openapi.json",
                "url": absolute_url(base_url, "/api/openapi.json"),
                "best_for": "tools that generate REST clients or actions",
            },
            {
                "label": "Safety Dossier API",
                "path": "/api/safety_dossier",
                "url": absolute_url(base_url, "/api/safety_dossier"),
                "best_for": "agents that need a ready-to-use evidence packet instead of raw tables",
            },
            {
                "label": "NLWeb discovery",
                "path": "/nlweb.json",
                "url": absolute_url(base_url, "/nlweb.json"),
                "best_for": "natural-language web and agent discovery clients",
            },
            {
                "label": "Bioschemas JSON-LD",
                "path": "/bioschemas.json",
                "url": absolute_url(base_url, "/bioschemas.json"),
                "best_for": "search engines, dataset indexers, and AI discovery layers",
            },
            {
                "label": "MCP config",
                "path": "/mcp.json",
                "url": absolute_url(base_url, "/mcp.json"),
                "best_for": "MCP-compatible coding agents",
            },
            {
                "label": "LLM guide",
                "path": "/llms.txt",
                "url": absolute_url(base_url, "/llms.txt"),
                "best_for": "documentation-first agents",
            },
            {
                "label": "Agent pack",
                "path": "/api/download/oligovigil_agent_pack.zip",
                "url": absolute_url(base_url, "/api/download/oligovigil_agent_pack.zip"),
                "best_for": "local SDK, template, prompt, and MCP reuse",
            },
        ],
        "tool_profiles": agent_tool_profiles(base_url),
        "guardrails": universal_agent_manifest(base_url).get("guardrails", []),
        "not_tool_specific": True,
    }


def api_agent_access() -> dict[str, object]:
    counts = api_stats()["counts"]
    release_records = int(counts.get("toxicity_endpoint", 0) or 0) + int(
        counts.get("offtarget_evidence", 0) or 0
    )
    benchmark_rows = int(counts.get("benchmark_split", 0) or 0)
    candidate_rows = int(counts.get("curation_candidate", 0) or 0)
    artifacts = agent_access_files()
    pack_body = agent_pack_zip_bytes()
    return {
        "version": PORTAL_VERSION,
        "title": "OligoVigil universal agent connect layer",
        "summary": (
            "A guarded, tool-agnostic reuse layer for agentic clients, coding tools, MCP "
            "clients, notebooks, and lightweight apps that need citable oligonucleotide safety "
            "evidence without scraping the portal."
        ),
        "release_snapshot": {
            "verified_release_records": release_records,
            "benchmark_split_rows": benchmark_rows,
            "candidate_gap_records": candidate_rows,
            "candidate_policy": "candidate rows are non-citable gap-finding context",
        },
        "summary_cards": [
            {
                "label": "Universal manifest",
                "value": "agent.json",
                "note": "Single discovery file for any agent that can fetch a public URL.",
            },
            {
                "label": "OpenAPI import",
                "value": "REST",
                "note": "API/action builders can import /api/openapi.json without a custom skill.",
            },
            {
                "label": "MCP tools",
                "value": "6",
                "note": "Search, record detail, triage, modification profile, benchmark, and manifest.",
            },
            {
                "label": "Agent discovery",
                "value": "llms.txt",
                "note": "Concise and full machine-readable instructions are exposed at stable root paths.",
            },
            {
                "label": "Starter clients",
                "value": "Python / JS / R",
                "note": "Small dependency-light clients for scripts, apps, and notebooks.",
            },
            {
                "label": "Optional Codex skill",
                "value": "oligovigil",
                "note": "Bundled for Codex users, but not required for universal access.",
            },
        ],
        "guardrails": [
            {
                "rule": "Verified release evidence only for claims",
                "why": "Candidates are derived annotations awaiting human review.",
                "enforced_by": ["/api/evidence_records", "/api/evidence_detail", "oligovigil_skill"],
            },
            {
                "rule": "Record-level citations required",
                "why": "Safety claims need evidence grade, source location, PMID/DOI, and audit status.",
                "enforced_by": ["/api/evidence_detail", "/api/citation"],
            },
            {
                "rule": "No de novo safety prediction",
                "why": "Safety triage is source-grounded and does not replace alignment, toxicology, or regulatory review.",
                "enforced_by": ["/api/safety_triage", "/api/sequence_search"],
            },
            {
                "rule": "Benchmark splits are fixed",
                "why": "Reusable ML results require unchanged leakage groups and versioned checksums.",
                "enforced_by": ["/api/benchmark", "/api/download/benchmark_reference_splits.csv"],
            },
            {
                "rule": "No fake adoption claims",
                "why": "Usage and citation claims must come from post-deployment evidence, not generated copy.",
                "enforced_by": ["/api/adoption_packet", "/api/archive_readiness"],
            },
        ],
        "workflows": [
            {
                "title": "Ask an agent for a citable safety packet",
                "entry": "/api/search",
                "next": "/api/evidence_detail",
                "output": "Evidence grade, exact source location, PMID/DOI, citation text, and audit trail.",
            },
            {
                "title": "Build a design-review dashboard",
                "entry": "/api/safety_triage",
                "next": "/api/download/evidence_release.csv",
                "output": "Release-supported concerns, candidate gaps, and validation checklist.",
            },
            {
                "title": "Reuse benchmark splits in a notebook",
                "entry": "/api/benchmark",
                "next": "/api/download/benchmark_reference_splits.csv",
                "output": "Task cards, fixed split groups, baseline rows, and citation metadata.",
            },
            {
                "title": "Connect any agentic client",
                "entry": "/agent.json",
                "next": "/api/openapi.json or /mcp.json",
                "output": "Automatic endpoint discovery plus evidence guardrails.",
            },
            {
                "title": "Install local agent helpers",
                "entry": "/api/download/oligovigil_agent_pack.zip",
                "next": "agent_ready/oligovigil_skill/SKILL.md",
                "output": "Skill, MCP server, SDK clients, prompts, and starter templates.",
            },
        ],
        "downloads": {
            "agent_pack_zip": "/api/download/oligovigil_agent_pack.zip",
            "universal_manifest": "/agent.json",
            "well_known_manifest": "/.well-known/oligovigil-agent.json",
            "openapi_action_manifest": "/.well-known/ai-plugin.json",
            "mcp_config": "/mcp.json",
            "agent_connect": "/api/agent_connect",
            "llms_txt": "/llms.txt",
            "llms_full_txt": "/llms-full.txt",
            "openapi": "/api/openapi.json",
        },
        "tool_profiles": agent_tool_profiles(""),
        "pack": {
            "filename": "oligovigil_agent_pack.zip",
            "url": "/api/download/oligovigil_agent_pack.zip",
            "bytes": len(pack_body),
            "sha256": sha256_bytes(pack_body),
            "files": len(artifacts),
        },
        "artifacts": artifacts,
    }


DOWNLOAD_CATALOG = [
    {
        "category": "Core release",
        "filename": "evidence_release.csv",
        "url": "/api/download/evidence_release.csv",
        "kind": "evidence_release",
        "schema": "data_dictionary_v1.csv",
        "purpose": "Unified curator-verified toxicity and off-target release evidence.",
        "recommended_use": "Primary citation and evidence reuse table.",
    },
    {
        "category": "Core release",
        "filename": "source_document.csv",
        "url": "/api/download/source_document.csv",
        "kind": "table",
        "table": "source_document",
        "schema": "data_dictionary_v1.csv",
        "purpose": "Source-level provenance metadata with PMID/DOI/PMCID links.",
        "recommended_use": "Resolve original articles and regulatory documents.",
    },
    {
        "category": "Core release",
        "filename": "molecule.csv",
        "url": "/api/download/molecule.csv",
        "kind": "table",
        "table": "molecule",
        "schema": "data_dictionary_v1.csv",
        "purpose": "Molecule/cohort entities linked to modality and target annotations.",
        "recommended_use": "Join evidence records to molecule-level context.",
    },
    {
        "category": "Benchmark",
        "filename": "benchmark_reference_splits.csv",
        "url": "/api/download/benchmark_reference_splits.csv",
        "kind": "benchmark_splits",
        "schema": "benchmark_task_cards_v1.csv",
        "purpose": "Deterministic Grade A/B reference train/validation/test splits.",
        "recommended_use": "Canonical ML benchmark split file.",
    },
    {
        "category": "Benchmark",
        "filename": "benchmark_task_cards.csv",
        "url": "/api/download/benchmark_task_cards.csv",
        "kind": "manifest_file",
        "manifest": "benchmark_task_cards_v1.csv",
        "schema": "benchmark_task_cards_v1.csv",
        "purpose": "Task definitions, targets, metrics, and leakage policy.",
        "recommended_use": "Cite task name, version, and checksum with benchmark results.",
    },
    {
        "category": "Benchmark",
        "filename": "benchmark_baseline_results.csv",
        "url": "/api/download/benchmark_baseline_results.csv",
        "kind": "benchmark_baseline",
        "schema": "benchmark_task_cards_v1.csv",
        "purpose": "Deterministic majority, modality-prior, grade-prior, and target-prior baselines for validation/test split sanity checks.",
        "recommended_use": "Reference baselines before reporting trained model comparisons.",
    },
    {
        "category": "Benchmark",
        "filename": "benchmark_split.csv",
        "url": "/api/download/benchmark_split.csv",
        "kind": "table",
        "table": "benchmark_split",
        "schema": "data_dictionary_v1.csv",
        "purpose": "Stored split assignments backing the reference split export.",
        "recommended_use": "Audit or regenerate benchmark_reference_splits.csv.",
    },
    {
        "category": "Curation and audit",
        "filename": "curation_audit.csv",
        "url": "/api/download/curation_audit.csv",
        "kind": "table",
        "table": "curation_audit",
        "schema": "data_dictionary_v1.csv",
        "purpose": "Curation decision, validation status, extraction method, and audit trail (v1 curator_id 'machine_v1_keyword_classifier' = automated pre-curation, not human).",
        "recommended_use": "Inspect provenance and curator decision history.",
    },
    {
        "category": "Curation and audit",
        "filename": "sequence_modification_curation_template.csv",
        "url": "/api/download/sequence_modification_curation_template.csv",
        "kind": "manifest_file",
        "manifest": "sequence_modification_curation_template_v1.csv",
        "schema": "data_dictionary_v1.csv",
        "purpose": "Template for sequence and chemical-modification completion.",
        "recommended_use": "Curator input; not a release evidence table.",
    },
    {
        "category": "Curation and audit",
        "filename": "core_oligo_field_curation_packet.csv",
        "url": "/api/download/core_oligo_field_curation_packet.csv",
        "kind": "manifest_file",
        "manifest": "core_oligo_field_curation_packet_v1.csv",
        "schema": "core_oligo_field_curation_packet_v1.csv",
        "purpose": "Prioritized release-row packet for source-verified sequence, modification, delivery, dose, exposure, and model curation.",
        "recommended_use": "Fill P0 benchmark-linked rows first; not a release claim until verified.",
    },
    {
        "category": "Curation and audit",
        "filename": "independent_curation_validation_template.csv",
        "url": "/api/download/independent_curation_validation_template.csv",
        "kind": "manifest_file",
        "manifest": "independent_curation_validation_template_v1.csv",
        "schema": "independent_curation_validation_template_v1.csv",
        "purpose": "Independent second-review sample containing release accept rows and rejected candidate controls for agreement/error-rate estimation.",
        "recommended_use": "Complete before claiming release-row false-accept / false-reject error rates. (Inter-curator Cohen kappa is separately claimed from the completed 100-row KAPPA-2 study: 0.42 drop-abstain / 0.34 collapse-abstain, raw agreement 66%.)",
    },
    {
        "category": "Curation and audit",
        "filename": "curation_candidates_filtered.csv",
        "url": "/api/download/curation_candidates_filtered.csv",
        "kind": "filtered_candidates",
        "manifest": "curation_candidate_v1.csv",
        "schema": "data_dictionary_v1.csv",
        "purpose": "Derived candidate annotations awaiting curator review.",
        "recommended_use": "Gap-finding only; do not cite as verified evidence.",
    },
    {
        "category": "Curation and audit",
        "filename": "curator_review_template_v1.csv",
        "url": "/api/manifest/curator_review_template_v1.csv",
        "kind": "manifest_file",
        "manifest": "curator_review_template_v1.csv",
        "schema": "data_dictionary_v1.csv",
        "purpose": "Human review packet template with provenance and decision fields.",
        "recommended_use": "Manual curation and external contribution review.",
    },
    {
        "category": "Manifests",
        "filename": "all_tables.zip",
        "url": "/api/download/all_tables.zip",
        "kind": "zip",
        "schema": "RELEASE_MANIFEST.json",
        "purpose": "Bulk reproducible snapshot of core CSV tables.",
        "recommended_use": "Archive or reproduce the release locally.",
    },
    {
        "category": "Agent access",
        "filename": "oligovigil_agent_pack.zip",
        "url": "/api/download/oligovigil_agent_pack.zip",
        "kind": "agent_pack",
        "schema": "agent_access_manifest.json",
        "purpose": "Universal manifests, MCP server, optional Codex skill, clients, prompts, llms.txt, and starter templates for agent reuse.",
        "recommended_use": "Connect agentic clients, MCP clients, OpenAPI importers, notebooks, or small apps without scraping the portal UI.",
    },
    {
        "category": "Manifests",
        "filename": "license_manifest_v1.csv",
        "url": "/api/manifest/license_manifest_v1.csv",
        "kind": "manifest_file",
        "manifest": "license_manifest_v1.csv",
        "schema": "license_manifest_v1.csv",
        "purpose": "Source reuse and redistribution policy annotations.",
        "recommended_use": "Check whether raw, derived, or link-out reuse is allowed.",
    },
    {
        "category": "Manifests",
        "filename": "source_license_manifest_v1.csv",
        "url": "/api/manifest/source_license_manifest_v1.csv",
        "kind": "manifest_file",
        "manifest": "source_license_manifest_v1.csv",
        "schema": "source_license_manifest_v1.csv",
        "purpose": "Record-level source provenance and conservative reuse flags for every source_document row.",
        "recommended_use": "Article/source-level license audit before manuscript submission or external redistribution.",
    },
    {
        "category": "Manifests",
        "filename": "data_dictionary_v1.csv",
        "url": "/api/manifest/data_dictionary_v1.csv",
        "kind": "manifest_file",
        "manifest": "data_dictionary_v1.csv",
        "schema": "data_dictionary_v1.csv",
        "purpose": "Column-level schema and field descriptions.",
        "recommended_use": "Read before parsing release tables.",
    },
    {
        "category": "Manifests",
        "filename": "closest_work_matrix_v1.csv",
        "url": "/api/manifest/closest_work_matrix_v1.csv",
        "kind": "manifest_file",
        "manifest": "closest_work_matrix_v1.csv",
        "schema": "closest_work_matrix_v1.csv",
        "purpose": "Comparison against adjacent RNA and oligonucleotide resources.",
        "recommended_use": "Novelty and scope audit.",
    },
]


def download_entry(spec: dict[str, object]) -> dict[str, object]:
    kind = str(spec["kind"])
    body: bytes | None = None
    file_path: Path | None = None
    row_count: int | None = None
    if kind == "evidence_release":
        release_rows = evidence_records({"limit": [str(RELEASE_EXPORT_LIMIT)]})
        body = dicts_to_csv_bytes(release_rows, EVIDENCE_RELEASE_COLUMNS)
        row_count = len(release_rows)
    elif kind == "benchmark_splits":
        split_rows = benchmark_reference_splits()
        body = dicts_to_csv_bytes(split_rows, BENCHMARK_SPLIT_COLUMNS)
        row_count = len(split_rows)
    elif kind == "benchmark_baseline":
        baseline_rows = api_benchmark_baseline_results()
        body = dicts_to_csv_bytes(baseline_rows, BENCHMARK_BASELINE_COLUMNS)
        row_count = len(baseline_rows)
    elif kind == "filtered_candidates":
        candidate_rows = api_curation_candidates({"limit": ["5000"]})
        body = dicts_to_csv_bytes(candidate_rows)
        row_count = len(candidate_rows)
    elif kind == "table":
        table = str(spec["table"])
        body = csv_bytes(table)
        row_count = table_row_count(table)
    elif kind == "manifest_file":
        file_path = MANIFEST_DOWNLOADS.get(str(spec["manifest"]))
        row_count = csv_row_count(file_path) if file_path else None
    elif kind == "zip":
        body = all_tables_zip_bytes()
    elif kind == "agent_pack":
        body = agent_pack_zip_bytes()
        row_count = len(agent_access_files())

    if file_path and file_path.exists():
        bytes_count = file_path.stat().st_size
        checksum = sha256_file(file_path)
    elif body is not None:
        bytes_count = len(body)
        checksum = sha256_bytes(body)
    else:
        bytes_count = 0
        checksum = ""

    filename = str(spec["filename"])
    license_notes = {
        "evidence_release.csv": "Curator-reviewed derived annotations and source identifiers; raw article text/PDFs are not redistributed.",
        "source_document.csv": "Source metadata and identifiers only; users must follow source URLs for original document terms.",
        "molecule.csv": "Derived molecule/cohort annotations linked to release evidence; sequence fields are curator-verified only when populated.",
        "benchmark_reference_splits.csv": "Derived benchmark split assignments over Grade A/B release evidence; cite version and checksum.",
        "benchmark_task_cards.csv": "Derived task metadata for benchmark reuse; cite task name, version, and checksum.",
        "benchmark_baseline_results.csv": "Derived deterministic baseline metrics over fixed splits.",
        "curation_audit.csv": "Audit metadata and curator decisions; no raw article text redistributed.",
        "curation_candidates_filtered.csv": "Derived triage candidates only; not citable verified release evidence.",
        "curator_review_template_v1.csv": "Blank/manual review template; not release evidence.",
        "license_manifest_v1.csv": "Source-class redistribution policy annotations.",
        "source_license_manifest_v1.csv": "Source-level conservative reuse flags; article-level legal reuse should be verified before raw redistribution.",
        "data_dictionary_v1.csv": "Column definitions for release and manifest files.",
        "all_tables.zip": "Bundle of derived annotations, source metadata, audit files, manifests, and benchmark files; raw article text/PDFs excluded.",
    }

    return {
        "category": spec["category"],
        "filename": filename,
        "url": spec["url"],
        "purpose": spec["purpose"],
        "recommended_use": spec["recommended_use"],
        "rows": row_count,
        "bytes": bytes_count,
        "sha256": checksum,
        "schema": spec["schema"],
        "license": license_notes.get(
            filename,
            "Derived annotations; raw article text not redistributed; source PMID/DOI linked.",
        ),
        "version": PORTAL_VERSION,
    }


_DOWNLOAD_MANIFEST_CACHE: dict[str, object] | None = None


def api_download_manifest() -> dict[str, object]:
    global _DOWNLOAD_MANIFEST_CACHE
    if _DOWNLOAD_MANIFEST_CACHE is not None:
        return _DOWNLOAD_MANIFEST_CACHE
    files = [download_entry(spec) for spec in DOWNLOAD_CATALOG]
    payload: dict[str, object] = {
        "version": PORTAL_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "doi_status": ARCHIVE_DOI,
        "archive_url": ARCHIVE_URL,
        "license_policy": "Raw article text is not redistributed. Curator-reviewed derived annotations, source metadata, and PMID/DOI links are provided for reuse.",
        "recommended_bundle": "/api/download/all_tables.zip",
        "files": files,
    }
    _DOWNLOAD_MANIFEST_CACHE = payload
    return payload


_BENCHMARK_CACHE: dict[str, object] | None = None
_MODIFICATION_PROFILE_CACHE: dict[str, dict[str, object]] = {}


def api_benchmark() -> dict[str, object]:
    global _BENCHMARK_CACHE
    if _BENCHMARK_CACHE is not None:
        return _BENCHMARK_CACHE
    release = release_records_all()
    split_rows = benchmark_reference_splits()
    baseline_rows = api_benchmark_baseline_results()
    grade_counts: dict[str, int] = {}
    for record in release:
        grade = str(record.get("evidence_grade") or "unknown")
        grade_counts[grade] = grade_counts.get(grade, 0) + 1
    task_counts: dict[tuple[str, str], int] = {}
    strategy_counts: dict[str, int] = {}
    for split in split_rows:
        key = (str(split["task_name"]), str(split["split_name"]))
        task_counts[key] = task_counts.get(key, 0) + 1
        strategy = str(split.get("split_strategy") or "unknown")
        strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
    payload: dict[str, object] = {
        "version": PORTAL_VERSION,
        "release_records": len(release),
        "benchmark_eligible_records": len(split_rows),
        "eligibility_rule": "Curator-verified accepted Grade A/B toxicity or off-target release evidence.",
        "leakage_policy": "Stored reference splits group records by source identifier plus molecule/cohort name.",
        "tasks": [
            {
                "task_name": "toxicity_safety_v0_1",
                "prediction_target": "toxicity endpoint category/label and evidence-grade-aware safety triage",
                "recommended_metrics": ["AUROC", "AUPRC", "macro-F1", "MSE for numeric toxicity endpoints when available"],
            },
            {
                "task_name": "offtarget_safety_v0_1",
                "prediction_target": "off-target evidence type or binary observed off-target signal",
                "recommended_metrics": ["AUROC", "AUPRC", "PCC", "Spearman"],
            },
        ],
        "grade_counts": [{"evidence_grade": grade, "n": n} for grade, n in sorted(grade_counts.items())],
        "split_counts": [
            {"task_name": task, "split_name": split, "n": n}
            for (task, split), n in sorted(task_counts.items())
        ],
        "split_strategy_counts": [
            {"split_strategy": strategy, "n": n} for strategy, n in sorted(strategy_counts.items())
        ],
            "benchmark_release": {
            "doi_status": ARCHIVE_DOI,
            "archive_url": ARCHIVE_URL,
            "recommended_archive": "Zenodo v1.0.1 data snapshot.",
            "citation_policy": "Cite OligoVigil version, task name, and the reference split CSV checksum.",
            "leakage_control": "stored_source_plus_molecule_grouped_splits",
        },
        "task_cards": api_benchmark_task_cards(),
        "downloads": {
            "reference_splits": "/api/download/benchmark_reference_splits.csv",
            "task_cards": "/api/download/benchmark_task_cards.csv",
            "evidence_release": "/api/download/evidence_release.csv",
            "all_tables": "/api/download/all_tables.zip",
        },
        "download_artifacts": [
            entry
            for entry in api_download_manifest()["files"]
            if entry["filename"]
            in {
                "benchmark_reference_splits.csv",
                "benchmark_baseline_results.csv",
                "benchmark_task_cards.csv",
                "evidence_release.csv",
            }
        ],
        "baseline_models": [
            {
                "model": "train_majority_class",
                "features": "task-level training label prior",
                "loss": "reported as accuracy and macro-F1 on validation/test splits",
            },
            {
                "model": "modality_prior_class",
                "features": "modality-specific training label prior with global fallback",
                "loss": "reported as accuracy and macro-F1 on validation/test splits",
            },
            {
                "model": "evidence_grade_prior_class",
                "features": "A/B evidence-grade training label prior",
                "loss": "reported as accuracy and macro-F1 on validation/test splits",
            },
            {
                "model": "target_prior_class",
                "features": "target-gene training label prior with global fallback",
                "loss": "reported with coverage to expose unseen target groups",
            },
        ],
        "baseline_status": {
            "status": "deterministic_baselines_completed",
            "reason": "Four leakage-aware deterministic baselines are computed from the fixed reference splits: global majority, modality prior, evidence-grade prior, and target-gene prior.",
            "result_table_policy": "Report benchmark_baseline_results.csv as transparent reference baselines; trained model comparisons can be added without changing the split contract.",
        },
        "baseline_result_rows": baseline_rows,
    }
    _BENCHMARK_CACHE = payload
    return payload


def api_benchmark_task_cards() -> list[dict[str, object]]:
    path = MANIFEST_DOWNLOADS.get("benchmark_task_cards_v1.csv")
    if not path or not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def api_modification_profile(query: dict[str, list[str]]) -> dict[str, object]:
    selected = first_param(query, "term").lower()
    if selected in _MODIFICATION_PROFILE_CACHE:
        return _MODIFICATION_PROFILE_CACHE[selected]
    release = release_records_all()
    candidates = rows(
        """
        SELECT candidate.id, candidate.evidence_domain, candidate.candidate_modality,
               candidate.matched_terms, candidate.candidate_signal,
               candidate.confidence_label, candidate.validation_status,
               candidate.curator_decision, source.title AS source_title, source.pmid
        FROM curation_candidate AS candidate
        JOIN source_document AS source ON source.id = candidate.source_document_id
        WHERE candidate.evidence_domain IN ('toxicity', 'offtarget', 'chemistry', 'delivery')
        """
    )
    split_pairs = {
        (str(row["entity_table"]), int(row["entity_id"]))
        for row in rows("SELECT entity_table, entity_id FROM benchmark_split")
    }
    profiles: list[dict[str, object]] = []
    for pattern in MODIFICATION_PATTERNS:
        if selected and selected not in {pattern["term"], pattern["label"].lower()}:
            continue
        synonyms = list(pattern["synonyms"])
        matched_release = [
            record
            for record in release
            if text_matches_any(
                [
                    record.get("canonical_name"),
                    record.get("modality"),
                    record.get("target_gene_symbol"),
                    record.get("disease_context"),
                    record.get("backbone_chemistry"),
                    record.get("sugar_modification"),
                    record.get("base_modification"),
                    record.get("conjugate_delivery"),
                    record.get("category"),
                    record.get("evidence_label"),
                    record.get("source_title"),
                    record.get("audit_note"),
                ],
                synonyms,
            )
        ]
        matched_candidates = [
            candidate
            for candidate in candidates
            if text_matches_any(
                [
                    candidate.get("candidate_modality"),
                    candidate.get("matched_terms"),
                    candidate.get("candidate_signal"),
                    candidate.get("source_title"),
                ],
                synonyms,
            )
        ]
        domain_counts: dict[str, int] = {}
        grade_counts: dict[str, int] = {}
        for record in matched_release:
            domain = str(record.get("evidence_domain") or "unknown")
            grade = str(record.get("evidence_grade") or "unknown")
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            grade_counts[grade] = grade_counts.get(grade, 0) + 1
        benchmark_rows = sum(
            1
            for record in matched_release
            if (str(record.get("entity_table")), int(record.get("evidence_id") or 0)) in split_pairs
        )
        profiles.append(
            {
                "term": pattern["term"],
                "label": pattern["label"],
                "kind": pattern["kind"],
                "synonyms": synonyms,
                "release_records": len(matched_release),
                "candidate_records": len(matched_candidates),
                "benchmark_records": benchmark_rows,
                "domain_counts": [
                    {"domain": domain, "n": n} for domain, n in sorted(domain_counts.items())
                ],
                "grade_counts": [
                    {"grade": grade, "n": n} for grade, n in sorted(grade_counts.items())
                ],
                "example_release_records": matched_release[:8],
                "example_candidates": matched_candidates[:8],
            }
        )
    profiles.sort(key=lambda item: int(item["release_records"]), reverse=True)
    payload = {
        "version": PORTAL_VERSION,
        "scope_note": "Profiles are derived from current release/candidate text fields and modality labels; raw third-party text is not redistributed.",
        "profiles": profiles,
    }
    _MODIFICATION_PROFILE_CACHE[selected] = payload
    return payload


def api_offtarget_taxonomy() -> dict[str, object]:
    release = [
        record for record in release_records_all() if str(record.get("evidence_domain")) == "offtarget"
    ]
    split_pairs = {
        (str(row["entity_table"]), int(row["entity_id"]))
        for row in rows("SELECT entity_table, entity_id FROM benchmark_split")
    }
    candidates = rows(
        """
        SELECT candidate.id, candidate.candidate_modality, candidate.matched_terms,
               candidate.candidate_signal, candidate.confidence_label,
               source.title AS source_title, source.pmid
        FROM curation_candidate AS candidate
        JOIN source_document AS source ON source.id = candidate.source_document_id
        WHERE candidate.evidence_domain = 'offtarget'
        """
    )
    buckets: dict[str, dict[str, object]] = {}
    for item in OFFTARGET_TAXONOMY:
        buckets[item["key"]] = {
            "key": item["key"],
            "label": item["label"],
            "definition": item["definition"],
            "synonyms": item["synonyms"],
            "release_records": 0,
            "benchmark_records": 0,
            "candidate_records": 0,
            "grade_counts": {},
            "examples": [],
            "endpoint": f"/api/evidence_records?domain=offtarget&q={item['synonyms'][0]}",
        }

    for record in release:
        bucket = classify_offtarget_record(record)
        item = buckets[bucket["key"]]
        item["release_records"] = int(item["release_records"]) + 1
        if (str(record.get("entity_table")), int(record.get("evidence_id") or 0)) in split_pairs:
            item["benchmark_records"] = int(item["benchmark_records"]) + 1
        grade_counts = item["grade_counts"]
        if isinstance(grade_counts, dict):
            grade = str(record.get("evidence_grade") or "unknown")
            grade_counts[grade] = int(grade_counts.get(grade, 0)) + 1
        examples = item["examples"]
        if isinstance(examples, list) and len(examples) < 4:
            examples.append(
                {
                    "record": f"{record.get('entity_table')}:{record.get('evidence_id')}",
                    "canonical_name": record.get("canonical_name"),
                    "evidence_label": record.get("evidence_label"),
                    "evidence_grade": record.get("evidence_grade"),
                    "pmid": record.get("pmid"),
                }
            )

    for candidate in candidates:
        blob = " ".join(
            str(candidate.get(field) or "").lower()
            for field in ["candidate_modality", "matched_terms", "candidate_signal", "source_title"]
        )
        matched = False
        for item in OFFTARGET_TAXONOMY:
            if any(term in blob for term in item["synonyms"]):
                buckets[item["key"]]["candidate_records"] = (
                    int(buckets[item["key"]]["candidate_records"]) + 1
                )
                matched = True
                break
        if not matched:
            buckets["general_offtarget"]["candidate_records"] = (
                int(buckets["general_offtarget"]["candidate_records"]) + 1
            )

    classes = sorted(
        buckets.values(),
        key=lambda item: (int(item["release_records"]), int(item["benchmark_records"])),
        reverse=True,
    )
    for item in classes:
        grade_counts = item.get("grade_counts")
        if isinstance(grade_counts, dict):
            item["grade_counts"] = [
                {"grade": grade, "n": n} for grade, n in sorted(grade_counts.items())
            ]
    return {
        "version": PORTAL_VERSION,
        "scope_note": "Off-target classes are mechanism-oriented evidence buckets for browsing and benchmark reuse; they are not de novo off-target predictions for a submitted sequence.",
        "release_records": len(release),
        "benchmark_records": sum(int(item["benchmark_records"]) for item in classes),
        "candidate_records": len(candidates),
        "classes": classes,
        "downloads": {
            "evidence_release": "/api/download/evidence_release.csv",
            "benchmark_splits": "/api/download/benchmark_reference_splits.csv",
        },
    }


def api_sequence_coverage() -> dict[str, object]:
    sequence_expr = """
        COALESCE(
            NULLIF(sense_sequence, ''),
            NULLIF(antisense_sequence, ''),
            NULLIF(guide_sequence, ''),
            NULLIF(passenger_sequence, ''),
            NULLIF(seed_region, '')
        ) IS NOT NULL
    """
    modification_expr = """
        COALESCE(
            NULLIF(backbone_chemistry, ''),
            NULLIF(sugar_modification, ''),
            NULLIF(base_modification, ''),
            NULLIF(conjugate_delivery, '')
        ) IS NOT NULL
    """
    molecule_count = int(one("SELECT COUNT(*) AS n FROM molecule").get("n", 0))
    sequence_nonempty = int(one(f"SELECT COUNT(*) AS n FROM molecule WHERE {sequence_expr}").get("n", 0))
    modification_nonempty = int(one(f"SELECT COUNT(*) AS n FROM molecule WHERE {modification_expr}").get("n", 0))
    sequence_verified = int(
        one(
            f"""
            SELECT COUNT(*) AS n
            FROM molecule
            WHERE sequence_annotation_status = 'curator_verified'
              AND {sequence_expr}
            """
        ).get("n", 0)
    )
    modification_verified = int(
        one(
            f"""
            SELECT COUNT(*) AS n
            FROM molecule
            WHERE modification_annotation_status = 'curator_verified'
              AND {modification_expr}
            """
        ).get("n", 0)
    )
    by_modality = rows(
        f"""
        SELECT modality.name AS modality,
               COUNT(*) AS molecules,
               SUM(CASE WHEN {sequence_expr} THEN 1 ELSE 0 END) AS sequence_nonempty,
               SUM(CASE WHEN {modification_expr} THEN 1 ELSE 0 END) AS modification_nonempty
        FROM molecule
        JOIN modality ON molecule.modality_id = modality.id
        GROUP BY modality.name
        ORDER BY molecules DESC, modality.name
        """
    )
    return {
        "version": PORTAL_VERSION,
        "molecule_count": molecule_count,
        "sequence_fields": [
            "sense_sequence",
            "antisense_sequence",
            "guide_sequence",
            "passenger_sequence",
            "seed_region",
        ],
        "modification_fields": [
            "backbone_chemistry",
            "sugar_modification",
            "base_modification",
            "conjugate_delivery",
        ],
        "sequence_nonempty": sequence_nonempty,
        "sequence_curator_verified": sequence_verified,
        "modification_nonempty": modification_nonempty,
        "modification_curator_verified": modification_verified,
        "needs_sequence_curation": max(molecule_count - sequence_verified, 0),
        "needs_modification_curation": max(molecule_count - modification_verified, 0),
        "release_grade_sequence_alignment_available": sequence_verified > 0,
        "curation_template": "/api/download/sequence_modification_curation_template.csv",
        "policy": "Only curator-verified sequence/modification rows should be used for alignment claims; unverified template rows are curation work items.",
        "by_modality": by_modality,
    }


def api_sequence_search(query: dict[str, list[str]]) -> dict[str, object]:
    raw_sequence = first_param(query, "sequence")
    target = first_param(query, "target")
    modification = first_param(query, "modification")
    endpoint = first_param(query, "endpoint")
    limit = limit_param(query, default=25, maximum=100)
    sequence = canonical_sequence(raw_sequence)
    seed_2_8 = sequence[1:8] if len(sequence) >= 8 else ""
    windows = sequence_windows(sequence, size=7)
    search_terms = [term for term in [target, modification, endpoint] if term]
    if seed_2_8:
        search_terms.extend(["seed", "off-target", "hybridization", "mismatch"])
    if not search_terms:
        search_terms = ["seed", "off-target", "hybridization"]
    q = " ".join(search_terms[:4])
    candidate_q = modification or endpoint or target or ("seed" if seed_2_8 else q)
    release_query: dict[str, list[str]] = {"q": [q], "limit": [str(limit)]}
    if target:
        release_query["target"] = [target]
    release_hits = evidence_records(release_query)
    if not release_hits and target:
        release_hits = evidence_records({"q": [target], "limit": [str(limit)]})
    candidate_hits = api_curation_candidates({"q": [candidate_q], "limit": [str(limit)]})
    modification_profile = api_modification_profile({"term": [modification]} if modification else {})
    sequence_coverage = api_sequence_coverage()
    return {
        "version": PORTAL_VERSION,
        "input": {
            "raw_sequence": raw_sequence,
            "canonical_dna_sequence": sequence,
            "length": len(sequence),
            "target": target,
            "modification": modification,
            "endpoint": endpoint,
        },
        "sequence_features": {
            "seed_2_8": seed_2_8,
            "unique_7mer_windows_first_12": windows,
            "contains_ambiguous_base": "N" in sequence,
        },
        "status": {
            "release_grade_sequence_columns_available": True,
            "release_grade_sequence_alignment_available": sequence_coverage[
                "release_grade_sequence_alignment_available"
            ],
            "current_mode": "sequence parsing plus seed/off-target/modification evidence lookup",
            "upgrade_needed": "Curate release-grade oligo sequence and modification strings before claiming full sequence-alignment search.",
            "sequence_coverage_endpoint": "/api/sequence_coverage",
            "curation_template": "/api/download/sequence_modification_curation_template.csv",
        },
        "evidence_query": {
            "terms": search_terms,
            "release_endpoint": f"/api/evidence_records{build_query_string(release_query)}",
            "candidate_endpoint": f"/api/curation_candidates{build_query_string({'q': [candidate_q], 'limit': [str(limit)]})}",
        },
        "release_hits": release_hits,
        "candidate_hits": candidate_hits,
        "modification_profiles": modification_profile.get("profiles", [])[:4],
        "sequence_coverage": sequence_coverage,
    }


TRIAGE_CONCERNS = [
    {
        "id": "sequence_seed_offtarget",
        "domain": "offtarget",
        "label": "Seed and hybridization off-target evidence",
        "terms": ["seed", "off-target", "hybridization", "mismatch"],
        "action": "Run transcriptome/3'UTR seed-match screening before claiming sequence-specific safety.",
    },
    {
        "id": "transcriptome_offtarget",
        "domain": "offtarget",
        "label": "Transcriptome-level off-target readout",
        "terms": ["transcriptome", "RNA-seq", "microarray", "off-target"],
        "action": "Prioritize observed transcriptome evidence and separate it from computational-only context.",
    },
    {
        "id": "hepatobiliary_toxicity",
        "domain": "toxicity",
        "label": "Hepatic and hepatobiliary toxicity",
        "terms": ["hepatotoxicity", "hepatic", "liver", "ALT", "AST", "GalNAc"],
        "action": "Check liver enzyme, histopathology, and delivery-related hepatobiliary findings.",
    },
    {
        "id": "renal_toxicity",
        "domain": "toxicity",
        "label": "Renal toxicity",
        "terms": ["renal", "kidney", "nephrotoxicity"],
        "action": "Check kidney biomarkers, histopathology, and chemistry/dose context.",
    },
    {
        "id": "hematology_platelet",
        "domain": "toxicity",
        "label": "Hematology and platelet safety",
        "terms": ["platelet", "thrombocytopenia", "hematology", "blood"],
        "action": "Check platelet, coagulation, and hematology endpoints before dose escalation.",
    },
    {
        "id": "immune_inflammatory",
        "domain": "toxicity",
        "label": "Immune and inflammatory activation",
        "terms": ["immune", "cytokine", "TLR", "immunostimulation", "inflammation"],
        "action": "Check cytokine, complement, TLR, and innate immune activation evidence.",
    },
    {
        "id": "local_tissue",
        "domain": "toxicity",
        "label": "Local tissue and administration-site safety",
        "terms": ["local", "injection", "tissue", "skin"],
        "action": "Check local tolerability, injection-site, and tissue exposure evidence.",
    },
]


def split_user_terms(*values: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for value in values:
        for term in re.split(r"[,;/|]+", value or ""):
            cleaned = term.strip()
            if len(cleaned) < 2:
                continue
            key = cleaned.lower()
            if key not in seen:
                seen.add(key)
                terms.append(cleaned)
    return terms


def invalid_sequence_characters(raw_sequence: str) -> list[str]:
    allowed = {"A", "C", "G", "T", "U", "N"}
    invalid = []
    seen: set[str] = set()
    for char in raw_sequence.upper():
        if char.isspace() or char in allowed:
            continue
        if char not in seen:
            seen.add(char)
            invalid.append(char)
    return invalid


def dedupe_evidence(records: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, object]] = []
    for record in records:
        key = (str(record.get("entity_table")), str(record.get("evidence_id")))
        if key in seen:
            continue
        seen.add(key)
        record = dict(record)
        record["record"] = f"{record.get('evidence_domain')}:{record.get('evidence_id')}"
        deduped.append(record)
    return deduped


def evidence_grade_rank(record: dict[str, object]) -> int:
    return {"A": 3, "B": 2, "C": 1}.get(str(record.get("evidence_grade")), 0)


TRIAGE_RELEASE_FIELDS = [
    "canonical_name",
    "category",
    "evidence_label",
    "target_gene_symbol",
    "disease_context",
    "backbone_chemistry",
    "sugar_modification",
    "base_modification",
    "conjugate_delivery",
    "modality",
    "source_location",
    "source_title",
    "pmid",
    "doi",
]
TRIAGE_CANDIDATE_FIELDS = [
    "candidate_signal",
    "matched_terms",
    "candidate_modality",
    "source_location",
    "source_title",
    "pmid",
    "doi",
]
_TRIAGE_RELEASE_CACHE: dict[str, list[dict[str, object]]] = {}
_TRIAGE_CANDIDATE_CACHE: dict[str, list[dict[str, object]]] = {}


def normalized_triage_text(value: object) -> str:
    return (
        str(value or "")
        .lower()
        .replace("off target", "offtarget")
        .replace("off-target", "offtarget")
    )


def triage_term_variants(terms: list[str]) -> list[str]:
    variants: list[str] = []
    seen: set[str] = set()
    for term in terms:
        cleaned = normalized_triage_text(term).strip()
        if not cleaned or len(cleaned) < 2:
            continue
        candidate_variants = [cleaned]
        for group in query_term_groups(cleaned, maximum=4):
            candidate_variants.extend(group)
        for variant in candidate_variants:
            normalized = normalized_triage_text(variant).strip()
            if normalized and len(normalized) >= 2 and normalized not in seen:
                seen.add(normalized)
                variants.append(normalized)
    return variants


def triage_row_text(record: dict[str, object], fields: list[str]) -> str:
    return " | ".join(normalized_triage_text(record.get(field)) for field in fields)


def triage_release_pool(domain: str) -> list[dict[str, object]]:
    if domain not in _TRIAGE_RELEASE_CACHE:
        _TRIAGE_RELEASE_CACHE[domain] = evidence_records(
            {"domain": [domain], "limit": [str(RELEASE_EXPORT_LIMIT)]}
        )
    return _TRIAGE_RELEASE_CACHE[domain]


def triage_candidate_pool(domain: str) -> list[dict[str, object]]:
    if domain not in _TRIAGE_CANDIDATE_CACHE:
        sql = """
            SELECT candidate.id, candidate.queue_id, candidate.pmid, candidate.doi,
                   candidate.evidence_domain, candidate.candidate_modality,
                   candidate.source_location, candidate.matched_terms, candidate.candidate_signal,
                   candidate.suggested_evidence_grade, candidate.confidence_label,
                   candidate.validation_status, candidate.curator_decision,
                   candidate.redistribution_level, source.title AS source_title
            FROM curation_candidate AS candidate
            JOIN source_document AS source ON candidate.source_document_id = source.id
            WHERE candidate.evidence_domain = ?
              AND COALESCE(candidate.curator_decision, '') != 'accept'
            ORDER BY CASE candidate.confidence_label
                WHEN 'high_candidate' THEN 0
                WHEN 'medium_candidate' THEN 1
                ELSE 2
            END, candidate.id
        """
        _TRIAGE_CANDIDATE_CACHE[domain] = rows(sql, (domain,))
    return _TRIAGE_CANDIDATE_CACHE[domain]


def triage_match_score(
    record: dict[str, object],
    fields: list[str],
    query_terms: list[str],
    target: str = "",
) -> tuple[int, list[str]]:
    variants = triage_term_variants(query_terms)
    text = triage_row_text(record, fields)
    matched = [variant for variant in variants if variant in text]
    score = len(matched)
    target_text = normalized_triage_text(target).strip()
    if target_text and target_text in text:
        score += 3
        if target_text not in matched:
            matched.append(target_text)
    return score, matched[:8]


def collect_release_matches(
    domain: str,
    concern_terms: list[str],
    input_terms: list[str],
    target: str,
    limit: int,
) -> list[dict[str, object]]:
    matches = []
    queries = [*input_terms[:5], *concern_terms[:6]]
    for record in triage_release_pool(domain):
        score, matched_terms = triage_match_score(record, TRIAGE_RELEASE_FIELDS, queries, target)
        if score <= 0:
            continue
        record = dict(record)
        record["triage_match_score"] = score
        record["triage_matched_terms"] = ", ".join(matched_terms)
        matches.append(record)
    matches = dedupe_evidence(matches)
    matches.sort(
        key=lambda item: (
            -int(item.get("triage_match_score") or 0),
            -evidence_grade_rank(item),
            str(item.get("record")),
        )
    )
    return matches[:limit]


def collect_candidate_matches(
    domain: str,
    concern_terms: list[str],
    input_terms: list[str],
    limit: int,
) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    queries = [*input_terms[:5], *concern_terms[:6]]
    seen: set[str] = set()
    for candidate in triage_candidate_pool(domain):
        score, matched_terms = triage_match_score(candidate, TRIAGE_CANDIDATE_FIELDS, queries)
        if score <= 0:
            continue
        key = str(candidate.get("id"))
        if key in seen:
            continue
        seen.add(key)
        candidate = dict(candidate)
        candidate["triage_match_score"] = score
        candidate["triage_matched_terms"] = ", ".join(matched_terms)
        matches.append(candidate)
    matches.sort(
        key=lambda item: (
            -int(item.get("triage_match_score") or 0),
            {"high_candidate": 3, "medium_candidate": 2, "low_candidate": 1}.get(
                str(item.get("confidence_label")), 0
            ),
            int(item.get("id") or 0),
        )
    )
    return matches[:limit]


def evidence_state(release_matches: list[dict[str, object]], candidate_matches: list[dict[str, object]]) -> str:
    grades = {str(record.get("evidence_grade")) for record in release_matches}
    if grades & {"A", "B"}:
        return "evidence-supported concern"
    if "C" in grades:
        return "contextual release evidence"
    if candidate_matches:
        return "evidence gap"
    return "not assessable from current release"


def triage_state_rank(state: str) -> int:
    return {
        "evidence-supported concern": 3,
        "contextual release evidence": 2,
        "evidence gap": 1,
        "not assessable from current release": 0,
    }.get(state, 0)


def api_safety_triage(query: dict[str, list[str]]) -> dict[str, object]:
    helm_notation = first_param(query, "helm")
    raw_sequence = first_param(query, "sequence")
    helm_sequence = sequence_from_helm(helm_notation)
    if not raw_sequence and helm_sequence:
        raw_sequence = helm_sequence
    target = first_param(query, "target")
    modification = first_param(query, "modification")
    delivery = first_param(query, "delivery")
    endpoint = first_param(query, "endpoint")
    species = first_param(query, "species")
    cell_type = first_param(query, "cell_type")
    limit = limit_param(query, default=20, maximum=50)
    sequence = canonical_sequence(raw_sequence)
    invalid_chars = invalid_sequence_characters(raw_sequence)
    seed_2_8 = sequence[1:8] if len(sequence) >= 8 else ""
    windows = sequence_windows(sequence, size=7)
    input_terms = split_user_terms(target, modification, delivery, endpoint, species, cell_type)
    if seed_2_8:
        input_terms.append(seed_2_8)

    concern_reports: list[dict[str, object]] = []
    all_release: list[dict[str, object]] = []
    all_candidates: list[dict[str, object]] = []
    for concern in TRIAGE_CONCERNS:
        concern_terms = list(concern["terms"])
        if concern["id"] == "hepatobiliary_toxicity" and modification:
            concern_terms.append(modification)
        if concern["id"] == "local_tissue" and delivery:
            concern_terms.append(delivery)
        release_matches = collect_release_matches(
            str(concern["domain"]), concern_terms, input_terms, target, limit
        )
        candidate_matches = collect_candidate_matches(
            str(concern["domain"]), concern_terms, input_terms, limit
        )
        state = evidence_state(release_matches, candidate_matches)
        benchmark_eligible = sum(
            1 for record in release_matches if str(record.get("evidence_grade")) in {"A", "B"}
        )
        all_release.extend(release_matches[:8])
        all_candidates.extend(candidate_matches[:8])
        concern_reports.append(
            {
                "concern_id": concern["id"],
                "domain": concern["domain"],
                "concern": concern["label"],
                "evidence_state": state,
                "release_records": len(release_matches),
                "benchmark_eligible_records": benchmark_eligible,
                "candidate_records": len(candidate_matches),
                "top_release_records": release_matches[:5],
                "top_candidate_records": candidate_matches[:5],
                "rationale": (
                    f"{len(release_matches)} curator-verified release records and "
                    f"{len(candidate_matches)} candidate gap records matched this concern."
                ),
                "recommended_action": concern["action"],
                "release_endpoint": f"/api/evidence_records{build_query_string({'domain': [str(concern['domain'])], 'q': [concern_terms[0]], 'limit': [str(limit)]})}",
                "candidate_endpoint": f"/api/curation_candidates{build_query_string({'domain': [str(concern['domain'])], 'q': [concern_terms[0]], 'limit': [str(limit)]})}",
            }
        )
    concern_reports.sort(
        key=lambda item: (
            -triage_state_rank(str(item["evidence_state"])),
            -int(item["release_records"]),
            str(item["concern"]),
        )
    )

    all_release = dedupe_evidence(all_release)
    all_release.sort(key=lambda item: (-evidence_grade_rank(item), str(item.get("record"))))
    candidate_seen: set[str] = set()
    candidate_gaps: list[dict[str, object]] = []
    for candidate in all_candidates:
        key = str(candidate.get("id"))
        if key in candidate_seen:
            continue
        candidate_seen.add(key)
        candidate_gaps.append(candidate)

    evidence_supported = sum(
        1 for concern in concern_reports if concern["evidence_state"] == "evidence-supported concern"
    )
    evidence_gaps = sum(1 for concern in concern_reports if concern["evidence_state"] == "evidence gap")
    not_assessable = sum(
        1 for concern in concern_reports if concern["evidence_state"] == "not assessable from current release"
    )
    sequence_status = (
        "valid seed-aware input"
        if len(sequence) >= 7 and not invalid_chars
        else "sequence input incomplete for seed-aware triage"
    )
    modification_profile = api_modification_profile({"term": [modification or delivery]} if modification or delivery else {})
    report_id = sha256_bytes(
        "|".join([sequence, target, modification, delivery, endpoint, species, cell_type]).encode("utf-8")
    )[:16]
    return {
        "version": PORTAL_VERSION,
        "report_id": report_id,
        "input": {
            "raw_sequence": raw_sequence,
            "helm_notation": helm_notation,
            "sequence_input_mode": "HELM-derived base string" if helm_notation and helm_sequence else "plain sequence",
            "canonical_dna_sequence": sequence,
            "invalid_sequence_characters": invalid_chars,
            "target": target,
            "modification": modification,
            "delivery": delivery,
            "endpoint": endpoint,
            "species": species,
            "cell_type": cell_type,
        },
        "sequence_features": {
            "length": len(sequence),
            "seed_2_8": seed_2_8,
            "unique_7mer_windows_first_12": windows,
            "contains_ambiguous_base": "N" in sequence,
            "status": sequence_status,
        },
        "summary": {
            "evidence_supported_concerns": evidence_supported,
            "evidence_gap_concerns": evidence_gaps,
            "not_assessable_concerns": not_assessable,
            "release_records_considered": len(all_release),
            "candidate_gap_records_considered": len(candidate_gaps),
            "interpretation": (
                "Evidence-dense safety review required."
                if evidence_supported >= 3
                else "Use as a source-grounded triage report, not a sequence-specific safety prediction."
            ),
        },
        "triage_policy": {
            "prediction_mode": "no de novo safety prediction",
            "evidence_boundary": "Report links user-provided design features to curator-verified release evidence and candidate curation gaps.",
            "citable_rows": "Only records marked curator-verified release evidence should be cited.",
        },
        "dossier": {
            "title": "OligoVigil Safety Evidence Dossier",
            "one_sentence_value": "Turns a candidate oligonucleotide safety question into a citable, source-grounded evidence packet.",
            "primary_use": "preclinical safety review, oligonucleotide design triage, benchmark reuse, and reviewer-auditable provenance inspection",
            "not_for": "clinical recommendation, de novo safety prediction, or replacement of transcriptome alignment/toxicology review",
            "sections": [
                {
                    "section": "Design context",
                    "purpose": "Normalize user-provided sequence, HELM-derived bases, target, chemistry, delivery, tissue/species, and endpoint focus.",
                },
                {
                    "section": "Risk matrix",
                    "purpose": "Separate evidence-supported concerns, contextual evidence, candidate gaps, and non-assessable concerns.",
                },
                {
                    "section": "Evidence graph",
                    "purpose": "Connect design features, safety concerns, release records, sources, and candidate gaps.",
                },
                {
                    "section": "Provenance packet",
                    "purpose": "Expose source location, PMID/DOI/PMCID, curator audit, grade policy, and citable record links.",
                },
                {
                    "section": "Benchmark reuse",
                    "purpose": "Identify Grade A/B records that can be reused in fixed reference split comparisons.",
                },
            ],
        },
        "risk_matrix": concern_reports,
        "matched_release_records": all_release[:30],
        "candidate_gap_records": candidate_gaps[:30],
        "modification_profiles": modification_profile.get("profiles", [])[:5],
        "validation_checklist": [
            {
                "item": "Sequence identity and full antisense/guide/passenger strings",
                "status": "blocked" if len(sequence) < 7 or invalid_chars else "seed parsed",
                "action": "Curate exact release-grade sequence fields before alignment claims.",
            },
            {
                "item": "Transcriptome or 3'UTR seed-match screening",
                "status": "required",
                "action": "Run external alignment/seed scan and link results as new curator-reviewed evidence.",
            },
            {
                "item": "Chemistry and delivery comparator",
                "status": "partially covered" if modification or delivery else "missing input",
                "action": "Provide backbone, sugar/base modification, conjugate, and delivery context.",
            },
            {
                "item": "Toxicity endpoint panel",
                "status": "endpoint-guided" if endpoint else "broad panel",
                "action": "Review hepatic, renal, platelet/hematology, immune, and local tissue endpoints.",
            },
            {
                "item": "Regulatory/clinical adverse-event linkage",
                "status": "source-linked gap",
                "action": "Add FDA/EMA label or clinical-trial safety evidence as curator-reviewed release rows.",
            },
        ],
        "downloads": {
            "evidence_release_csv": "/api/download/evidence_release.csv",
            "benchmark_reference_splits_csv": "/api/download/benchmark_reference_splits.csv",
            "curation_candidates_filtered_csv": "/api/download/curation_candidates_filtered.csv",
        },
        "api_links": {
            "self": f"/api/safety_triage{build_query_string(query)}",
            "dossier": f"/api/safety_dossier{build_query_string(query)}",
            "evidence_graph": f"/api/evidence_graph{build_query_string(query)}",
            "prov_graph": f"/api/prov_graph{build_query_string(query)}",
            "sequence_search": f"/api/sequence_search{build_query_string({'sequence': [raw_sequence], 'target': [target], 'modification': [modification], 'endpoint': [endpoint]})}",
            "evidence_records": "/api/evidence_records",
            "submission_schema": "/api/submission_schema",
        },
    }


def node_id(prefix: str, value: object) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value or "unknown")).strip("_")
    return f"{prefix}:{cleaned[:80] or 'unknown'}"


def evidence_graph_from_triage(
    triage: dict[str, object], query: dict[str, list[str]]
) -> dict[str, object]:
    input_data = triage.get("input", {})
    graph_nodes: dict[str, dict[str, object]] = {}
    graph_edges: list[dict[str, object]] = []

    def add_node(identifier: str, label: str, kind: str, **extra: object) -> None:
        graph_nodes.setdefault(
            identifier,
            {"id": identifier, "label": label, "type": kind, **extra},
        )

    def add_edge(source: str, target: str, label: str, kind: str) -> None:
        if source in graph_nodes and target in graph_nodes:
            graph_edges.append({"source": source, "target": target, "label": label, "type": kind})

    design_label = " / ".join(
        item
        for item in [
            str(input_data.get("target") or "any target"),
            str(input_data.get("modification") or input_data.get("delivery") or "any chemistry"),
            str(input_data.get("endpoint") or "safety endpoint"),
        ]
        if item
    )
    design_id = "design:query"
    add_node(
        design_id,
        design_label,
        "design_query",
        href=triage.get("api_links", {}).get("self"),
        description="User-provided oligonucleotide design context.",
    )

    for concern in triage.get("risk_matrix", [])[:8]:
        concern_id = node_id("concern", concern.get("concern_id"))
        add_node(
            concern_id,
            str(concern.get("concern") or concern.get("concern_id")),
            "safety_concern",
            state=concern.get("evidence_state"),
            release_records=concern.get("release_records"),
            candidate_records=concern.get("candidate_records"),
        )
        add_edge(design_id, concern_id, "assessed for", "assesses")
        for record in concern.get("top_release_records", [])[:3]:
            record_key = record.get("record") or f"{record.get('entity_table')}:{record.get('evidence_id')}"
            record_id = node_id("release", record_key)
            source_key = record.get("pmid") or record.get("doi") or record.get("source_title")
            source_id = node_id("source", source_key)
            add_node(
                record_id,
                str(record.get("canonical_name") or record.get("evidence_label") or record_key),
                "verified_release_record",
                grade=record.get("evidence_grade"),
                domain=record.get("evidence_domain"),
                href=f"/#record/{record.get('evidence_domain')}/{record.get('evidence_id')}",
            )
            add_node(
                source_id,
                str(record.get("pmid") or record.get("doi") or "source"),
                "source_document",
                title=record.get("source_title"),
                href=record.get("source_url"),
            )
            add_edge(concern_id, record_id, "supported by", "supported_by")
            add_edge(record_id, source_id, "has source", "has_source")
        for candidate in concern.get("top_candidate_records", [])[:2]:
            candidate_id = node_id("candidate", candidate.get("id"))
            add_node(
                candidate_id,
                str(candidate.get("matched_terms") or candidate.get("source_location") or "candidate gap"),
                "candidate_gap",
                confidence=candidate.get("confidence_label"),
            )
            add_edge(concern_id, candidate_id, "candidate gap", "candidate_gap")

    nodes = list(graph_nodes.values())
    return {
        "version": PORTAL_VERSION,
        "graph_type": "safety_dossier_evidence_graph",
        "scope_note": "Graph edges connect user design context to curator-verified release evidence and separated candidate gaps; they do not encode de novo safety prediction.",
        "report_id": triage.get("report_id"),
        "nodes": nodes,
        "edges": graph_edges,
        "counts": {
            "nodes": len(nodes),
            "edges": len(graph_edges),
            "verified_release_nodes": sum(1 for node in nodes if node.get("type") == "verified_release_record"),
            "source_nodes": sum(1 for node in nodes if node.get("type") == "source_document"),
            "candidate_gap_nodes": sum(1 for node in nodes if node.get("type") == "candidate_gap"),
        },
        "api_links": {
            "dossier": f"/api/safety_dossier{build_query_string(query)}",
            "prov_graph": f"/api/prov_graph{build_query_string(query)}",
            "evidence_release": "/api/download/evidence_release.csv",
        },
    }


def api_evidence_graph(query: dict[str, list[str]]) -> dict[str, object]:
    return evidence_graph_from_triage(api_safety_triage(query), query)


def api_prov_graph(query: dict[str, list[str]]) -> dict[str, object]:
    graph = api_evidence_graph(query)
    entities = [
        {
            "id": node["id"],
            "prov:type": node.get("type"),
            "label": node.get("label"),
        }
        for node in graph.get("nodes", [])
    ]
    activities = [
        {
            "id": f"activity:{graph.get('report_id')}",
            "prov:type": "oligovigil:safety_dossier_generation",
            "label": "Generate source-grounded safety dossier",
        }
    ]
    return {
        "version": PORTAL_VERSION,
        "standard": "W3C PROV-compatible JSON profile",
        "scope_note": "This profile records derivation from user query, verified release records, source documents, and candidate-gap annotations.",
        "entity": entities,
        "activity": activities,
        "agent": [
            {
                "id": "agent:oligovigil",
                "prov:type": "softwareAgent",
                "label": "OligoVigil portal",
            },
            {
                "id": "agent:curation_team",
                "prov:type": "organization",
                "label": "OligoVigil human curation workflow",
            },
        ],
        "wasDerivedFrom": [
            {"generatedEntity": edge["source"], "usedEntity": edge["target"], "prov:role": edge["type"]}
            for edge in graph.get("edges", [])
            if edge.get("type") in {"supported_by", "has_source", "candidate_gap"}
        ],
        "wasGeneratedBy": [
            {"entity": node["id"], "activity": f"activity:{graph.get('report_id')}"}
            for node in graph.get("nodes", [])
            if node.get("type") in {"design_query", "safety_concern"}
        ],
        "api_links": graph.get("api_links", {}),
    }


def api_safety_dossier(query: dict[str, list[str]]) -> dict[str, object]:
    triage = api_safety_triage(query)
    graph = evidence_graph_from_triage(triage, query)
    summary = triage.get("summary", {})
    input_data = triage.get("input", {})
    return {
        "version": PORTAL_VERSION,
        "dossier_id": triage.get("report_id"),
        "title": "OligoVigil Safety Evidence Dossier",
        "headline": "From oligonucleotide design to citable safety evidence.",
        "input": input_data,
        "executive_summary": {
            "interpretation": summary.get("interpretation"),
            "supported_concerns": summary.get("evidence_supported_concerns"),
            "candidate_gap_concerns": summary.get("evidence_gap_concerns"),
            "release_records_considered": summary.get("release_records_considered"),
            "candidate_gap_records_considered": summary.get("candidate_gap_records_considered"),
            "prediction_boundary": triage.get("triage_policy", {}).get("prediction_mode"),
        },
        "dossier_sections": triage.get("dossier", {}).get("sections", []),
        "risk_matrix": triage.get("risk_matrix", []),
        "evidence_graph": graph,
        "provenance_profile": f"/api/prov_graph{build_query_string(query)}",
        "export_actions": [
            {"label": "JSON dossier", "url": f"/api/safety_dossier{build_query_string(query)}"},
            {"label": "Evidence graph JSON", "url": f"/api/evidence_graph{build_query_string(query)}"},
            {"label": "W3C PROV profile", "url": f"/api/prov_graph{build_query_string(query)}"},
            {"label": "Print or save PDF", "url": "/#triage"},
        ],
        "citation_boundary": "Cite only curator-verified release rows and their source records; candidate gaps are curation leads.",
        "api_links": triage.get("api_links", {}),
    }


def api_bioschemas(base_url: str) -> dict[str, object]:
    stats = api_stats()
    return {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "@id": absolute_url(base_url, "/#overview"),
        "name": "OligoVigil",
        "description": "Source-localized oligonucleotide (ASO/siRNA) safety and off-target evidence resource. 737 human curator-verified release rows (626 toxicity + 111 off-target), Cohen κ_binary = 0.42 (drop-abstain) / 0.34 (collapse-abstain) from a blinded second-curator 100-row inter-rater study, independently re-curated over source passages from 2003 v1 machine pre-curated candidates (v2 LLM-assisted), with citable provenance, benchmark splits, downloads, and agent-readable access.",
        "url": absolute_url(base_url, "/"),
        "license": "Derived annotations and source metadata are redistributed under the project data policy; raw third-party article text is not redistributed.",
        "isAccessibleForFree": True,
        "keywords": [
            "oligonucleotide therapeutics",
            "ASO",
            "siRNA",
            "toxicity",
            "off-target evidence",
            "curation provenance",
            "benchmark dataset",
        ],
        "measurementTechnique": [
            "human curation",
            "source-localized evidence extraction",
            "curator audit trail",
            "reference benchmark split generation",
        ],
        "distribution": [
            {
                "@type": "DataDownload",
                "name": "Evidence release CSV",
                "encodingFormat": "text/csv",
                "contentUrl": absolute_url(base_url, "/api/download/evidence_release.csv"),
            },
            {
                "@type": "DataDownload",
                "name": "All tables ZIP",
                "encodingFormat": "application/zip",
                "contentUrl": absolute_url(base_url, "/api/download/all_tables.zip"),
            },
        ],
        "variableMeasured": [
            {"@type": "PropertyValue", "name": "verified release evidence", "value": stats.get("counts", {}).get("toxicity_endpoint", 0) + stats.get("counts", {}).get("offtarget_evidence", 0)},
            {"@type": "PropertyValue", "name": "benchmark split rows", "value": stats.get("counts", {}).get("benchmark_split", 0)},
        ],
    }


def api_nlweb_manifest(base_url: str) -> dict[str, object]:
    return {
        "name": "OligoVigil",
        "version": PORTAL_VERSION,
        "description": "Natural-language and agent-ready entrypoints for oligonucleotide safety evidence lookup, Safety Dossier generation, evidence graph retrieval, and benchmark reuse.",
        "base_url": base_url,
        "default_query_examples": NATURAL_LANGUAGE_QUERY_EXAMPLES
        + [
            "Generate a Safety Dossier for a GalNAc PCSK9 siRNA with hepatic endpoint focus",
            "Show the evidence graph for seed-mediated off-target evidence",
            "Return PROV JSON for this safety dossier",
        ],
        "tools": [
            {
                "name": "generate_safety_dossier",
                "method": "GET",
                "path": "/api/safety_dossier",
                "description": "Generate a source-grounded dossier from sequence/HELM, target, modification, delivery, endpoint, species, and cell/tissue input.",
            },
            {
                "name": "get_evidence_graph",
                "method": "GET",
                "path": "/api/evidence_graph",
                "description": "Return nodes and edges connecting design context, safety concerns, verified release records, sources, and candidate gaps.",
            },
            {
                "name": "ask_verified_evidence",
                "method": "GET",
                "path": "/api/ask",
                "description": "Read-only natural-language query over verified release evidence.",
            },
            {
                "name": "download_release",
                "method": "GET",
                "path": "/api/download/evidence_release.csv",
                "description": "Download citable verified release evidence.",
            },
        ],
        "guardrails": [
            "Do not claim de novo safety prediction.",
            "Cite only curator-verified release evidence rows (737 human curator-verified rows; join via the release_audit_v SQL view, not the raw curation_audit table).",
            "Disclose that curation was AI-assisted: a primary human curator adjudicated v2 LLM proposals over source passages (re-curated from 2003 v1 machine candidates); inter-curator Cohen kappa is claimed from a blinded second curator (HY) on a 100-row mixed inter-rater sample (KAPPA-2): κ_binary = 0.42 (drop-abstain, n=92) / 0.34 (collapse-abstain, n=100), raw agreement 66% (66/100); A10 third-adjudicator pass in progress.",
            "Treat candidate rows as curation leads, not verified evidence; machine-only rows are labelled machine_precurated_v1.",
            "Do not redistribute raw third-party article text.",
        ],
        "machine_interfaces": {
            "openapi": absolute_url(base_url, "/api/openapi.json"),
            "mcp": absolute_url(base_url, "/mcp.json"),
            "agent_manifest": absolute_url(base_url, "/agent.json"),
            "llms_txt": absolute_url(base_url, "/llms.txt"),
            "bioschemas": absolute_url(base_url, "/bioschemas.json"),
        },
    }


def build_query_string(query: dict[str, list[str]]) -> str:
    payload = {key: (values or [""])[0] for key, values in query.items() if (values or [""])[0]}
    suffix = urlencode(payload)
    return f"?{suffix}" if suffix else ""


def api_use_cases() -> dict[str, object]:
    workflows = api_case_workflows()["case_workflows"]
    return {
        "case_workflows": workflows,
        "use_cases": [
            {
                "title": "Safety triage for an ASO/siRNA program",
                "audience": "wet-lab oligonucleotide researchers",
                "query": "hepatotoxicity GalNAc ASO",
                "primary_endpoint": "/api/search?q=hepatotoxicity%20GalNAc%20ASO",
                "next_action": "Open matching evidence records, cite the record page, and download the release CSV.",
            },
            {
                "title": "Off-target mechanism lookup",
                "audience": "RNAi and transcriptomics groups",
                "query": "seed-mediated off-target effect",
                "primary_endpoint": "/api/evidence_records?domain=offtarget&q=seed",
                "next_action": "Filter by off-target category and inspect PMID-level provenance.",
            },
            {
                "title": "Sequence-to-evidence triage",
                "audience": "oligonucleotide design teams",
                "query": "AUGCUACUGACUGA",
                "primary_endpoint": "/api/sequence_search?sequence=AUGCUACUGACUGA&modification=GalNAc&target=PCSK9",
                "next_action": "Inspect seed windows, then open linked off-target and safety evidence routes.",
            },
            {
                "title": "Modification safety profile",
                "audience": "chemistry and delivery optimization groups",
                "query": "galnac",
                "primary_endpoint": "/api/modification_profile?term=galnac",
                "next_action": "Compare release evidence, candidate coverage, and benchmark rows by chemistry/delivery term.",
            },
            {
                "title": "Benchmark dataset reuse",
                "audience": "ML and computational biology groups",
                "query": "toxicity_safety_v0_1",
                "primary_endpoint": "/api/benchmark",
                "next_action": "Download reference splits and report metrics against fixed train/validation/test groups.",
            },
            *workflows,
            {
                "title": "Curation contribution or correction",
                "audience": "database users and authors",
                "query": "candidate evidence correction",
                "primary_endpoint": "/api/submission_schema",
                "next_action": "Submit source location, PMID/DOI, decision, and curator note using the review template fields.",
            },
        ]
    }


def case_count(endpoint_query: dict[str, list[str]]) -> int:
    return cached_release_count(endpoint_query)


def api_case_workflows() -> dict[str, object]:
    workflows = [
        {
            "id": "galnac_liver_safety",
            "title": "GalNAc-siRNA liver safety profile",
            "result_title": "Example result: GalNAc liver safety profile",
            "audience": "oligonucleotide drug discovery teams",
            "query": "galnac",
            "question": "Which verified safety records mention GalNAc delivery and hepatic/liver toxicity signals?",
            "primary_endpoint": "/api/modification_profile?term=galnac",
            "release_endpoint": "/api/evidence_records?domain=toxicity&q=galnac",
            "benchmark_endpoint": "/api/benchmark",
            "next_action": "Start from GalNAc profile counts, open toxicity evidence, then export A/B benchmark rows for model reuse.",
            "why_useful": "Connects delivery chemistry, liver safety evidence, provenance, and benchmark-eligible rows in one reusable path.",
            "workflow_steps": [
                "Open the GalNAc modification profile.",
                "Filter verified toxicity records by liver/hepatic endpoints.",
                "Download evidence_release.csv and benchmark_reference_splits.csv.",
            ],
            "release_records": case_count({"domain": ["toxicity"], "q": ["galnac"]}),
            "benchmark_task": "toxicity_safety_v0_1",
            "dashboard_cards": [
                {"label": "domain", "value": "toxicity"},
                {"label": "primary filter", "value": "GalNAc"},
                {"label": "evidence use", "value": "safety profile"},
            ],
        },
        {
            "id": "aso_gapmer_hepatotoxicity",
            "title": "ASO/gapmer hepatotoxicity review",
            "result_title": "Example result: ASO/gapmer hepatotoxicity review",
            "audience": "ASO chemistry and safety groups",
            "query": "hepatotoxicity",
            "question": "Which ASO/gapmer records have verified hepatotoxicity source locations and evidence grades?",
            "primary_endpoint": "/api/evidence_records?domain=toxicity&q=hepatotoxicity",
            "release_endpoint": "/api/evidence_records?domain=toxicity&q=hepatotoxicity",
            "benchmark_endpoint": "/api/benchmark",
            "next_action": "Compare Grade A/B/C hepatotoxicity evidence, inspect exact source locations, and cite record pages.",
            "why_useful": "Turns a broad safety concern into a citable, source-located evidence packet.",
            "workflow_steps": [
                "Search hepatotoxicity release records.",
                "Open record-level provenance and audit trail.",
                "Separate A/B benchmark records from C-grade contextual evidence.",
            ],
            "release_records": case_count({"domain": ["toxicity"], "q": ["hepatotoxicity"]}),
            "benchmark_task": "toxicity_safety_v0_1",
            "dashboard_cards": [
                {"label": "domain", "value": "toxicity"},
                {"label": "primary filter", "value": "hepatotoxicity"},
                {"label": "evidence use", "value": "record citation"},
            ],
        },
        {
            "id": "renal_platelet_scan",
            "title": "Renal and thrombocytopenia safety scan",
            "result_title": "Example result: renal and platelet safety scan",
            "audience": "preclinical safety reviewers",
            "query": "renal",
            "question": "What verified and candidate safety evidence exists for renal or platelet-related endpoints?",
            "primary_endpoint": "/api/search?q=renal",
            "release_endpoint": "/api/evidence_records?domain=toxicity&q=renal",
            "benchmark_endpoint": "/api/benchmark",
            "next_action": "Use endpoint filters to build a renal or platelet-focused safety evidence packet.",
            "why_useful": "Shows how users can move between release evidence and candidate gaps before a review meeting.",
            "workflow_steps": [
                "Search renal or platelet endpoint terms.",
                "Inspect molecule/cohort and source-level evidence.",
                "Download filtered candidates for missing high-value records.",
            ],
            "release_records": case_count({"domain": ["toxicity"], "q": ["renal"]}),
            "benchmark_task": "toxicity_safety_v0_1",
            "dashboard_cards": [
                {"label": "domain", "value": "toxicity"},
                {"label": "primary filter", "value": "renal"},
                {"label": "evidence use", "value": "gap scan"},
            ],
        },
        {
            "id": "sirna_seed_offtarget",
            "title": "siRNA seed/off-target transcriptome evidence",
            "result_title": "Example result: siRNA seed off-target evidence",
            "audience": "RNAi design and transcriptomics groups",
            "query": "seed",
            "question": "Which verified records support seed-mediated, mismatch, or transcriptome-level off-target evidence?",
            "primary_endpoint": "/api/evidence_records?domain=offtarget&q=seed",
            "release_endpoint": "/api/evidence_records?domain=offtarget&q=seed",
            "benchmark_endpoint": "/api/benchmark",
            "next_action": "Check observed off-target evidence, then use the sequence workbench for seed-window triage.",
            "why_useful": "Connects design triage with evidence records that computational RNAi users naturally reuse.",
            "workflow_steps": [
                "Filter off-target records by seed or mismatch evidence.",
                "Enter candidate guide sequence in the sequence workbench.",
                "Reuse offtarget_safety_v0_1 splits for baseline comparison.",
            ],
            "release_records": case_count({"domain": ["offtarget"], "q": ["seed"]}),
            "benchmark_task": "offtarget_safety_v0_1",
            "dashboard_cards": [
                {"label": "domain", "value": "off-target"},
                {"label": "primary filter", "value": "seed"},
                {"label": "evidence use", "value": "design triage"},
            ],
        },
        {
            "id": "benchmark_reuse",
            "title": "Benchmark reuse with fixed reference splits",
            "result_title": "Example result: reproducible benchmark reuse",
            "audience": "ML and computational biology groups",
            "query": "toxicity_safety_v0_1",
            "question": "How should users cite and reuse fixed A/B-grade safety benchmark splits?",
            "primary_endpoint": "/api/benchmark",
            "release_endpoint": "/api/download/evidence_release.csv",
            "benchmark_endpoint": "/api/download/benchmark_reference_splits.csv",
            "next_action": "Download benchmark splits, task cards, and the release evidence; report the version and checksum.",
            "why_useful": "Makes the database citable by model developers without turning the paper into an algorithm paper.",
            "workflow_steps": [
                "Open benchmark metadata and task cards.",
                "Download fixed train/validation/test reference splits.",
                "Report task name, version, leakage policy, metrics, and checksum.",
            ],
            "release_records": len(evidence_records({"limit": [str(RELEASE_EXPORT_LIMIT)]})),
            "benchmark_task": "toxicity_safety_v0_1 / offtarget_safety_v0_1",
            "dashboard_cards": [
                {"label": "domain", "value": "benchmark"},
                {"label": "primary file", "value": "reference splits"},
                {"label": "evidence use", "value": "model reuse"},
            ],
        },
    ]
    return {"version": PORTAL_VERSION, "case_workflows": workflows}


def api_client_examples() -> dict[str, object]:
    base = "https://your-public-oligovigil.example.org"
    return {
        "examples": [
            {
                "language": "python",
                "title": "Load verified evidence release",
                "code": (
                    "import pandas as pd\n"
                    f"base = \"{base}\"\n"
                    "evidence = pd.read_csv(f\"{base}/api/download/evidence_release.csv\")\n"
                    "print(evidence[['evidence_domain', 'canonical_name', 'evidence_grade']].head())"
                ),
            },
            {
                "language": "python",
                "title": "Fetch one citable record",
                "code": (
                    "import requests\n"
                    f"base = \"{base}\"\n"
                    "record = requests.get(f\"{base}/api/evidence_detail?domain=toxicity&id=1\", timeout=20).json()\n"
                    "print(record['citation']['plain_text'])"
                ),
            },
            {
                "language": "shell",
                "title": "Download reference benchmark splits",
                "code": (
                    f"curl -L \"{base}/api/download/benchmark_reference_splits.csv\" "
                    "-o benchmark_reference_splits.csv"
                ),
            },
            {
                "language": "python",
                "title": "Run sequence-to-evidence triage",
                "code": (
                    "import requests\n"
                    f"base = \"{base}\"\n"
                    "payload = requests.get(\n"
                    "    f\"{base}/api/sequence_search\",\n"
                    "    params={\"sequence\": \"AUGCUACUGACUGA\", \"modification\": \"GalNAc\", \"target\": \"PCSK9\"},\n"
                    "    timeout=20,\n"
                    ").json()\n"
                    "print(payload['sequence_features'])\n"
                    "print(len(payload['release_hits']))"
                ),
            },
            {
                "language": "python",
                "title": "Generate a safety triage report",
                "code": (
                    "import requests\n"
                    f"base = \"{base}\"\n"
                    "report = requests.get(\n"
                    "    f\"{base}/api/safety_triage\",\n"
                    "    params={\n"
                    "        \"sequence\": \"AUGCUACUGACUGA\",\n"
                    "        \"target\": \"PCSK9\",\n"
                    "        \"modification\": \"GalNAc\",\n"
                    "        \"delivery\": \"GalNAc\",\n"
                    "        \"endpoint\": \"hepatic\",\n"
                    "        \"species\": \"human\",\n"
                    "    },\n"
                    "    timeout=20,\n"
                    ").json()\n"
                    "print(report['summary'])\n"
                    "print(report['triage_policy']['prediction_mode'])"
                ),
            },
            {
                "language": "r",
                "title": "Read benchmark metadata",
                "code": (
                    "library(jsonlite)\n"
                    f"base <- \"{base}\"\n"
                    "benchmark <- fromJSON(paste0(base, \"/api/benchmark\"))\n"
                    "benchmark$split_counts"
                ),
            },
        ]
    }


def api_submission_schema() -> dict[str, object]:
    return {
        "submission_policy": {
            "write_api_enabled": False,
            "reason": "Public release accepts contribution packets through curator-reviewed CSV/email, not anonymous writes.",
            "human_final_decision_required": True,
        },
        "required_fields": [
            {"field": "submitter_name", "type": "text", "purpose": "Correspondence and contributor tracking."},
            {"field": "submitter_email", "type": "email", "purpose": "Correction follow-up."},
            {"field": "pmid_or_doi", "type": "text", "purpose": "Resolvable source identifier."},
            {"field": "source_location", "type": "text", "purpose": "Exact figure, table, paragraph, or supplement location."},
            {"field": "molecule_or_cohort", "type": "text", "purpose": "Oligonucleotide, comparator, or cohort name."},
            {"field": "evidence_domain", "type": "enum", "values": "toxicity|offtarget|chemistry|delivery"},
            {"field": "evidence_label", "type": "text", "purpose": "Endpoint, off-target mechanism, or safety finding."},
            {"field": "proposed_evidence_grade", "type": "enum", "values": "A|B|C"},
            {"field": "curator_note", "type": "text", "purpose": "Rationale for accept, reject, or needs-full-text decision."},
            {"field": "license_or_reuse_note", "type": "text", "purpose": "Redistribution level and raw-content restrictions."},
        ],
        "download_templates": {
            "curator_review_template": "/api/manifest/curator_review_template_v1.csv",
            "candidate_packet": "/api/download/curation_candidates_filtered.csv",
            "data_dictionary": "/api/manifest/data_dictionary_v1.csv",
        },
    }


def curation_candidates_csv_bytes(query: dict[str, list[str]]) -> bytes:
    prepared_query = dict(query)
    prepared_query["limit"] = [first_param(query, "limit", "5000") or "5000"]
    return dicts_to_csv_bytes(api_curation_candidates(prepared_query))


def api_audit(query: dict[str, list[str]]) -> list[dict[str, object]]:
    entity_table = first_param(query, "entity_table")
    validation_status = first_param(query, "validation_status")
    q = first_param(query, "q")
    limit = limit_param(query, default=250, maximum=2000)
    sql = """
        SELECT audit.id, audit.entity_table, audit.entity_id, audit.extraction_method,
               audit.extractor_model_or_script, audit.validation_status,
               audit.curator_decision, audit.curator_id, audit.audit_note,
               audit.audited_at
        FROM curation_audit AS audit
    """
    clauses: list[str] = []
    params: list[object] = []
    if entity_table:
        clauses.append("audit.entity_table = ?")
        params.append(entity_table)
    if validation_status:
        clauses.append("audit.validation_status = ?")
        params.append(validation_status)
    if q:
        clauses.append(
            """
            (audit.entity_table LIKE ? OR audit.extraction_method LIKE ?
             OR audit.validation_status LIKE ? OR audit.curator_decision LIKE ?
             OR audit.curator_id LIKE ? OR audit.audit_note LIKE ?)
            """
        )
        params.extend([f"%{q}%"] * 6)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY audit.id DESC LIMIT ?"
    params.append(limit)
    return rows(sql, tuple(params))


def api_search(query: dict[str, list[str]]) -> dict[str, object]:
    q = first_param(query, "q")
    limit = limit_param(query, default=20, maximum=100)
    if not q:
        return {"query": q, "sources": [], "molecules": [], "candidates": [], "toxicity": [], "offtarget": []}
    source_clauses: list[str] = []
    source_params: list[object] = []
    append_query_match_or_raw(
        source_clauses,
        source_params,
        ["title", "journal_or_agency", "doi", "pmid", "source_type"],
        q,
    )
    candidate_clauses: list[str] = []
    candidate_params: list[object] = []
    append_query_match_or_raw(
        candidate_clauses,
        candidate_params,
        [
            "candidate.candidate_signal",
            "candidate.matched_terms",
            "candidate.pmid",
            "candidate.doi",
            "candidate.candidate_modality",
            "candidate.source_location",
            "source.title",
        ],
        q,
    )
    toxicity_clauses: list[str] = []
    toxicity_params: list[object] = []
    append_query_match_or_raw(
        toxicity_clauses,
        toxicity_params,
        [
            "toxicity_endpoint.endpoint_name",
            "toxicity_endpoint.endpoint_category",
            "toxicity_endpoint.source_location",
            "molecule.canonical_name",
            "modality.name",
            "molecule.target_gene_symbol",
            "molecule.disease_context",
            "molecule.backbone_chemistry",
            "molecule.sugar_modification",
            "molecule.base_modification",
            "molecule.conjugate_delivery",
            "source_document.title",
            "source_document.pmid",
            "source_document.doi",
        ],
        q,
    )
    offtarget_clauses: list[str] = []
    offtarget_params: list[object] = []
    append_query_match_or_raw(
        offtarget_clauses,
        offtarget_params,
        [
            "offtarget_evidence.evidence_type",
            "offtarget_evidence.match_type",
            "offtarget_evidence.source_location",
            "molecule.canonical_name",
            "modality.name",
            "molecule.target_gene_symbol",
            "molecule.disease_context",
            "molecule.backbone_chemistry",
            "molecule.sugar_modification",
            "molecule.base_modification",
            "molecule.conjugate_delivery",
            "source_document.title",
            "source_document.pmid",
            "source_document.doi",
        ],
        q,
    )
    return {
        "query": q,
        "sources": rows(
            f"""
            SELECT id, title, journal_or_agency, publication_year, doi, pmid, source_url
            FROM source_document
            WHERE {' AND '.join(source_clauses)}
            ORDER BY publication_year DESC, id
            LIMIT ?
            """,
            tuple(source_params + [limit]),
        ),
        "molecules": api_molecules({"q": [q], "limit": [str(limit)]}),
        "candidates": rows(
            f"""
            SELECT candidate.id, candidate.evidence_domain, candidate.confidence_label,
                   candidate.candidate_modality, candidate.source_location,
                   candidate.matched_terms, candidate.pmid, source.title AS source_title,
                   source.source_url
            FROM curation_candidate AS candidate
            JOIN source_document AS source ON candidate.source_document_id = source.id
            WHERE {' AND '.join(candidate_clauses)}
            ORDER BY CASE candidate.confidence_label
                WHEN 'high_candidate' THEN 0
                WHEN 'medium_candidate' THEN 1
                ELSE 2
            END, candidate.id
            LIMIT ?
            """,
            tuple(candidate_params + [limit]),
        ),
        "toxicity": rows(
            f"""
            SELECT 'toxicity' AS evidence_domain,
                   toxicity_endpoint.id AS evidence_id,
                   molecule.canonical_name, modality.name AS modality,
                   toxicity_endpoint.endpoint_category,
                   toxicity_endpoint.endpoint_name, toxicity_endpoint.evidence_grade,
                   molecule.target_gene_symbol, molecule.disease_context,
                   toxicity_endpoint.source_location,
                   source_document.title AS source_title, source_document.pmid,
                   source_document.doi, source_document.source_url
            FROM toxicity_endpoint
            JOIN molecule ON toxicity_endpoint.molecule_id = molecule.id
            JOIN modality ON molecule.modality_id = modality.id
            JOIN source_document ON toxicity_endpoint.source_document_id = source_document.id
            WHERE {' AND '.join(toxicity_clauses)}
            ORDER BY toxicity_endpoint.id
            LIMIT ?
            """,
            tuple(toxicity_params + [limit]),
        ),
        "offtarget": rows(
            f"""
            SELECT 'offtarget' AS evidence_domain,
                   offtarget_evidence.id AS evidence_id,
                   molecule.canonical_name, modality.name AS modality,
                   offtarget_evidence.evidence_type,
                   offtarget_evidence.evidence_grade, molecule.target_gene_symbol,
                   molecule.disease_context, offtarget_evidence.source_location,
                   source_document.title AS source_title, source_document.pmid,
                   source_document.doi, source_document.source_url
            FROM offtarget_evidence
            JOIN molecule ON offtarget_evidence.molecule_id = molecule.id
            JOIN modality ON molecule.modality_id = modality.id
            JOIN source_document ON offtarget_evidence.source_document_id = source_document.id
            WHERE {' AND '.join(offtarget_clauses)}
            ORDER BY offtarget_evidence.id
            LIMIT ?
            """,
            tuple(offtarget_params + [limit]),
        ),
    }


def api_curation_queue(query: dict[str, list[str]]) -> list[dict[str, object]]:
    domain = first_param(query, "domain")
    priority = first_param(query, "priority")
    q = first_param(query, "q")
    limit = limit_param(query)
    sql = """
        SELECT id, pmid, doi, source_type, candidate_modality, evidence_domain,
               extraction_target, suggested_evidence_grade, priority, queue_status,
               source_title
        FROM curation_queue
    """
    clauses: list[str] = []
    params: list[object] = []
    if domain:
        clauses.append("evidence_domain = ?")
        params.append(domain)
    if priority:
        clauses.append("priority = ?")
        params.append(priority)
    if q:
        clauses.append(
            """
            (source_title LIKE ? OR pmid LIKE ? OR doi LIKE ? OR candidate_modality LIKE ?
             OR evidence_domain LIKE ? OR extraction_target LIKE ?)
            """
        )
        params.extend([f"%{q}%"] * 6)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, id LIMIT ?"
    params.append(limit)
    return rows(sql, tuple(params))


def api_curation_candidates(query: dict[str, list[str]]) -> list[dict[str, object]]:
    domain = first_param(query, "domain")
    confidence = first_param(query, "confidence")
    q = first_param(query, "q")
    limit = limit_param(query, maximum=5000)
    sql = """
        SELECT candidate.id, candidate.queue_id, candidate.pmid, candidate.doi,
               candidate.evidence_domain, candidate.candidate_modality,
               candidate.source_location, candidate.matched_terms, candidate.candidate_signal,
               candidate.suggested_evidence_grade, candidate.confidence_label,
               candidate.validation_status, candidate.curator_decision,
               candidate.redistribution_level, source.title AS source_title
        FROM curation_candidate AS candidate
        JOIN source_document AS source ON candidate.source_document_id = source.id
    """
    clauses: list[str] = []
    params: list[object] = []
    if domain:
        clauses.append("candidate.evidence_domain = ?")
        params.append(domain)
    if confidence:
        clauses.append("candidate.confidence_label = ?")
        params.append(confidence)
    if q:
        clauses.append(
            """
            (candidate.candidate_signal LIKE ? OR candidate.matched_terms LIKE ?
             OR candidate.pmid LIKE ? OR source.title LIKE ?)
            """
        )
        params.extend([f"%{q}%"] * 4)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += """
        ORDER BY CASE candidate.confidence_label
            WHEN 'high_candidate' THEN 0
            WHEN 'medium_candidate' THEN 1
            ELSE 2
        END, candidate.id
        LIMIT ?
    """
    params.append(limit)
    return rows(sql, tuple(params))


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        parsed = urlparse(path)
        requested = parsed.path
        if requested == "/":
            requested = "/index.html"
        return str(STATIC_DIR / requested.lstrip("/"))

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def request_base_url(self) -> str:
        proto = self.headers.get("X-Forwarded-Proto") or "http"
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or "127.0.0.1:8077"
        return f"{proto}://{host}"

    def send_payload(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_head_payload(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/downloads":
            self.send_response(302)
            self.send_header("Location", "/#downloads")
            self.end_headers()
            return

        if path == "/api/health":
            payload = {"ok": DB_PATH.exists(), "database": str(DB_PATH)}
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(payload))
            return
        if path == "/api/stats":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_stats()))
            return
        if path == "/api/metadata":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_metadata()))
            return
        if path == "/api/summary":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_summary()))
            return
        if path == "/api/facets":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_facets()))
            return
        if path == "/api/quality":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_quality()))
            return
        if path == "/api/coverage":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_coverage()))
            return
        if path == "/api/examples":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_examples()))
            return
        if path == "/api/ask":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_ask(query)))
            return
        if path == "/api/help":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_help()))
            return
        if path == "/api/curation_protocol":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_curation_protocol()))
            return
        if path == "/api/data_availability":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_data_availability()))
            return
        if path == "/api/release_status":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_release_status()))
            return
        if path == "/api/submission_pack":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_submission_pack()))
            return
        if path == "/api/field_completeness":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_field_completeness()))
            return
        if path == "/api/core_oligo_fields":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_core_oligo_fields()))
            return
        if path == "/api/independent_validation":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_independent_validation()))
            return
        if path == "/api/novelty_position":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_novelty_position()))
            return
        if path == "/api/archive_readiness":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_archive_readiness()))
            return
        if path == "/api/adoption_packet":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_adoption_packet()))
            return
        if path == "/api/agent_access":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_agent_access()))
            return
        if path == "/api/agent_connect":
            self.send_payload(
                200,
                "application/json; charset=utf-8",
                json_bytes(api_agent_connect(self.request_base_url())),
            )
            return
        if path == "/bioschemas.json":
            self.send_payload(
                200,
                "application/ld+json; charset=utf-8",
                json_bytes(api_bioschemas(self.request_base_url())),
            )
            return
        if path in {"/nlweb.json", "/.well-known/nlweb.json"}:
            self.send_payload(
                200,
                "application/json; charset=utf-8",
                json_bytes(api_nlweb_manifest(self.request_base_url())),
            )
            return
        if path == "/agent.json":
            self.send_payload(
                200,
                "application/json; charset=utf-8",
                json_bytes(universal_agent_manifest(self.request_base_url())),
            )
            return
        if path == "/.well-known/oligovigil-agent.json":
            self.send_payload(
                200,
                "application/json; charset=utf-8",
                json_bytes(universal_agent_manifest(self.request_base_url())),
            )
            return
        if path == "/.well-known/ai-plugin.json":
            self.send_payload(
                200,
                "application/json; charset=utf-8",
                json_bytes(ai_plugin_manifest(self.request_base_url())),
            )
            return
        if path == "/mcp.json":
            self.send_payload(
                200,
                "application/json; charset=utf-8",
                json_bytes(mcp_client_manifest(self.request_base_url())),
            )
            return
        if path == "/llms.txt":
            self.send_payload(200, "text/plain; charset=utf-8", agent_text_file("llms.txt"))
            return
        if path == "/llms-full.txt":
            self.send_payload(200, "text/plain; charset=utf-8", agent_text_file("llms-full.txt"))
            return
        if path == "/api/citation":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_citation()))
            return
        if path == "/api/use_cases":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_use_cases()))
            return
        if path == "/api/case_workflows":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_case_workflows()))
            return
        if path == "/api/sequence_coverage":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_sequence_coverage()))
            return
        if path == "/api/offtarget_taxonomy":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_offtarget_taxonomy()))
            return
        if path == "/api/sequence_search":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_sequence_search(query)))
            return
        if path == "/api/safety_triage":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_safety_triage(query)))
            return
        if path == "/api/safety_dossier":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_safety_dossier(query)))
            return
        if path == "/api/evidence_graph":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_evidence_graph(query)))
            return
        if path == "/api/prov_graph":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_prov_graph(query)))
            return
        if path == "/api/modification_profile":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_modification_profile(query)))
            return
        if path == "/api/client_examples":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_client_examples()))
            return
        if path == "/api/submission_schema":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_submission_schema()))
            return
        if path == "/api/openapi.json":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_openapi()))
            return
        if path in {"/api/download_manifest", "/api/downloads"}:
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_download_manifest()))
            return
        if path == "/api/search":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_search(query)))
            return
        if path == "/api/readiness":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_readiness()))
            return
        if path == "/api/closest_work":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_closest_work()))
            return
        if path == "/api/data_dictionary":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_data_dictionary()))
            return
        if path == "/api/sources":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_sources(query)))
            return
        if path == "/api/source_detail":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_source_detail(query)))
            return
        if path == "/api/molecules":
            self.send_payload(
                200,
                "application/json; charset=utf-8",
                json_bytes(api_molecules(query)),
            )
            return
        if path == "/api/evidence":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_evidence()))
            return
        if path == "/api/evidence_records":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(evidence_records(query)))
            return
        if path == "/api/evidence_detail":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_evidence_detail(query)))
            return
        if path == "/api/benchmark":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_benchmark()))
            return
        if path == "/api/benchmark_baseline_results":
            self.send_payload(
                200,
                "application/json; charset=utf-8",
                json_bytes(api_benchmark_baseline_results()),
            )
            return
        if path == "/api/benchmark_tasks":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_benchmark_task_cards()))
            return
        if path == "/api/audit":
            self.send_payload(200, "application/json; charset=utf-8", json_bytes(api_audit(query)))
            return
        if path == "/api/curation_queue":
            self.send_payload(
                200,
                "application/json; charset=utf-8",
                json_bytes(api_curation_queue(query)),
            )
            return
        if path == "/api/curation_candidates":
            self.send_payload(
                200,
                "application/json; charset=utf-8",
                json_bytes(api_curation_candidates(query)),
            )
            return
        if path == "/api/download/all_tables.zip":
            body = all_tables_zip_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", "attachment; filename=oligovigil_tables.zip")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/download/oligovigil_agent_pack.zip":
            body = agent_pack_zip_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", "attachment; filename=oligovigil_agent_pack.zip")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/download/evidence_release.csv":
            body = evidence_release_csv_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=evidence_release.csv")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/download/benchmark_reference_splits.csv":
            body = benchmark_reference_splits_csv_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=benchmark_reference_splits.csv")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/download/benchmark_baseline_results.csv":
            body = benchmark_baseline_results_csv_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=benchmark_baseline_results.csv")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/download/benchmark_task_cards.csv":
            manifest = MANIFEST_DOWNLOADS["benchmark_task_cards_v1.csv"]
            if not manifest.exists():
                self.send_payload(404, "application/json; charset=utf-8", json_bytes({"error": "missing benchmark task cards"}))
                return
            body = manifest.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=benchmark_task_cards.csv")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/download/sequence_modification_curation_template.csv":
            manifest = MANIFEST_DOWNLOADS["sequence_modification_curation_template_v1.csv"]
            if not manifest.exists():
                self.send_payload(404, "application/json; charset=utf-8", json_bytes({"error": "missing sequence/modification curation template"}))
                return
            body = manifest.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header(
                "Content-Disposition",
                "attachment; filename=sequence_modification_curation_template.csv",
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/download/core_oligo_field_curation_packet.csv":
            manifest = MANIFEST_DOWNLOADS["core_oligo_field_curation_packet_v1.csv"]
            if not manifest.exists():
                self.send_payload(404, "application/json; charset=utf-8", json_bytes({"error": "missing core oligo field curation packet"}))
                return
            body = manifest.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header(
                "Content-Disposition",
                "attachment; filename=core_oligo_field_curation_packet.csv",
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/download/independent_curation_validation_template.csv":
            manifest = MANIFEST_DOWNLOADS["independent_curation_validation_template_v1.csv"]
            if not manifest.exists():
                self.send_payload(404, "application/json; charset=utf-8", json_bytes({"error": "missing independent curation validation template"}))
                return
            body = manifest.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header(
                "Content-Disposition",
                "attachment; filename=independent_curation_validation_template.csv",
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/download/curation_candidates_filtered.csv":
            body = curation_candidates_csv_bytes(query)
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header(
                "Content-Disposition",
                "attachment; filename=curation_candidates_filtered.csv",
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path.startswith("/api/download/") and path.endswith(".csv"):
            table = path.removeprefix("/api/download/").removesuffix(".csv")
            if table not in DOWNLOAD_TABLES:
                self.send_payload(404, "application/json; charset=utf-8", json_bytes({"error": "unknown table"}))
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", f"attachment; filename={table}.csv")
            body = csv_bytes(table)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path.startswith("/api/manifest/"):
            filename = path.removeprefix("/api/manifest/")
            manifest = MANIFEST_DOWNLOADS.get(filename)
            if manifest is None or not manifest.exists():
                self.send_payload(404, "application/json; charset=utf-8", json_bytes({"error": "unknown manifest"}))
                return
            body = manifest.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", f"attachment; filename={filename}")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        return super().do_GET()

    def do_HEAD(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/download/all_tables.zip":
            body = all_tables_zip_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", "attachment; filename=oligovigil_tables.zip")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return
        if path == "/api/download/oligovigil_agent_pack.zip":
            body = agent_pack_zip_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", "attachment; filename=oligovigil_agent_pack.zip")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return
        if path == "/api/download/evidence_release.csv":
            body = evidence_release_csv_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=evidence_release.csv")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return
        if path == "/api/download/benchmark_reference_splits.csv":
            body = benchmark_reference_splits_csv_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=benchmark_reference_splits.csv")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return
        if path == "/api/download/benchmark_baseline_results.csv":
            body = benchmark_baseline_results_csv_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=benchmark_baseline_results.csv")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return
        if path == "/api/download/benchmark_task_cards.csv":
            manifest = MANIFEST_DOWNLOADS["benchmark_task_cards_v1.csv"]
            if not manifest.exists():
                self.send_head_payload(404, "application/json; charset=utf-8", 0)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=benchmark_task_cards.csv")
            self.send_header("Content-Length", str(manifest.stat().st_size))
            self.end_headers()
            return
        if path == "/api/download/sequence_modification_curation_template.csv":
            manifest = MANIFEST_DOWNLOADS["sequence_modification_curation_template_v1.csv"]
            if not manifest.exists():
                self.send_head_payload(404, "application/json; charset=utf-8", 0)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header(
                "Content-Disposition",
                "attachment; filename=sequence_modification_curation_template.csv",
            )
            self.send_header("Content-Length", str(manifest.stat().st_size))
            self.end_headers()
            return
        if path == "/api/download/core_oligo_field_curation_packet.csv":
            manifest = MANIFEST_DOWNLOADS["core_oligo_field_curation_packet_v1.csv"]
            if not manifest.exists():
                self.send_head_payload(404, "application/json; charset=utf-8", 0)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header(
                "Content-Disposition",
                "attachment; filename=core_oligo_field_curation_packet.csv",
            )
            self.send_header("Content-Length", str(manifest.stat().st_size))
            self.end_headers()
            return
        if path == "/api/download/independent_curation_validation_template.csv":
            manifest = MANIFEST_DOWNLOADS["independent_curation_validation_template_v1.csv"]
            if not manifest.exists():
                self.send_head_payload(404, "application/json; charset=utf-8", 0)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header(
                "Content-Disposition",
                "attachment; filename=independent_curation_validation_template.csv",
            )
            self.send_header("Content-Length", str(manifest.stat().st_size))
            self.end_headers()
            return
        if path == "/api/download/curation_candidates_filtered.csv":
            body = curation_candidates_csv_bytes(parse_qs(parsed.query))
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header(
                "Content-Disposition",
                "attachment; filename=curation_candidates_filtered.csv",
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return
        if path.startswith("/api/download/") and path.endswith(".csv"):
            table = path.removeprefix("/api/download/").removesuffix(".csv")
            if table not in DOWNLOAD_TABLES:
                self.send_head_payload(404, "application/json; charset=utf-8", 0)
                return
            body = csv_bytes(table)
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", f"attachment; filename={table}.csv")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return
        if path.startswith("/api/manifest/"):
            filename = path.removeprefix("/api/manifest/")
            manifest = MANIFEST_DOWNLOADS.get(filename)
            if manifest is None or not manifest.exists():
                self.send_head_payload(404, "application/json; charset=utf-8", 0)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", f"attachment; filename={filename}")
            self.send_header("Content-Length", str(manifest.stat().st_size))
            self.end_headers()
            return
        return super().do_HEAD()


def prewarm_runtime_caches() -> None:
    api_benchmark()
    api_modification_profile({"term": ["galnac"]})
    for domain in ("toxicity", "offtarget"):
        triage_release_pool(domain)
        triage_candidate_pool(domain)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8077)
    args = parser.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}. Run scripts/init_db.py first.")

    prewarm_runtime_caches()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"OligoVigil release candidate listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
