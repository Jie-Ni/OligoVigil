from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT.parents[1] / "data" / "oligosafety.db"
OUT_DIR = ROOT / "figures" / "source_data"
ROWS_CSV = OUT_DIR / "FIG3_evidence_landscape_v3_rows.csv"
SUMMARY_JSON = OUT_DIR / "FIG3_evidence_landscape_v3_summary.json"


def modality_group(name: str | None) -> str:
    value = (name or "unknown").lower()
    if "aso/sirna" in value or "aso/rna" in value:
        return "mixed ASO/siRNA"
    if "sirna" in value:
        return "siRNA"
    if "aso" in value or "lna" in value:
        return "ASO/gapmer"
    if "pmo" in value:
        return "PMO"
    if "cpg" in value:
        return "CpG ODN"
    return "other"


def toxicity_group(category: str | None) -> str:
    value = (category or "other").lower()
    if "hepatic" in value:
        return "hepatic"
    if "renal" in value:
        return "renal"
    if "immune" in value or "complement" in value or "cytokine" in value:
        return "immune"
    if "hemat" in value or "platelet" in value or "thrombo" in value:
        return "hematologic"
    if "neuro" in value:
        return "neurological"
    if "geno" in value:
        return "genotoxicity"
    if "chemistry" in value or "delivery" in value:
        return "chemistry/delivery"
    return "general/other safety"


def offtarget_group(evidence_type: str | None) -> str:
    value = (evidence_type or "other").lower()
    if "seed" in value:
        return "seed-mediated"
    if "mismatch" in value or "hybrid" in value:
        return "mismatch/hybridization"
    if "transcriptome" in value or "rna-seq" in value or "microarray" in value:
        return "transcriptome-wide"
    return "general specificity"


def fetch_rows(con: sqlite3.Connection) -> list[dict[str, str]]:
    sql = """
    SELECT 'toxicity' AS domain,
           te.id AS entity_id,
           te.endpoint_category AS raw_category,
           te.endpoint_name AS endpoint_name,
           te.evidence_grade AS grade,
           m.canonical_name AS molecule_name,
           mo.name AS modality,
           sd.id AS source_id,
           sd.pmid AS pmid,
           sd.pmcid AS pmcid,
           sd.doi AS doi,
           sd.publication_year AS publication_year,
           sd.journal_or_agency AS journal,
           a.organism AS organism,
           a.model_system AS model_system,
           a.cell_line_or_tissue AS tissue,
           a.dose_value AS dose_value,
           bs.split_name AS split_name,
           m.sense_sequence AS sense_sequence,
           m.antisense_sequence AS antisense_sequence,
           m.guide_sequence AS guide_sequence,
           m.seed_region AS seed_region,
           m.backbone_chemistry AS backbone_chemistry,
           m.sugar_modification AS sugar_modification,
           m.base_modification AS base_modification,
           m.conjugate_delivery AS conjugate_delivery
      FROM toxicity_endpoint te
      JOIN release_audit_v ra
        ON ra.entity_table='toxicity_endpoint' AND ra.entity_id=te.id
      LEFT JOIN molecule m ON te.molecule_id=m.id
      LEFT JOIN modality mo ON m.modality_id=mo.id
      LEFT JOIN source_document sd ON te.source_document_id=sd.id
      LEFT JOIN assay a ON te.assay_id=a.id
      LEFT JOIN benchmark_split bs
        ON bs.entity_table='toxicity_endpoint' AND bs.entity_id=te.id
    UNION ALL
    SELECT 'off-target' AS domain,
           oe.id AS entity_id,
           oe.evidence_type AS raw_category,
           oe.evidence_type AS endpoint_name,
           oe.evidence_grade AS grade,
           m.canonical_name AS molecule_name,
           mo.name AS modality,
           sd.id AS source_id,
           sd.pmid AS pmid,
           sd.pmcid AS pmcid,
           sd.doi AS doi,
           sd.publication_year AS publication_year,
           sd.journal_or_agency AS journal,
           a.organism AS organism,
           a.model_system AS model_system,
           a.cell_line_or_tissue AS tissue,
           a.dose_value AS dose_value,
           bs.split_name AS split_name,
           m.sense_sequence AS sense_sequence,
           m.antisense_sequence AS antisense_sequence,
           m.guide_sequence AS guide_sequence,
           m.seed_region AS seed_region,
           m.backbone_chemistry AS backbone_chemistry,
           m.sugar_modification AS sugar_modification,
           m.base_modification AS base_modification,
           m.conjugate_delivery AS conjugate_delivery
      FROM offtarget_evidence oe
      JOIN release_audit_v ra
        ON ra.entity_table='offtarget_evidence' AND ra.entity_id=oe.id
      LEFT JOIN molecule m ON oe.molecule_id=m.id
      LEFT JOIN modality mo ON m.modality_id=mo.id
      LEFT JOIN source_document sd ON oe.source_document_id=sd.id
      LEFT JOIN assay a ON oe.assay_id=a.id
      LEFT JOIN benchmark_split bs
        ON bs.entity_table='offtarget_evidence' AND bs.entity_id=oe.id
    """
    out: list[dict[str, str]] = []
    for row in con.execute(sql):
        names = [description[0] for description in con.execute(sql).description]
        break
    cursor = con.execute(sql)
    names = [description[0] for description in cursor.description]
    for values in cursor:
        record = {name: "" if value is None else str(value) for name, value in zip(names, values)}
        record["modality_group"] = modality_group(record["modality"])
        if record["domain"] == "toxicity":
            record["endpoint_group"] = toxicity_group(record["raw_category"])
        else:
            record["endpoint_group"] = offtarget_group(record["raw_category"])
        record["benchmark_status"] = "benchmark split" if record["split_name"] else "release only"
        record["source_depth"] = "PMC full text" if record["pmcid"] else "abstract/metadata"
        record["has_sequence_or_seed"] = str(
            int(any(record[key] for key in ["sense_sequence", "antisense_sequence", "guide_sequence", "seed_region"]))
        )
        record["has_chemistry_or_delivery"] = str(
            int(any(record[key] for key in ["backbone_chemistry", "sugar_modification", "base_modification", "conjugate_delivery"]))
        )
        record["has_dose"] = str(int(bool(record["dose_value"])))
        out.append(record)
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        rows = fetch_rows(con)

    fieldnames = list(rows[0].keys())
    with ROWS_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "release_rows": len(rows),
        "toxicity_rows": sum(row["domain"] == "toxicity" for row in rows),
        "offtarget_rows": sum(row["domain"] == "off-target" for row in rows),
        "distinct_sources": len({row["source_id"] for row in rows if row["source_id"]}),
        "full_text_rows": sum(row["source_depth"] == "PMC full text" for row in rows),
        "benchmark_rows": sum(row["benchmark_status"] == "benchmark split" for row in rows),
        "sequence_or_seed_rows": sum(row["has_sequence_or_seed"] == "1" for row in rows),
        "chemistry_or_delivery_rows": sum(row["has_chemistry_or_delivery"] == "1" for row in rows),
        "dose_rows": sum(row["has_dose"] == "1" for row in rows),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
