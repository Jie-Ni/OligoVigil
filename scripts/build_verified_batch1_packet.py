from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from http.client import IncompleteRead
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "oligosafety.db"
GENERATED_DIR = ROOT / "data" / "generated"
DELIVERY_DIR = ROOT.parent / "04_delivery"
DEFAULT_CSV = GENERATED_DIR / "verified_release_batch1_prequest.csv"
DEFAULT_CARDS = DELIVERY_DIR / "VERIFIED_EVIDENCE_BATCH1_PRECURATION.md"
USER_AGENT = "OligoVigil-curation/0.2 (human-review-required; mailto:jie.ni@student.uibk.ac.at)"

OLIGO_TERMS = [
    "antisense oligonucleotide",
    "antisense",
    "oligonucleotide",
    "aso",
    "sirna",
    "small interfering rna",
    "rnai",
    "galnac",
    "gapmer",
    "phosphorothioate",
    "locked nucleic acid",
    "lna",
]

TOXICITY_TERMS = [
    "toxicity",
    "toxic",
    "hepatotoxicity",
    "neurotoxicity",
    "renal",
    "kidney",
    "liver",
    "adverse",
    "safety",
    "tolerability",
    "dna damage",
    "cytotoxicity",
    "thrombocytopenia",
    "immunogenicity",
    "complement",
]

OFFTARGET_TERMS = [
    "off-target",
    "off target",
    "seed",
    "unintended",
    "transcriptome",
    "mismatch",
    "hybridization",
    "silencing",
    "risc",
    "partially complementary",
]

EXPERIMENTAL_TERMS = [
    "rna-seq",
    "transcriptome",
    "rat",
    "mouse",
    "mice",
    "in vivo",
    "in vitro",
    "cell",
    "dose",
    "repeat-dose",
    "study",
    "assay",
    "figure",
    "table",
    "supplement",
]

REVIEW_TERMS = ["review", "guidance", "perspective", "systematic review", "meta-analysis"]

DRUG_OR_MOLECULE_PATTERNS = [
    r"\b[A-Z]{2,}[0-9][A-Z0-9-]*\b",
    r"\b[A-Z]?[a-z]{3,}(?:virsen|arsen|acarsen|ersen|siran|zarsen)\b",
    r"\bnusinersen\b",
    r"\bpelacarsen\b",
    r"\bbepirovirsen\b",
    r"\binclisiran\b",
    r"\bvutrisiran\b",
    r"\bpatisiran\b",
    r"\bfomivirsen\b",
]


@dataclass(frozen=True)
class Candidate:
    candidate_id: int
    queue_id: int
    source_document_id: int
    pmid: str
    pmcid: str
    doi: str
    evidence_domain: str
    candidate_modality: str
    source_location: str
    matched_terms: str
    candidate_signal: str
    suggested_evidence_grade: str
    title: str
    journal_or_agency: str
    publication_year: int | None
    source_url: str
    license_status: str
    reuse_category: str


def compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def has_any(text: str, terms: list[str]) -> bool:
    haystack = text.lower()
    return any(term.lower() in haystack for term in terms)


def matched_terms(text: str, terms: list[str]) -> list[str]:
    haystack = text.lower()
    return [term for term in terms if term.lower() in haystack]


def pmcid_number(pmcid: str) -> str:
    match = re.search(r"PMC(\d+)", pmcid or "")
    return match.group(1) if match else ""


