from __future__ import annotations

import csv
import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "oligosafety.db"
GENERATED_DIR = ROOT / "data" / "generated"
CANDIDATE_CSV = GENERATED_DIR / "curation_candidate_v1.csv"
CANDIDATE_JSON = GENERATED_DIR / "curation_candidate_v1.json"

TARGET_DOMAINS = {"toxicity", "offtarget", "chemistry", "delivery", "assay", "benchmark"}
KEYWORDS = {
    "toxicity": [
        "toxicity",
        "toxic",
        "safety",
        "risk",
        "adverse",
        "hepatotoxicity",
        "renal",
        "hematological",
        "proarrhythmic",
        "dna damage",
        "tolerability",
    ],
    "offtarget": [
        "off-target",
        "off target",
        "seed",
        "transcriptome",
        "hybridization",
        "mismatch",
        "unintended",
        "silencing",
    ],
    "chemistry": [
        "chemical",
        "modification",
        "modified",
        "phosphorothioate",
        "galnac",
        "2'-o",
        "2'-moe",
        "lna",
        "amna",
        "conjugate",
    ],
    "delivery": [
        "delivery",
        "nanoparticle",
        "galnac",
        "conjugated",
        "lnp",
        "uptake",
        "route",
    ],
    "assay": [
        "assay",
        "screen",
        "preclinical",
        "model",
        "rna-seq",
        "experiment",
        "phase",
        "trial",
    ],
    "benchmark": [
        "database",
        "model",
        "prediction",
        "tool",
        "generator",
        "benchmark",
        "challenge",
        "dataset",
    ],
}


def queue_rows() -> list[sqlite3.Row]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return list(
            conn.execute(
                """
                SELECT id, source_document_id, pmid, doi, source_title, evidence_domain,
                       candidate_modality, suggested_evidence_grade
                FROM curation_queue
                WHERE evidence_domain IN ('toxicity', 'offtarget', 'chemistry',
                                          'delivery', 'assay', 'benchmark')
                ORDER BY id
                """
            )
        )
    finally:
        conn.close()


def fetch_pubmed_xml(pmids: list[str]) -> ElementTree.Element:
    if not pmids:
        return ElementTree.Element("PubmedArticleSet")
    query = urlencode({"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"})
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?{query}"
    with ncbi_open(url) as response:
        return ElementTree.fromstring(response.read())


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


def text_content(element: ElementTree.Element | None) -> str:
    if element is None:
        return ""
    return " ".join(part.strip() for part in element.itertext() if part and part.strip())


def sentence_split(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()]


def pubmed_records(pmids: list[str]) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    for start in range(0, len(pmids), 150):
        root = fetch_pubmed_xml(pmids[start : start + 150])
        for article in root.findall(".//PubmedArticle"):
            pmid = text_content(article.find(".//PMID"))
            title = text_content(article.find(".//ArticleTitle"))
            abstract_parts = [
                text_content(item)
                for item in article.findall(".//Abstract/AbstractText")
                if text_content(item)
            ]
            abstract = " ".join(abstract_parts)
            records[pmid] = {"title": title, "sentences": sentence_split(abstract)}
    return records


def matched_terms(text: str, domain: str) -> list[str]:
    lower = text.lower()
    return [term for term in KEYWORDS.get(domain, []) if term in lower]


def best_location(
    domain: str,
    title: str,
    sentences: list[str],
) -> tuple[str, list[str], str]:
    best_terms: list[str] = []
    best_location_label = "source title"
    best_source = title
    for index, sentence in enumerate(sentences, start=1):
        terms = matched_terms(sentence, domain)
        if len(terms) > len(best_terms):
            best_terms = terms
            best_location_label = f"PubMed abstract sentence {index}"
            best_source = sentence
    title_terms = matched_terms(title, domain)
    if len(title_terms) > len(best_terms):
        best_terms = title_terms
        best_location_label = "PubMed title"
        best_source = title
    return best_location_label, best_terms, best_source


def confidence_label(location: str, terms: list[str]) -> str:
    if location.startswith("PubMed abstract") and len(terms) >= 2:
        return "high_candidate"
    if terms:
        return "medium_candidate"
    return "low_candidate"


def candidate_signal(domain: str, terms: list[str], source_title: str) -> str:
    if terms:
        return (
            f"{domain} candidate; matched derived terms: {', '.join(terms)}; "
            f"source title: {source_title}"
        )
    return f"{domain} candidate from queue only; source title: {source_title}"


def build_candidates() -> list[dict[str, object]]:
    rows = queue_rows()
    pmids = sorted({str(row["pmid"]) for row in rows if row["pmid"]})
    records = pubmed_records(pmids)
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    output: list[dict[str, object]] = []

    for next_id, row in enumerate(rows, start=1):
        domain = str(row["evidence_domain"])
        if domain not in TARGET_DOMAINS:
            continue
        pmid = str(row["pmid"] or "")
        record = records.get(pmid, {})
        title = str(record.get("title") or row["source_title"] or "")
        sentences = list(record.get("sentences") or [])
        location, terms, _ = best_location(domain, title, sentences)
        if not pmid:
            location = "external source title"
        if not terms:
            terms = matched_terms(str(row["source_title"]), domain)
        output.append(
            {
                "id": next_id,
                "queue_id": row["id"],
                "source_document_id": row["source_document_id"],
                "pmid": pmid,
                "doi": row["doi"] or "",
                "evidence_domain": domain,
                "candidate_modality": row["candidate_modality"],
                "source_location": location,
                "matched_terms": ";".join(terms),
                "candidate_signal": candidate_signal(domain, terms, str(row["source_title"])),
                "suggested_evidence_grade": row["suggested_evidence_grade"],
                "confidence_label": confidence_label(location, terms),
                "extraction_method": "rule_based_pubmed_metadata_v1",
                "validation_status": "candidate_needs_curator_review",
                "curator_decision": "pending",
                "redistribution_level": "derived_annotations_only",
                "created_at": created_at,
            }
        )
    return output


def write_candidates(rows: list[dict[str, object]]) -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    CANDIDATE_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    if not rows:
        return
    with CANDIDATE_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def load_candidates(rows: list[dict[str, object]]) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM curation_candidate")
        if rows:
            columns = list(rows[0].keys())
            placeholders = ", ".join(["?"] * len(columns))
            conn.executemany(
                f"INSERT INTO curation_candidate ({', '.join(columns)}) VALUES ({placeholders})",
                [[row[column] for column in columns] for row in rows],
            )
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    rows = build_candidates()
    write_candidates(rows)
    load_candidates(rows)
    print(f"curation_candidate={len(rows)} generated={CANDIDATE_CSV}")


if __name__ == "__main__":
    main()
