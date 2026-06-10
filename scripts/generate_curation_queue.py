from __future__ import annotations

import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "oligosafety.db"
GENERATED_DIR = ROOT / "data" / "generated"
QUEUE_CSV = GENERATED_DIR / "curation_queue_v1.csv"

TARGETS = [
    ("source_provenance", "source_location", "C", "high"),
    ("molecule_identity", "sequence_or_molecule_name", "B", "high"),
    ("chemistry", "site_level_modification_or_chemistry_summary", "B", "high"),
    ("delivery", "delivery_modality_and_route", "C", "medium"),
    ("assay", "model_system_dose_time_replicates", "B", "high"),
    ("toxicity", "toxicity_endpoint_and_direction", "B", "high"),
    ("offtarget", "transcriptome_or_seed_offtarget_evidence", "B", "high"),
    ("benchmark", "benchmark_eligibility_and_leakage_group", "C", "medium"),
]


def infer_modality(title: str) -> str:
    lower = title.lower()
    if "sirna" in lower or "rnai" in lower:
        return "siRNA"
    if "antisense" in lower or "aso" in lower or "oligonucleotide" in lower:
        return "ASO"
    return "ASO/siRNA"


def infer_domains(title: str, source_type: str) -> list[tuple[str, str, str, str]]:
    lower = title.lower()
    domains = [TARGETS[0], TARGETS[1]]
    if any(
        word in lower
        for word in [
            "chemical",
            "modified",
            "modification",
            "phosphorothioate",
            "galnac",
            "locked nucleic acid",
            "lna",
            "moe",
            "morpholino",
            "pmo",
            "conjugate",
            "chemistry",
        ]
    ):
        domains.append(TARGETS[2])
    if any(
        word in lower
        for word in [
            "delivery",
            "nanoparticle",
            "galnac",
            "lnp",
            "conjugate",
            "formulation",
            "uptake",
            "lipid",
            "carrier",
            "vehicle",
            "targeted",
        ]
    ):
        domains.append(TARGETS[3])
    if any(
        word in lower
        for word in [
            "trial",
            "phase",
            "screen",
            "screening",
            "assay",
            "preclinical",
            "nonclinical",
            "toxicology",
            "model",
            "clinical",
            "patient",
            "dose",
            "study",
        ]
    ):
        domains.append(TARGETS[4])
    if any(
        word in lower
        for word in [
            "toxicity",
            "toxic",
            "safety",
            "risk",
            "adverse",
            "tolerability",
            "immunogenicity",
            "immunostimulation",
            "immune",
            "innate",
            "cytokine",
            "interferon",
            "tlr",
            "complement",
            "platelet",
            "thrombocytopenia",
            "hepatotoxicity",
            "liver",
            "renal",
            "kidney",
            "hematological",
            "dna damage",
        ]
    ):
        domains.append(TARGETS[5])
    if any(
        word in lower
        for word in [
            "off-target",
            "off target",
            "seed",
            "transcriptome",
            "hybridization",
            "mismatch",
            "specificity",
            "unintended",
            "silencing",
            "rna-seq",
            "microarray",
        ]
    ):
        domains.append(TARGETS[6])
    if source_type in {"industry_guidance", "tool_reference", "method_reference", "literature_signal"} or any(
        word in lower for word in ["database", "dataset", "benchmark", "prediction", "model", "machine learning"]
    ):
        domains.append(TARGETS[7])
    return list(dict.fromkeys(domains))


def source_rows() -> list[sqlite3.Row]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return list(
            conn.execute(
                """
                SELECT id, source_type, pmid, doi, title
                FROM source_document
                WHERE source_type NOT IN ('nar_guideline', 'nar_editorial', 'closest_work')
                ORDER BY id
                """
            )
        )
    finally:
        conn.close()


def write_queue(rows: list[dict[str, object]]) -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with QUEUE_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def load_queue(rows: list[dict[str, object]]) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM curation_queue")
        columns = list(rows[0].keys()) if rows else []
        if rows:
            placeholders = ", ".join(["?"] * len(columns))
            col_sql = ", ".join(columns)
            conn.executemany(
                f"INSERT INTO curation_queue ({col_sql}) VALUES ({placeholders})",
                [[row[col] for col in columns] for row in rows],
            )
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows: list[dict[str, object]] = []
    next_id = 1
    for source in source_rows():
        title = source["title"] or ""
        modality = infer_modality(title)
        for evidence_domain, extraction_target, grade, priority in infer_domains(
            title, source["source_type"]
        ):
            rows.append(
                {
                    "id": next_id,
                    "source_document_id": source["id"],
                    "pmid": source["pmid"],
                    "doi": source["doi"],
                    "source_title": title,
                    "source_type": source["source_type"],
                    "candidate_modality": modality,
                    "evidence_domain": evidence_domain,
                    "extraction_target": extraction_target,
                    "suggested_evidence_grade": grade,
                    "priority": priority,
                    "queue_status": "candidate",
                    "curator_id": "",
                    "created_at": created_at,
                }
            )
            next_id += 1
    write_queue(rows)
    load_queue(rows)
    print(f"curation_queue={len(rows)} generated={QUEUE_CSV}")


if __name__ == "__main__":
    main()
