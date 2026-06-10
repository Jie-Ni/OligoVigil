from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
SEED_SOURCE_CSV = ROOT / "data" / "seed" / "source_document.csv"
SOURCE_CANDIDATES_V1 = ROOT / "data" / "manifests" / "source_candidates_v1.csv"
SOURCE_CANDIDATES_V2 = ROOT / "data" / "manifests" / "source_candidates_v2.csv"
SOURCE_CANDIDATES_V3 = ROOT / "data" / "manifests" / "source_candidates_v3.csv"
SOURCE_CANDIDATES_V4 = ROOT / "data" / "manifests" / "source_candidates_v4.csv"
SOURCE_CANDIDATES_V5 = ROOT / "data" / "manifests" / "source_candidates_v5.csv"
GENERATED_DIR = ROOT / "data" / "generated"
DISCOVERY_CSV = GENERATED_DIR / "pubmed_discovery_candidates_v1.csv"
DISCOVERY_CSV_V2 = GENERATED_DIR / "pubmed_discovery_candidates_v2.csv"
DISCOVERY_CSV_V3 = GENERATED_DIR / "pubmed_discovery_candidates_v3.csv"
DISCOVERY_CSV_V4 = GENERATED_DIR / "pubmed_discovery_candidates_v4.csv"

QUERIES = [
    (
        "aso_toxicity_safety_2024_2026",
        '"antisense oligonucleotide" AND (toxicity OR safety OR hepatotoxicity OR renal OR thrombocytopenia OR "DNA damage") AND 2024:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "sirna_offtarget_safety_2024_2026",
        '(siRNA OR RNAi) AND ("off-target" OR "off target" OR seed OR transcriptome OR toxicity OR safety) AND 2024:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "oligo_therapeutics_safety_2023_2026",
        '"oligonucleotide therapeutics" AND (toxicity OR safety OR "adverse event" OR immunogenicity OR tolerability) AND 2023:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "aso_offtarget_transcriptome_2023_2026",
        '("antisense oligonucleotide" OR ASO) AND ("off-target" OR "off target" OR transcriptome OR hybridization OR mismatch) AND 2023:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "aso_immune_complement_safety_2023_2026",
        '("antisense oligonucleotide" OR ASO) AND (immune OR immunostimulation OR complement OR TLR OR cytokine OR thrombocytopenia) AND 2023:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "sirna_seed_transcriptome_2023_2026",
        '(siRNA OR RNAi OR "small interfering RNA") AND (seed OR "off-target" OR "off target" OR transcriptome OR unintended) AND 2023:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "sirna_clinical_safety_2023_2026",
        '(siRNA OR RNAi OR "small interfering RNA") AND ("clinical trial" OR phase OR patient) AND (safety OR adverse OR tolerability) AND 2023:2026[pdat]',
        "literature_discovery",
        "secondary",
    ),
    (
        "galnac_sirna_safety_2024_2026",
        '"GalNAc" AND (siRNA OR "small interfering RNA") AND (safety OR toxicity OR "off-target" OR pharmacokinetic) AND 2024:2026[pdat]',
        "literature_discovery",
        "secondary",
    ),
    (
        "phosphorothioate_aso_safety_2024_2026",
        'phosphorothioate AND ("antisense oligonucleotide" OR ASO) AND (toxicity OR safety OR protein OR immune OR "DNA damage") AND 2024:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "lnp_oligo_delivery_safety_2023_2026",
        '("lipid nanoparticle" OR LNP OR nanoparticle) AND (siRNA OR RNAi OR oligonucleotide) AND (safety OR toxicity OR delivery OR uptake) AND 2023:2026[pdat]',
        "literature_discovery",
        "secondary",
    ),
    (
        "chemical_modification_oligo_safety_2023_2026",
        '("2-O-methyl" OR "2\'-O-methyl" OR "2-MOE" OR "2\'-MOE" OR LNA OR phosphorothioate OR GalNAc) AND (oligonucleotide OR ASO OR siRNA) AND (toxicity OR safety OR off-target OR "off target") AND 2023:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "oligo_prediction_benchmark_2023_2026",
        '(oligonucleotide OR siRNA OR "antisense oligonucleotide") AND (prediction OR model OR benchmark OR database OR dataset) AND (toxicity OR safety OR "off-target" OR efficacy) AND 2023:2026[pdat]',
        "literature_discovery",
        "secondary",
    ),
    (
        "gapmer_aso_hepatotoxicity_2020_2026",
        '(gapmer OR "RNase H" OR "RNase-H") AND ("antisense oligonucleotide" OR ASO) AND (hepatotoxicity OR liver OR toxicity OR safety) AND 2020:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "aso_thrombocytopenia_complement_2020_2026",
        '("antisense oligonucleotide" OR ASO OR oligonucleotide) AND (thrombocytopenia OR complement OR platelet OR coagulation) AND 2020:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "aso_kidney_toxicity_2020_2026",
        '("antisense oligonucleotide" OR ASO OR oligonucleotide) AND (kidney OR renal OR nephrotoxicity OR glomerular) AND (toxicity OR safety OR adverse) AND 2020:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "oligo_innate_immune_tlr_2020_2026",
        '(oligonucleotide OR siRNA OR "antisense oligonucleotide") AND (TLR OR "toll-like" OR innate OR cytokine OR interferon OR immunostimulation) AND 2020:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "locked_nucleic_acid_safety_2020_2026",
        '("locked nucleic acid" OR LNA OR "constrained ethyl" OR cEt) AND (oligonucleotide OR antisense OR siRNA) AND (toxicity OR safety OR adverse OR hepatotoxicity) AND 2020:2026[pdat]',
        "literature_discovery",
        "secondary",
    ),
    (
        "sso_splice_oligo_safety_2020_2026",
        '("splice-switching oligonucleotide" OR "splice switching oligonucleotide" OR "exon skipping" OR "splice-modulating oligonucleotide") AND (safety OR toxicity OR adverse OR tolerability) AND 2020:2026[pdat]',
        "literature_discovery",
        "secondary",
    ),
    (
        "sirna_seed_toxicity_broad_2020_2026",
        '("small interfering RNA" OR siRNA OR RNAi) AND (seed OR "miRNA-like" OR "off-target" OR "off target" OR transcriptome) AND (toxicity OR safety OR phenotype OR unintended) AND 2020:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "rnai_screen_offtarget_2020_2026",
        '(RNAi OR siRNA OR shRNA) AND ("off-target" OR "off target" OR seed OR transcriptome) AND (screen OR screening OR validation OR benchmark) AND 2020:2026[pdat]',
        "literature_discovery",
        "secondary",
    ),
    (
        "galnac_conjugate_clinical_safety_2020_2026",
        '(GalNAc OR "N-acetylgalactosamine") AND (siRNA OR oligonucleotide OR antisense) AND ("clinical" OR patient OR trial OR phase) AND (safety OR adverse OR tolerability) AND 2020:2026[pdat]',
        "literature_discovery",
        "secondary",
    ),
    (
        "lnp_rna_safety_toxicity_2020_2026",
        '("lipid nanoparticle" OR LNP) AND (siRNA OR RNAi OR oligonucleotide OR "RNA therapy") AND (toxicity OR safety OR immunogenicity OR reactogenicity OR adverse) AND 2020:2026[pdat]',
        "literature_discovery",
        "secondary",
    ),
    (
        "oligo_drug_discovery_safety_review_2020_2026",
        '("oligonucleotide therapeutics" OR "RNA therapeutics") AND (safety OR toxicity OR "off-target" OR "off target" OR adverse) AND (review OR perspective OR guideline) AND 2020:2026[pdat]',
        "literature_discovery",
        "secondary",
    ),
    (
        "oligo_nonclinical_safety_2020_2026",
        '(oligonucleotide OR "antisense oligonucleotide" OR siRNA) AND ("nonclinical" OR preclinical OR toxicology OR "safety assessment") AND 2020:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "oligo_chemistry_toxicity_mechanism_2020_2026",
        '(phosphorothioate OR "2-O-methoxyethyl" OR "2-MOE" OR "2\'-MOE" OR "2\'-O-methyl" OR PMO OR morpholino) AND (toxicity OR safety OR protein-binding OR "protein binding" OR hepatotoxicity) AND 2020:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "oligo_sequence_dependent_toxicity_2020_2026",
        '(oligonucleotide OR "antisense oligonucleotide" OR siRNA) AND ("sequence-dependent" OR "sequence dependent" OR motif OR "off-target" OR hybridization) AND (toxicity OR safety) AND 2020:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "oligo_safety_toxicology_broad_2010_2026",
        '(oligonucleotide OR oligonucleotides OR siRNA OR RNAi OR "small interfering RNA" OR "antisense oligonucleotide" OR ASO OR gapmer OR shRNA) AND (safety OR toxicity OR toxicology OR adverse OR tolerability OR immunogenicity OR hepatotoxicity OR renal OR thrombocytopenia OR "off-target" OR "off target") AND 2010:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "rna_therapeutics_safety_broad_2010_2026",
        '("RNA therapeutics" OR "oligonucleotide therapeutics" OR "nucleic acid therapeutics" OR "RNA interference therapeutics") AND (safety OR toxicity OR toxicology OR adverse OR delivery OR immunogenicity OR "off-target" OR "off target") AND 2010:2026[pdat]',
        "literature_discovery",
        "secondary",
    ),
    (
        "sirna_rnai_offtarget_broad_2010_2026",
        '(siRNA OR "small interfering RNA" OR RNAi OR shRNA) AND ("off-target" OR "off target" OR seed OR transcriptome OR unintended OR specificity OR silencing OR screening) AND 2010:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "sirna_rnai_safety_broad_2010_2026",
        '(siRNA OR "small interfering RNA" OR RNAi OR shRNA) AND (safety OR toxicity OR adverse OR immunogenicity OR delivery OR nanoparticle OR GalNAc OR tolerability) AND 2010:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "aso_safety_broad_2010_2026",
        '("antisense oligonucleotide" OR "antisense oligonucleotides" OR ASO OR gapmer OR "RNase H" OR "splice switching oligonucleotide" OR "exon skipping") AND (safety OR toxicity OR toxicology OR adverse OR tolerability OR hepatotoxicity OR renal OR thrombocytopenia OR complement OR immunogenicity) AND 2010:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "oligo_delivery_safety_broad_2010_2026",
        '(oligonucleotide OR siRNA OR RNAi OR "antisense oligonucleotide" OR ASO) AND (delivery OR GalNAc OR conjugate OR "lipid nanoparticle" OR LNP OR nanoparticle OR formulation) AND (safety OR toxicity OR adverse OR immunogenicity OR uptake) AND 2010:2026[pdat]',
        "literature_discovery",
        "secondary",
    ),
    (
        "oligo_chemistry_safety_broad_2010_2026",
        '(phosphorothioate OR "2-O-methyl" OR "2\'-O-methyl" OR "2-O-methoxyethyl" OR "2-MOE" OR "2\'-MOE" OR LNA OR PMO OR morpholino OR GalNAc) AND (oligonucleotide OR siRNA OR antisense OR ASO) AND (safety OR toxicity OR adverse OR immunogenicity OR off-target OR "off target") AND 2010:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "oligo_preclinical_clinical_safety_2010_2026",
        '(oligonucleotide OR siRNA OR RNAi OR "antisense oligonucleotide" OR ASO) AND (preclinical OR nonclinical OR clinical OR trial OR phase OR patient OR toxicology) AND (safety OR adverse OR toxicity OR tolerability) AND 2010:2026[pdat]',
        "literature_discovery",
        "secondary",
    ),
    (
        "oligo_transcriptome_specificity_2010_2026",
        '(oligonucleotide OR siRNA OR RNAi OR "antisense oligonucleotide" OR ASO) AND (transcriptome OR RNA-seq OR microarray OR specificity OR hybridization OR mismatch OR seed) AND ("off-target" OR "off target" OR unintended OR toxicity OR safety) AND 2010:2026[pdat]',
        "literature_discovery",
        "core",
    ),
    (
        "oligo_model_benchmark_safety_2010_2026",
        '(oligonucleotide OR siRNA OR RNAi OR "antisense oligonucleotide" OR ASO) AND (database OR dataset OR benchmark OR prediction OR model OR machine-learning OR "machine learning") AND (toxicity OR safety OR efficacy OR "off-target" OR "off target") AND 2010:2026[pdat]',
        "literature_discovery",
        "secondary",
    ),
]