def load_candidates(limit_per_domain: int) -> list[Candidate]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT c.id AS candidate_id, c.queue_id, c.source_document_id, c.pmid,
                   s.pmcid, c.doi, c.evidence_domain, c.candidate_modality,
                   c.source_location, c.matched_terms, c.candidate_signal,
                   c.suggested_evidence_grade, s.title, s.journal_or_agency,
                   s.publication_year, s.source_url, s.license_status, s.reuse_category
            FROM curation_candidate AS c
            JOIN source_document AS s ON s.id = c.source_document_id
            WHERE c.evidence_domain IN ('toxicity', 'offtarget')
              AND c.confidence_label = 'high_candidate'
              AND s.pmcid IS NOT NULL
              AND s.pmcid != ''
            ORDER BY c.evidence_domain,
                     CASE WHEN s.title LIKE '%oligonucleotide%' THEN 0
                          WHEN s.title LIKE '%siRNA%' THEN 0
                          WHEN s.title LIKE '%antisense%' THEN 0
                          ELSE 1 END,
                     COALESCE(s.publication_year, 0) DESC,
                     c.id
            """
        ).fetchall()
    finally:
        conn.close()

    selected: list[Candidate] = []
    counts = {"toxicity": 0, "offtarget": 0}
    seen_pmids_by_domain: set[tuple[str, str]] = set()
    for row in rows:
        domain = row["evidence_domain"]
        if counts[domain] >= limit_per_domain:
            continue
        title = row["title"] or ""
        signal = row["candidate_signal"] or ""
        if not has_any(f"{title} {signal}", OLIGO_TERMS):
            continue
        key = (domain, row["pmid"] or str(row["source_document_id"]))
        if key in seen_pmids_by_domain:
            continue
        seen_pmids_by_domain.add(key)
        counts[domain] += 1
        selected.append(Candidate(**dict(row)))
    return selected


def fetch_pmc_xml(pmcid: str, cache_dir: Path, pause_seconds: float) -> tuple[str, str]:
    pmc_num = pmcid_number(pmcid)
    if not pmc_num:
        return "", "missing_pmcid"
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"PMC{pmc_num}.xml"
    if path.exists() and path.stat().st_size > 100:
        return path.read_text(encoding="utf-8", errors="ignore"), "cache"

    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        f"?db=pmc&id={pmc_num}&rettype=full&retmode=xml"
    )
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=25) as response:
            payload = response.read().decode("utf-8", errors="ignore")
    except (HTTPError, URLError, TimeoutError, IncompleteRead) as exc:
        return "", f"fetch_failed:{type(exc).__name__}"
    path.write_text(payload, encoding="utf-8")
    if pause_seconds:
        time.sleep(pause_seconds)
    return payload, "fetched"


def article_meta(root: ET.Element) -> dict[str, str]:
    article = root.find(".//article")
    article_type = article.attrib.get("article-type", "") if article is not None else ""
    license_el = root.find(".//license")
    license_type = license_el.attrib.get("{http://www.w3.org/1999/xlink}href", "") if license_el is not None else ""
    if not license_type and license_el is not None:
        license_type = license_el.attrib.get("license-type", "")
    return {
        "article_type": article_type,
        "pmc_license": license_type,
    }


def element_label(element: ET.Element, section_stack: list[str], index: int) -> str:
    tag = element.tag.split("}")[-1]
    if tag == "caption":
        label = "caption"
    else:
        label = "paragraph"
    section = " > ".join([item for item in section_stack if item])
    if section:
        return f"{section}; {label} {index}"
    return f"article body; {label} {index}"


def iter_text_anchors(root: ET.Element) -> list[dict[str, str]]:
    anchors: list[dict[str, str]] = []
    counter = 0

    def walk(element: ET.Element, section_stack: list[str]) -> None:
        nonlocal counter
        tag = element.tag.split("}")[-1]
        if tag == "sec":
            title_el = element.find("title")
            title = compact_text("".join(title_el.itertext())) if title_el is not None else ""
            next_stack = [*section_stack, title] if title else section_stack
            for child in list(element):
                if child is not title_el:
                    walk(child, next_stack)
            return
        if tag in {"abstract", "body"}:
            for child in list(element):
                walk(child, section_stack)
            return
        if tag in {"p", "caption"}:
            text = compact_text("".join(element.itertext()))
            if len(text) >= 50:
                counter += 1
                anchors.append(
                    {
                        "location": element_label(element, section_stack, counter),
                        "text": text,
                        "anchor_hash": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
                    }
                )
            return
        if tag in {"fig", "table-wrap"}:
            label_el = element.find("label")
            label = compact_text("".join(label_el.itertext())) if label_el is not None else tag
            caption = element.find("caption")
            if caption is not None:
                text = compact_text("".join(caption.itertext()))
                if len(text) >= 30:
                    counter += 1
                    section = " > ".join([item for item in section_stack if item])
                    loc = f"{section}; {label} caption" if section else f"{label} caption"
                    anchors.append(
                        {
                            "location": loc,
                            "text": text,
                            "anchor_hash": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
                        }
                    )
            return
        for child in list(element):
            walk(child, section_stack)

    for abstract in root.findall(".//abstract"):
        walk(abstract, ["Abstract"])
    body = root.find(".//body")
    if body is not None:
        walk(body, [])
    return anchors


def score_anchor(candidate: Candidate, anchor: dict[str, str]) -> tuple[int, list[str], list[str]]:
    text = anchor["text"]
    domain_terms = TOXICITY_TERMS if candidate.evidence_domain == "toxicity" else OFFTARGET_TERMS
    domain_matches = matched_terms(text, domain_terms)
    oligo_matches = matched_terms(text, OLIGO_TERMS)
    experimental_matches = matched_terms(text, EXPERIMENTAL_TERMS)
    score = 0
    score += 6 * len(domain_matches)
    score += 3 * len(oligo_matches)
    score += 2 * len(experimental_matches)
    if "Abstract" not in anchor["location"]:
        score += 3
    else:
        score -= 8
    if re.search(r"\bIntroduction\b", anchor["location"], flags=re.I):
        score -= 5
    if re.search(r"\bDiscussion\b|\bConclusion", anchor["location"], flags=re.I):
        score -= 2
    if re.search(r"\bResults\b", anchor["location"], flags=re.I):
        score += 7
    if re.search(r"\b(Fig|Figure|Table|Supplement)", anchor["location"], flags=re.I):
        score += 8
    if has_any(text, ["significant", "reduced", "increased", "mitigated", "observed"]):
        score += 2
    return score, domain_matches, oligo_matches


def infer_endpoint(candidate: Candidate, text: str) -> tuple[str, str]:
    if candidate.evidence_domain == "offtarget":
        if has_any(text, ["seed"]):
            return "", "seed-mediated off-target effect"
        if has_any(text, ["transcriptome", "rna-seq"]):
            return "", "transcriptome-level off-target effect"
        if has_any(text, ["mismatch", "hybridization"]):
            return "", "hybridization/mismatch off-target effect"
        return "", "off-target evidence"

    lowered = text.lower()
    if "hepatotoxic" in lowered or "liver" in lowered:
        return "hepatotoxicity", "hepatic"
    if "neurotoxic" in lowered or "cns" in lowered or "neuron" in lowered:
        return "neurotoxicity", "neurological"
    if "renal" in lowered or "kidney" in lowered:
        return "renal safety", "renal"
    if "dna damage" in lowered:
        return "DNA damage response", "genotoxicity"
    if "thrombocytopenia" in lowered or "platelet" in lowered:
        return "thrombocytopenia", "hematological"
    if "immunogenicity" in lowered or "complement" in lowered or "tlr" in lowered:
        return "immune activation", "immunotoxicity"
    if "tolerability" in lowered or "adverse" in lowered or "safety" in lowered:
        return "safety/tolerability", "general safety"
    return "toxicity", "general toxicity"


def infer_grade(article_type: str, text: str) -> str:
    lowered = text.lower()
    if has_any(lowered, REVIEW_TERMS) or article_type in {"review-article"}:
        return "C"
    if has_any(lowered, EXPERIMENTAL_TERMS):
        return "B"
    return "C"


def infer_molecule_name(candidate: Candidate, text: str) -> str:
    merged = candidate.title
    found: list[str] = []
    for pattern in DRUG_OR_MOLECULE_PATTERNS:
        for match in re.findall(pattern, merged, flags=re.I):
            token = match if isinstance(match, str) else match[0]
            token = token.strip()
            if token and token.lower() not in {"rna", "dna", "risc", "aso", "sirna", "galnac"}:
                found.append(token)
    deduped: list[str] = []
    for token in found:
        key = token.lower()
        if key not in {item.lower() for item in deduped}:
            deduped.append(token)
    return "; ".join(deduped[:4])


def risk_flags(candidate: Candidate, article_type: str, anchor: dict[str, str], domain_matches: list[str]) -> list[str]:
    flags: list[str] = []
    if "Abstract" in anchor["location"]:
        flags.append("abstract_anchor_only")
    if re.search(r"\bIntroduction\b", anchor["location"], flags=re.I):
        flags.append("intro_anchor_needs_primary_result")
    if re.search(r"\bDiscussion\b|\bConclusion", anchor["location"], flags=re.I):
        flags.append("discussion_or_conclusion_anchor")
    if article_type in {"review-article"} or has_any(candidate.title, REVIEW_TERMS):
        flags.append("review_or_meta_analysis")
    if not domain_matches:
        flags.append("domain_term_weak")
    if candidate.evidence_domain == "toxicity" and "safety" in domain_matches and len(domain_matches) == 1:
        flags.append("broad_safety_only")
    if candidate.candidate_modality == "ASO/siRNA":
        flags.append("mixed_modality_needs_resolution")
    return flags


def build_record(candidate: Candidate, xml_text: str, fetch_status: str) -> dict[str, str]:
    base = {
        "candidate_id": str(candidate.candidate_id),
        "queue_id": str(candidate.queue_id),
        "source_document_id": str(candidate.source_document_id),
        "pmid": candidate.pmid,
        "pmcid": candidate.pmcid,
        "doi": candidate.doi,
        "title": candidate.title,
        "journal_or_agency": candidate.journal_or_agency,
        "publication_year": str(candidate.publication_year or ""),
        "source_url": candidate.source_url,
        "evidence_domain": candidate.evidence_domain,
        "candidate_modality": candidate.candidate_modality,
        "candidate_source_location": candidate.source_location,
        "candidate_matched_terms": candidate.matched_terms,
        "fetch_status": fetch_status,
        "article_type": "",
        "pmc_license": "",
        "proposed_source_location": "",
        "source_anchor_hash": "",
        "machine_matched_terms": "",
        "molecule_name_proposed": "",
        "molecule_id": "",
        "molecule_canonical_name": "",
        "modality_name": candidate.candidate_modality
        if candidate.candidate_modality != "ASO/siRNA"
        else "ASO/siRNA mixed context",
        "target_gene_symbol_proposed": "",
        "target_gene_symbol": "",
        "disease_context": "",
        "therapeutic_status": "",
        "external_ids": "{}",
        "verified_entity_table": "toxicity_endpoint"
        if candidate.evidence_domain == "toxicity"
        else "offtarget_evidence",
        "endpoint_name_proposed": "",
        "endpoint_name": "",
        "endpoint_category_proposed": "",
        "endpoint_category": "",
        "evidence_type_proposed": "",
        "evidence_type": "",
        "assay_type_proposed": "",
        "assay_type": "",
        "model_context_proposed": "",
        "model_context": "",
        "organism": "",
        "cell_line_or_tissue": "",
        "dose_value": "",
        "dose_unit": "",
        "exposure_time_value": "",
        "exposure_time_unit": "",
        "replicate_count": "",
        "assay_source_location": "",
        "measured_value_proposed": "",
        "measured_value": "",
        "measured_unit_proposed": "",
        "measured_unit": "",
        "direction_proposed": "",
        "direction": "",
        "significance_label_proposed": "",
        "significance_label": "",
        "offtarget_gene_symbol": "",
        "offtarget_transcript_id": "",
        "measured_effect": "",
        "effect_unit": "",
        "match_type": "",
        "seed_match_length": "",
        "is_observed_experimental": "1",
        "is_computational_prediction": "0",
        "evidence_grade_proposed": "",
        "evidence_grade": "",
        "source_location_verified": "",
        "benchmark_eligible_proposed": "false",
        "curator_decision": "pending_pi_review",
        "curator_id": "",
        "validation_status": "machine_extracted_needs_human_verification",
        "audit_note_proposed": "",
        "risk_flags": "",
    }
    if not xml_text:
        base["risk_flags"] = "xml_fetch_failed"
        base["audit_note_proposed"] = "PMC XML fetch failed; verify manually from source URL."
        return base

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        base["risk_flags"] = "xml_parse_failed"
        base["audit_note_proposed"] = "PMC XML parse failed; verify manually from source URL."
        return base

    meta = article_meta(root)
    base.update(meta)
    anchors = iter_text_anchors(root)
    scored: list[tuple[int, dict[str, str], list[str], list[str]]] = []
    for anchor in anchors:
        score, domain_matches, oligo_matches = score_anchor(candidate, anchor)
        if domain_matches and (oligo_matches or has_any(candidate.title, OLIGO_TERMS)):
            scored.append((score, anchor, domain_matches, oligo_matches))
    if not scored:
        base["risk_flags"] = "no_full_text_anchor_found"
        base["audit_note_proposed"] = "No strong full-text anchor found by machine scan; manual source review required."
        return base

    scored.sort(key=lambda item: item[0], reverse=True)
    _, anchor, domain_matches, oligo_matches = scored[0]
    endpoint_name, endpoint_category_or_type = infer_endpoint(candidate, anchor["text"])
    grade = infer_grade(meta["article_type"], anchor["text"])
    flags = risk_flags(candidate, meta["article_type"], anchor, domain_matches)
    all_terms = [*domain_matches, *oligo_matches]
    base["proposed_source_location"] = anchor["location"]
    base["source_location_verified"] = anchor["location"]
    base["source_anchor_hash"] = anchor["anchor_hash"]
    base["machine_matched_terms"] = "; ".join(dict.fromkeys(all_terms))
    base["molecule_name_proposed"] = infer_molecule_name(candidate, anchor["text"])
    base["evidence_grade_proposed"] = grade
    base["evidence_grade"] = grade
    base["benchmark_eligible_proposed"] = "true" if grade in {"A", "B"} and not flags else "false"
    base["assay_type_proposed"] = "full_text_experimental_context_needs_curator_resolution"
    if candidate.evidence_domain == "toxicity":
        base["endpoint_name_proposed"] = endpoint_name
        base["endpoint_name"] = endpoint_name
        base["endpoint_category_proposed"] = endpoint_category_or_type
        base["endpoint_category"] = endpoint_category_or_type
    else:
        base["evidence_type_proposed"] = endpoint_category_or_type
        base["evidence_type"] = endpoint_category_or_type
    base["risk_flags"] = "; ".join(flags) if flags else "none"
    base["audit_note_proposed"] = (
        "Machine pre-curation only. Human curator must verify source anchor, molecule identity, "
        "assay context, endpoint, and grade before promotion."
    )
    base["audit_note"] = base["audit_note_proposed"]
    return base


FIELDNAMES = [
    "candidate_id",
    "queue_id",
    "source_document_id",
    "pmid",
    "pmcid",
    "doi",
    "title",
    "journal_or_agency",
    "publication_year",
    "source_url",
    "evidence_domain",
    "candidate_modality",
    "candidate_source_location",
    "candidate_matched_terms",
    "fetch_status",
    "article_type",
    "pmc_license",
    "proposed_source_location",
    "source_anchor_hash",
    "machine_matched_terms",
    "molecule_name_proposed",
    "molecule_id",
    "molecule_canonical_name",
    "modality_name",
    "target_gene_symbol_proposed",
    "target_gene_symbol",
    "disease_context",
    "therapeutic_status",
    "external_ids",
    "verified_entity_table",
    "endpoint_name_proposed",
    "endpoint_name",
    "endpoint_category_proposed",
    "endpoint_category",
    "evidence_type_proposed",
    "evidence_type",
    "assay_type_proposed",
    "assay_type",
    "model_context_proposed",
    "model_context",
    "organism",
    "cell_line_or_tissue",
    "dose_value",
    "dose_unit",
    "exposure_time_value",
    "exposure_time_unit",
    "replicate_count",
    "assay_source_location",
    "measured_value_proposed",
    "measured_value",
    "measured_unit_proposed",
    "measured_unit",
    "direction_proposed",
    "direction",
    "significance_label_proposed",
    "significance_label",
    "offtarget_gene_symbol",
    "offtarget_transcript_id",
    "measured_effect",
    "effect_unit",
    "match_type",
    "seed_match_length",
    "is_observed_experimental",
    "is_computational_prediction",
    "evidence_grade_proposed",
    "evidence_grade",
    "source_location_verified",
    "benchmark_eligible_proposed",
    "curator_decision",
    "curator_id",
    "validation_status",
    "audit_note_proposed",
    "audit_note",
    "risk_flags",
]


def write_cards(records: list[dict[str, str]], path: Path, max_cards: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    accepted = [row for row in records if row["proposed_source_location"]]
    toxicity = sum(1 for row in accepted if row["evidence_domain"] == "toxicity")
    offtarget = sum(1 for row in accepted if row["evidence_domain"] == "offtarget")
    lines = [
        "# Verified Evidence Batch-1 Precuration Packet",
        "",
        "Status: machine pre-curation only; no row is curator-verified.",
        "",
        f"- candidate rows scanned: {len(records)}",
        f"- rows with machine full-text anchors: {len(accepted)}",
        f"- toxicity anchors: {toxicity}",
        f"- off-target anchors: {offtarget}",
        "",
        "## Human Review Rule",
        "",
        "A row may be promoted only after a human curator opens the source, verifies the proposed source location, resolves molecule/assay fields, and changes `curator_decision` to `accept` plus `validation_status` to `curator_verified`.",
        "",
        "## Review Cards",
        "",
    ]
    for index, row in enumerate(accepted[:max_cards], start=1):
        lines.extend(
            [
                f"### Card {index}: candidate {row['candidate_id']} / PMID {row['pmid']}",
                "",
                f"- domain: {row['evidence_domain']}",
                f"- title: {row['title']}",
                f"- source: {row['source_url']}",
                f"- proposed location: {row['proposed_source_location']}",
                f"- anchor hash: `{row['source_anchor_hash']}`",
                f"- matched terms: {row['machine_matched_terms']}",
                f"- proposed molecule: {row['molecule_name_proposed'] or 'needs curator resolution'}",
                f"- proposed endpoint/type: {row['endpoint_name_proposed'] or row['evidence_type_proposed']}",
                f"- proposed grade: {row['evidence_grade_proposed']}",
                f"- risk flags: {row['risk_flags']}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit-per-domain", type=int, default=80)
    parser.add_argument("--max-cards", type=int, default=80)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output-cards", type=Path, default=DEFAULT_CARDS)
    parser.add_argument("--pause-seconds", type=float, default=0.34)
    parser.add_argument("--cache-dir", type=Path, default=GENERATED_DIR / "pmc_xml_cache")
    args = parser.parse_args()

    candidates = load_candidates(args.limit_per_domain)
    records: list[dict[str, str]] = []
    for index, candidate in enumerate(candidates, start=1):
        xml_text, fetch_status = fetch_pmc_xml(candidate.pmcid, args.cache_dir, args.pause_seconds)
        record = build_record(candidate, xml_text, fetch_status)
        records.append(record)
        if index % 25 == 0:
            print(f"processed={index}/{len(candidates)}", file=sys.stderr)

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(records)
    write_cards(records, args.output_cards, args.max_cards)

    anchored = [row for row in records if row["proposed_source_location"]]
    tox = sum(1 for row in anchored if row["evidence_domain"] == "toxicity")
    off = sum(1 for row in anchored if row["evidence_domain"] == "offtarget")
    print(f"batch1_prequest_rows={len(records)} anchored_rows={len(anchored)} toxicity={tox} offtarget={off}")
    print(f"csv={args.output_csv}")
    print(f"cards={args.output_cards}")


if __name__ == "__main__":
    main()