TITLE_KEYWORDS = {
    "toxicity": 4,
    "toxic": 4,
    "safety": 4,
    "off-target": 4,
    "off target": 4,
    "seed": 3,
    "transcriptome": 3,
    "hepatotoxicity": 4,
    "renal": 3,
    "hematological": 3,
    "thrombocytopenia": 4,
    "dna damage": 4,
    "phosphorothioate": 3,
    "galnac": 2,
    "antisense": 2,
    "sirna": 2,
    "oligonucleotide": 2,
    "rna interference": 2,
    "immunogenicity": 3,
    "immunostimulation": 3,
    "complement": 3,
    "cytokine": 2,
    "clinical trial": 2,
    "adverse event": 3,
    "lipid nanoparticle": 2,
    "lnp": 2,
    "lna": 2,
    "2'-o-methyl": 2,
    "2'-moe": 2,
    "prediction": 1,
    "benchmark": 1,
    "database": 1,
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def existing_pmids() -> set[str]:
    pmids: set[str] = set()
    for path in [
        SEED_SOURCE_CSV,
        SOURCE_CANDIDATES_V1,
        SOURCE_CANDIDATES_V2,
        SOURCE_CANDIDATES_V3,
        SOURCE_CANDIDATES_V4,
        SOURCE_CANDIDATES_V5,
    ]:
        for row in read_csv(path):
            pmid = row.get("pmid")
            if pmid:
                pmids.add(pmid)
    return pmids


def active_manifest_rows() -> list[dict[str, str]]:
    if SOURCE_CANDIDATES_V5.exists():
        return read_csv(SOURCE_CANDIDATES_V5)
    if SOURCE_CANDIDATES_V4.exists():
        return read_csv(SOURCE_CANDIDATES_V4)
    if SOURCE_CANDIDATES_V3.exists():
        return read_csv(SOURCE_CANDIDATES_V3)
    if SOURCE_CANDIDATES_V2.exists():
        return read_csv(SOURCE_CANDIDATES_V2)
    return read_csv(SOURCE_CANDIDATES_V1)


def esearch(term: str, retmax: int) -> list[str]:
    query = urlencode(
        {
            "db": "pubmed",
            "term": term,
            "retmode": "json",
            "retmax": str(retmax),
            "sort": "pub+date",
        }
    )
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{query}"
    with ncbi_open(url) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("esearchresult", {}).get("idlist", [])


def ncbi_open(url: str):
    delay = 2.0
    for attempt in range(6):
        try:
            time.sleep(0.35)
            return urlopen(url, timeout=45)
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 5:
                raise
            time.sleep(delay)
            delay *= 1.8
    raise RuntimeError("unreachable NCBI retry state")


def esummary_chunk(pmids: list[str]) -> dict[str, dict]:
    if not pmids:
        return {}
    query = urlencode({"db": "pubmed", "id": ",".join(pmids), "retmode": "json"})
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?{query}"
    with ncbi_open(url) as response:
        payload = json.loads(response.read().decode("utf-8"))
    result = payload["result"]
    return {uid: result[uid] for uid in result["uids"]}


def esummary(pmids: list[str]) -> dict[str, dict]:
    records: dict[str, dict] = {}
    for start in range(0, len(pmids), 150):
        records.update(esummary_chunk(pmids[start : start + 150]))
    return records


def year_from_pubdate(pubdate: str) -> str:
    for token in re.split(r"\D+", pubdate):
        if len(token) == 4 and token.isdigit():
            return token
    return ""


def score_title(title: str) -> int:
    lower = title.lower()
    return sum(weight for keyword, weight in TITLE_KEYWORDS.items() if keyword in lower)


def discover(retmax_per_query: int, max_add: int) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    known = existing_pmids()
    discovered: dict[str, dict[str, str]] = {}
    for label, term, source_type, priority in QUERIES:
        pmids = [pmid for pmid in esearch(term, retmax_per_query) if pmid not in known]
        summaries = esummary(pmids)
        for pmid in pmids:
            record = summaries.get(pmid)
            if not record:
                continue
            title = record.get("title", "")
            score = score_title(title)
            if pmid in discovered and int(discovered[pmid]["score"]) >= score:
                continue
            discovered[pmid] = {
                "pmid": pmid,
                "source_type": source_type,
                "reuse_category": "derived_annotations_only",
                "license_status": "abstract_metadata_only",
                "priority": priority,
                "query_label": label,
                "score": str(score),
                "title": title,
                "journal": record.get("source", ""),
                "publication_year": year_from_pubdate(record.get("pubdate", "")),
            }

    ranked = sorted(
        discovered.values(),
        key=lambda row: (int(row["score"]), row["publication_year"], row["pmid"]),
        reverse=True,
    )
    selected = ranked[:max_add]
    existing_rows = active_manifest_rows()
    existing_keys = {row["source_key"] for row in existing_rows}
    existing_manifest_pmids = {row.get("pmid", "") for row in existing_rows if row.get("pmid")}
    manifest_rows = list(existing_rows)
    for row in selected:
        source_key = f"pubmed_discovery_{row['pmid']}"
        if source_key in existing_keys or row["pmid"] in existing_manifest_pmids:
            continue
        manifest_rows.append(
            {
                "source_key": source_key,
                "pmid": row["pmid"],
                "source_type": row["source_type"],
                "reuse_category": row["reuse_category"],
                "license_status": row["license_status"],
                "priority": row["priority"],
                "notes": f"{row['query_label']}; score={row['score']}; {row['title']}",
            }
        )
    return ranked, manifest_rows


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retmax-per-query", type=int, default=160)
    parser.add_argument("--max-add", type=int, default=260)
    args = parser.parse_args()

    ranked, manifest_rows = discover(args.retmax_per_query, args.max_add)
    discovery_fields = [
        "pmid",
        "source_type",
        "reuse_category",
        "license_status",
        "priority",
        "query_label",
        "score",
        "title",
        "journal",
        "publication_year",
    ]
    write_csv(DISCOVERY_CSV_V3, ranked, discovery_fields)
    write_csv(DISCOVERY_CSV_V4, ranked, discovery_fields)
    write_csv(DISCOVERY_CSV_V2, ranked, discovery_fields)
    write_csv(DISCOVERY_CSV, ranked, discovery_fields)
    write_csv(
        SOURCE_CANDIDATES_V5,
        manifest_rows,
        ["source_key", "pmid", "source_type", "reuse_category", "license_status", "priority", "notes"],
    )
    print(f"discovered={len(ranked)} selected_manifest_rows={len(manifest_rows)}")
    print(f"discovery_csv={DISCOVERY_CSV}")
    print(f"discovery_csv_v2={DISCOVERY_CSV_V2}")
    print(f"discovery_csv_v3={DISCOVERY_CSV_V3}")
    print(f"discovery_csv_v4={DISCOVERY_CSV_V4}")
    print(f"source_candidates_v5={SOURCE_CANDIDATES_V5}")


if __name__ == "__main__":
    main()
