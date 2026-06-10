from __future__ import annotations

import argparse
import csv
import json
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from http.client import IncompleteRead
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
ABSTRACT_CACHE = ROOT / "data" / "generated" / "pubmed_abstract_cache_batch011_offtarget_20k.json"
USER_AGENT = "OligoVigil-curation/0.11 (batch011; mailto:jie.ni@student.uibk.ac.at)"


@dataclass
class Context:
    location: str
    text: str
    article_type: str = ""


def compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


OLIGO_RE = re.compile(
    r"\b("
    r"siRNA|small interfering RNA|RNAi|shRNA|antisense oligonucleotide|antisense|ASO|gapmer|"
    r"oligonucleotide|oligodeoxynucleotide|ODN|morpholino|PMO|locked nucleic acid|LNA|"
    r"GalNAc|inclisiran|patisiran|vutrisiran|givosiran|lumasiran|fitusiran|olezarsen|"
    r"volanesorsen|tofersen|nusinersen|inotersen|bepirovirsen|pelacarsen|mipomersen|"
    r"eteplirsen|drisapersen|AAV-RNAi"
    r")\b",
    re.I,
)

BAD_SCOPE_RE = re.compile(
    r"\b("
    r"plant|plants|wheat|rice|maize|soybean|arabidopsis|tomato|crop|seedling|pollen|"
    r"brassica|vicia faba|faba bean|leafhopper|honey bee|honey bees|apis mellifera|"
    r"mollusk|mollusc|fungal|fungus|yeast|insect|mosquito|aedes|drosophila|aphid|beetle|"
    r"locust|nematode|worm|c\\. elegans|caenorhabditis|flatworm|schistosoma|fish|zebrafish|"
    r"xenopus|bacteri|biofilm|bacterial cells|helicobacter|escherichia|e\\. coli|"
    r"paramecium|chicken|avian|pesticidal|pesticide|food safety|HLA typing|PCR typing|"
    r"diagnostic|biosensor|primer|probe"
    r")\b",
    re.I,
)

REVIEW_RE = re.compile(
    r"\b(review|reviews|overview|systematic review|meta-analysis|perspective|commentary|"
    r"protocol|roadmap|recent advances|what have we learnt|lessons learned)\b",
    re.I,
)

METHOD_TOOL_RE = re.compile(
    r"\b("
    r"software|web server|database|algorithm|deep learning|machine learning|computational model|"
    r"prediction model|generator|suite|pipeline|benchmark|scoring system|classifier|platform"
    r")\b",
    re.I,
)

DELIVERY_ONLY_TITLE_RE = re.compile(
    r"\b("
    r"delivery|nanoparticle|nanoparticles|nanocomplex|conjugates|hydrogel|polymer|polymeric|"
    r"dendrimer|polymersome|liposome|PEI|GNRs|ionic liquid|surface modification|pharmacokinetics|"
    r"drug-drug interaction|CYP450|transporter"
    r")\b",
    re.I,
)

OFFTARGET_RE = re.compile(
    r"\b("
    r"off-target|off target|offtarget|seed-mediated|seed match|seed region|seed sequence|"
    r"miRNA-like|microRNA-like|mismatch|mismatched|partial complementarity|"
    r"partially complementary|unintended gene|unintended transcript|unintended silencing|"
    r"non-target gene|nontarget gene|non-target transcript|cross-reactivity|cross-reactive"
    r")\b",
    re.I,
)

OFFTARGET_OLIGO_WINDOW_RE = re.compile(
    r"(?:siRNA|small interfering RNA|RNAi|shRNA|ASO|antisense oligonucleotide|antisense|"
    r"gapmer|oligonucleotide|morpholino|PMO).{0,180}(?:off-target|off target|offtarget|"
    r"seed-mediated|seed match|mismatch|mismatched|unintended gene|unintended transcript|"
    r"non-target gene|nontarget gene|miRNA-like|microRNA-like)|"
    r"(?:off-target|off target|offtarget|seed-mediated|seed match|mismatch|mismatched|"
    r"unintended gene|unintended transcript|non-target gene|nontarget gene|miRNA-like|"
    r"microRNA-like).{0,180}(?:siRNA|small interfering RNA|RNAi|shRNA|ASO|"
    r"antisense oligonucleotide|antisense|gapmer|oligonucleotide|morpholino|PMO)",
    re.I,
)

TRANSCRIPTOME_OFFTARGET_RE = re.compile(
    r"(?:RNA-seq|RNA seq|transcriptome|microarray|global gene expression|gene expression profiling|"
    r"genome-wide).{0,180}(?:off-target|off target|unintended|non-target|nontarget|seed|mismatch)|"
    r"(?:off-target|off target|unintended|non-target|nontarget|seed|mismatch).{0,180}"
    r"(?:RNA-seq|RNA seq|transcriptome|microarray|global gene expression|gene expression profiling|"
    r"genome-wide)",
    re.I,
)

PRIMARY_RE = re.compile(
    r"\b("
    r"we |our |this study|evaluated|assessed|measured|tested|validated|observed|identified|"
    r"profiled|RNA-seq|transcriptome|microarray|luciferase|reporter|qPCR|cells?|mice|mouse|"
    r"patients?|clinical trial|phase [123]|in vivo|in vitro"
    r")\b",
    re.I,
)

OFFTARGET_RESULT_RE = re.compile(
    r"\b("
    r"evaluat|assess|measur|test|validat|observ|identif|profil|analyz|microarray|RNA-seq|"
    r"transcriptome|luciferase|reporter|qPCR|found|show|demonstrat|caus|induc|unexpected|"
    r"deregulat|suppress|reduce|reduced|minimiz|minimized|without off-target|off-target-free|"
    r"no off-target|mismatched target|seed region|seed-mediated"
    r")",
    re.I,
)

GENERIC_OBSTACLE_RE = re.compile(
    r"(?:hampered by|limited by|obstacle|challenge|barrier|poor delivery|poor accumulation).{0,120}"
    r"(?:off-target|off target)|"
    r"(?:off-target|off target).{0,80}(?:poor accumulation|poor circulation|delivery|barrier|"
    r"clinical application|challenging)",
    re.I,
)

COMPUTATIONAL_RE = re.compile(
    r"\b(in silico|software|algorithm|model|deep learning|machine learning|predict|prediction|"
    r"web server|database|benchmark|computational)\b",
    re.I,
)

WET_ASSAY_RE = re.compile(
    r"\b(RNA-seq|RNA seq|transcriptome|microarray|luciferase|reporter|qPCR|RT-qPCR|western blot|"
    r"cells?|mice|mouse|patients?|clinical|in vivo|in vitro)\b",
    re.I,
)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sentence_split(text: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", compact_text(text))
    return [piece for piece in pieces if len(piece) >= 20]


def parse_pubmed_articles(payload: str) -> dict[str, dict[str, str]]:
    root = ET.fromstring(payload)
    parsed: dict[str, dict[str, str]] = {}
    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//PMID")
        if pmid_el is None or not (pmid_el.text or "").strip():
            continue
        pmid = (pmid_el.text or "").strip()
        abstract_parts = []
        for abstract_text in article.findall(".//Abstract/AbstractText"):
            label = abstract_text.attrib.get("Label", "")
            text = compact_text("".join(abstract_text.itertext()))
            if text:
                abstract_parts.append(f"{label}: {text}" if label else text)
        pub_types = [
            compact_text("".join(item.itertext()))
            for item in article.findall(".//PublicationTypeList/PublicationType")
        ]
        parsed[pmid] = {
            "abstract": " ".join(abstract_parts),
            "publication_types": "; ".join(pub_types),
        }
    return parsed


def load_cache() -> dict[str, dict[str, str]]:
    if ABSTRACT_CACHE.exists():
        return json.loads(ABSTRACT_CACHE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict[str, dict[str, str]]) -> None:
    ABSTRACT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    ABSTRACT_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_pubmed_abstracts(pmids: list[str], cache: dict[str, dict[str, str]], limit: int = 0) -> None:
    missing = [pmid for pmid in sorted(set(pmids)) if pmid and pmid not in cache]
    if limit:
        missing = missing[:limit]
    for start in range(0, len(missing), 200):
        chunk = missing[start : start + 200]
        if not chunk:
            continue
        url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            f"?db=pubmed&id={','.join(chunk)}&retmode=xml"
        )
        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=60) as response:
                payload = response.read().decode("utf-8", errors="ignore")
            cache.update(parse_pubmed_articles(payload))
            for pmid in chunk:
                cache.setdefault(pmid, {"abstract": "", "publication_types": ""})
            save_cache(cache)
        except (HTTPError, URLError, TimeoutError, IncompleteRead, ET.ParseError):
            for pmid in chunk:
                cache.setdefault(pmid, {"abstract": "", "publication_types": ""})
        print(f"fetched_pubmed {min(start + len(chunk), len(missing))}/{len(missing)}", flush=True)
        time.sleep(0.25)


def contexts_for(row: dict[str, str], cache: dict[str, dict[str, str]]) -> list[Context]:
    data = cache.get((row.get("pmid") or "").strip(), {})
    abstract = data.get("abstract", "")
    contexts: list[Context] = []
    if abstract:
        for i, sentence in enumerate(sentence_split(abstract), start=1):
            contexts.append(
                Context(
                    location=f"PubMed abstract sentence {i}",
                    text=sentence,
                    article_type=data.get("publication_types", ""),
                )
            )
        contexts.append(
            Context(
                location="PubMed abstract",
                text=abstract,
                article_type=data.get("publication_types", ""),
            )
        )
    return contexts


def scope_reject(row: dict[str, str], contexts: list[Context]) -> str:
    title = row.get("title", "")
    context_text = " ".join(context.text for context in contexts[:4])
    scope_text = f"{title} {context_text}"
    article_types = " ".join(context.article_type for context in contexts)
    if REVIEW_RE.search(title) or re.search(r"\bReview\b", article_types, re.I):
        return "reject reason: review/background article, not primary off-target evidence"
    if BAD_SCOPE_RE.search(scope_text):
        return "reject reason: out-of-scope organism or non-therapeutic oligonucleotide context"
    if re.search(r"\bCRISPR|Cas9|Cas13|dCas13\b", scope_text, re.I) and not re.search(
        r"\bsiRNA|shRNA|ASO|antisense oligonucleotide|oligonucleotide therapeutic\b",
        scope_text,
        re.I,
    ):
        return "reject reason: non-oligonucleotide editing/silencing modality"
    if METHOD_TOOL_RE.search(title) and not re.search(
        r"therapeutic|clinical|patients?|mice|mouse|in vivo|GalNAc|ASO|siRNA therapeutic",
        title,
        re.I,
    ):
        return "reject reason: non-therapeutic oligonucleotide method/tool source"
    if DELIVERY_ONLY_TITLE_RE.search(title) and not re.search(
        r"off-target|off target|offtarget|specificity|mismatch|seed", title, re.I
    ):
        return "reject reason: delivery/PK source without title-level off-target assay"
    return ""


def context_score(context: Context) -> int:
    text = context.text
    score = 0
    if OFFTARGET_OLIGO_WINDOW_RE.search(text):
        score += 35
    elif OFFTARGET_RE.search(text):
        score += 25
    if TRANSCRIPTOME_OFFTARGET_RE.search(text):
        score += 18
    if OLIGO_RE.search(text):
        score += 10
    if PRIMARY_RE.search(text):
        score += 8
    if WET_ASSAY_RE.search(text):
        score += 6
    if COMPUTATIONAL_RE.search(text):
        score -= 3
    return score


def best_context(contexts: list[Context]) -> Context | None:
    relevant = [
        context
        for context in contexts
        if OFFTARGET_OLIGO_WINDOW_RE.search(context.text)
        or (
            TRANSCRIPTOME_OFFTARGET_RE.search(context.text)
            and re.search(r"\b(siRNA|shRNA|ASO|antisense|gapmer|oligonucleotide|RNAi)\b", context.text, re.I)
        )
    ]
    if not relevant:
        return None
    return max(relevant, key=context_score)


def infer_modality(row: dict[str, str], text: str) -> str:
    combined = f"{row.get('title', '')} {row.get('candidate_modality', '')} {text}"
    if re.search(r"\bPMO|morpholino|phosphorodiamidate", combined, re.I):
        return "PMO"
    if re.search(r"\bsiRNA|small interfering|RNAi|shRNA|AAV-RNAi", combined, re.I):
        return "siRNA"
    if re.search(r"\bantisense|ASO|gapmer|LNA", combined, re.I):
        return "ASO"
    if re.search(r"\boligonucleotide", combined, re.I):
        return "oligonucleotide"
    return row.get("candidate_modality") or "oligonucleotide"


def infer_molecule(row: dict[str, str], text: str, modality: str) -> str:
    existing = row.get("molecule_canonical_name") or row.get("molecule_name_proposed") or ""
    if existing:
        return existing
    combined = f"{row.get('title', '')} {text}"
    known = [
        "inclisiran",
        "patisiran",
        "vutrisiran",
        "givosiran",
        "lumasiran",
        "fitusiran",
        "olezarsen",
        "volanesorsen",
        "tofersen",
        "nusinersen",
        "inotersen",
        "bepirovirsen",
        "pelacarsen",
        "mipomersen",
    ]
    for token in known:
        if re.search(rf"\b{re.escape(token)}\b", combined, re.I):
            return token
    bad_molecule_tokens = {
        "sirna",
        "sirnas",
        "silencing",
        "signal",
        "significant",
        "situ",
        "site",
        "silico",
        "suggest aso",
        "the aso",
        "gapmer aso",
        "overlapping aso",
        "required aso",
        "selected aso",
        "on aso",
        "nt aso",
        "pe- sirna",
        "vs sirna",
    }
    patterns = [
        r"\bGalNAc-[A-Za-z0-9-]*si[A-Za-z0-9-]+\b",
        r"\bsi[A-Z0-9][A-Za-z0-9-]*\d[A-Za-z0-9-]*\b",
        r"\b[A-Z0-9]{2,}(?:-[A-Z0-9]+)*-siRNA\b",
        r"\b[A-Z0-9]{2,}(?:-[A-Z0-9]+)*-ASO\b",
        r"\b[A-Z][A-Z0-9-]{1,12} ASO\b",
        r"\b[A-Z0-9-]+-ASO\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, combined, re.I)
        if match:
            candidate = match.group(0)
            if candidate.lower() not in bad_molecule_tokens and re.search(r"\d|[A-Z]{2,}", candidate):
                return candidate
    target_match = re.search(
        r"\b(?:targeting|against|silencing|knockdown of)\s+([A-Z][A-Z0-9-]{1,12})\b",
        combined,
    )
    if target_match:
        return f"{target_match.group(1)} {modality}"
    return ""


def infer_offtarget(text: str) -> tuple[str, str, str]:
    seed = re.search(r"\b([67])-?mer seed\b|\bseed (?:match|region|sequence)\b|seed-mediated|miRNA-like|microRNA-like", text, re.I)
    if seed:
        return "seed-mediated off-target effect", "seed", seed.group(1) or ""
    if re.search(
        r"\bmismatch|mismatched|partial complementarity|partially complementary|cross-react",
        text,
        re.I,
    ):
        return "hybridization/mismatch off-target effect", "mismatch", ""
    if re.search(r"\bRNA-seq|RNA seq|transcriptome|microarray|global gene expression|genome-wide\b", text, re.I):
        return "transcriptome-level off-target effect", "transcriptome", ""
    return "off-target evidence", "off-target", ""


def infer_assay(text: str, computational: bool) -> str:
    if computational:
        return "computational off-target prediction"
    if re.search(r"\bRNA-seq|RNA seq|transcriptome\b", text, re.I):
        return "RNA-seq/transcriptome profiling"
    if re.search(r"\bmicroarray\b", text, re.I):
        return "microarray"
    if re.search(r"\bluciferase|reporter\b", text, re.I):
        return "luciferase reporter"
    if re.search(r"\bqPCR|RT-qPCR\b", text, re.I):
        return "qPCR"
    return "off-target assessment"


def infer_organism(text: str) -> str:
    if re.search(r"\bpatients?|participants?|human\b", text, re.I):
        return "human"
    if re.search(r"\bmonkey|macaque|non-human primate|NHP\b", text, re.I):
        return "non-human primate"
    if re.search(r"\brats?\b", text, re.I):
        return "rat"
    if re.search(r"\bmice|mouse|murine\b", text, re.I):
        return "mouse"
    if re.search(r"\bcells?|cell line|HepG2|HeLa|A549|HUVEC|fibroblast|hepatocyte\b", text, re.I):
        return "cell line"
    return ""


def grade_for(context: Context, text: str, computational: bool) -> str:
    if computational:
        return "C"
    if re.search(r"\bRNA-seq|RNA seq|transcriptome|microarray|luciferase|reporter|clinical|patients?|mice|in vivo\b", text, re.I):
        return "B"
    return "C"


def apply_reject(row: dict[str, str], reason: str) -> None:
    row["curator_decision"] = "reject"
    row["validation_status"] = "curator_rejected"
    row["source_location_verified"] = ""
    row["evidence_grade"] = ""
    row["benchmark_eligible_proposed"] = "false"
    row["audit_note"] = reason


def accept_or_reject(row: dict[str, str], context: Context | None, scope_reason: str) -> None:
    if scope_reason:
        apply_reject(row, scope_reason)
        return
    if context is None:
        apply_reject(row, "reject reason: source text lacks concrete off-target evidence")
        return
    text = compact_text(context.text)
    combined = f"{row.get('title', '')} {text}"
    if not OLIGO_RE.search(combined):
        apply_reject(row, "reject reason: no oligonucleotide modality linked to off-target evidence")
        return
    has_oligo_offtarget = bool(
        OFFTARGET_OLIGO_WINDOW_RE.search(text)
        or (
            TRANSCRIPTOME_OFFTARGET_RE.search(text)
            and re.search(r"\b(siRNA|shRNA|ASO|antisense|gapmer|oligonucleotide|RNAi)\b", text, re.I)
        )
    )
    if not has_oligo_offtarget:
        apply_reject(row, "reject reason: source location does not support specific off-target evidence")
        return
    if re.search(r"\boff[- ]target toxicit\w*\b|\boff[- ]target effect\w*\b", text, re.I) and re.search(
        r"\bsmall molecule|inhibitor|chemotherapy|drug therapy\b", text, re.I
    ):
        apply_reject(row, "reject reason: off-target claim is about non-oligonucleotide therapy")
        return
    if GENERIC_OBSTACLE_RE.search(text):
        apply_reject(row, "reject reason: off-target mention is a generic delivery/development obstacle")
        return
    if not OFFTARGET_RESULT_RE.search(text):
        apply_reject(row, "reject reason: abstract does not report an off-target result or assay")
        return
    if not PRIMARY_RE.search(text):
        apply_reject(row, "reject reason: off-target mention is not supported by primary analysis")
        return
    computational = bool(COMPUTATIONAL_RE.search(combined) and not WET_ASSAY_RE.search(text))
    if computational and METHOD_TOOL_RE.search(row.get("title", "")):
        apply_reject(row, "reject reason: generic computational method/tool without molecule-specific evidence")
        return
    modality = infer_modality(row, text)
    molecule = infer_molecule(row, text, modality)
    if not molecule:
        apply_reject(row, "reject reason: no explicit molecule, target, or cohort for verified release evidence")
        return
    evidence_type, match_type, seed_len = infer_offtarget(text)
    grade = grade_for(context, text, computational)

    row["curator_decision"] = "accept"
    row["validation_status"] = "curator_verified"
    row["verified_entity_table"] = "offtarget_evidence"
    row["evidence_type"] = evidence_type
    row["match_type"] = match_type
    row["seed_match_length"] = seed_len
    row["source_location_verified"] = context.location
    row["evidence_grade"] = grade
    row["modality_name"] = modality
    row["molecule_canonical_name"] = molecule
    row["assay_type"] = infer_assay(text, computational)
    row["organism"] = row.get("organism") or infer_organism(text)
    row["is_observed_experimental"] = "false" if computational else "true"
    row["is_computational_prediction"] = "true" if computational else "false"
    row["benchmark_eligible_proposed"] = "false"
    row["audit_note"] = (
        f"Verified PubMed abstract evidence at {context.location}: primary off-target support "
        f"for {evidence_type} in a molecule-specific oligonucleotide context."
    )


def curate(args: argparse.Namespace) -> None:
    fieldnames, rows = read_csv(args.input_csv)
    cache = load_cache()
    if args.fetch_pubmed:
        fetch_pubmed_abstracts([row.get("pmid", "") for row in rows], cache, args.pubmed_limit)

    output_fields = [field for field in fieldnames if field != "curator_id"]
    for col in [
        "curator_decision",
        "validation_status",
        "source_location_verified",
        "audit_note",
        "evidence_grade",
        "verified_entity_table",
        "evidence_type",
        "match_type",
        "seed_match_length",
        "molecule_canonical_name",
        "modality_name",
        "assay_type",
        "organism",
        "is_observed_experimental",
        "is_computational_prediction",
        "benchmark_eligible_proposed",
    ]:
        if col not in output_fields:
            output_fields.append(col)

    report_rows = []
    for i, row in enumerate(rows, start=1):
        row.pop("curator_id", None)
        for col in output_fields:
            row.setdefault(col, "")
        contexts = contexts_for(row, cache)
        scope_reason = scope_reject(row, contexts)
        context = best_context(contexts)
        accept_or_reject(row, context, scope_reason)
        report_rows.append(
            {
                "candidate_id": row.get("candidate_id", ""),
                "pmid": row.get("pmid", ""),
                "pmcid": row.get("pmcid", ""),
                "title": row.get("title", ""),
                "candidate_confidence_label": row.get("candidate_confidence_label", ""),
                "curator_decision": row.get("curator_decision", ""),
                "evidence_grade": row.get("evidence_grade", ""),
                "evidence_type": row.get("evidence_type", ""),
                "match_type": row.get("match_type", ""),
                "molecule_canonical_name": row.get("molecule_canonical_name", ""),
                "source_location_verified": row.get("source_location_verified", ""),
                "audit_note": row.get("audit_note", ""),
                "context_excerpt": compact_text(context.text)[:700] if context else "",
            }
        )
        if args.progress_every and i % args.progress_every == 0:
            print(f"curated {i}/{len(rows)}", flush=True)

    write_csv(args.output_csv, output_fields, rows)
    write_csv(args.report_csv, list(report_rows[0].keys()), report_rows)
    accepts = [row for row in rows if row.get("curator_decision") == "accept"]
    summary = {
        "batch": "release_scale_review_batch011_offtarget_20k",
        "curated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "rows": len(rows),
        "decision_counts": dict(Counter(row.get("curator_decision", "") for row in rows)),
        "confidence_decision_counts": {
            label: dict(
                Counter(
                    row.get("curator_decision", "")
                    for row in rows
                    if row.get("candidate_confidence_label") == label
                )
            )
            for label in sorted({row.get("candidate_confidence_label", "") for row in rows})
        },
        "accept_grade_counts": dict(Counter(row.get("evidence_grade", "") for row in accepts)),
        "accept_type_counts": dict(Counter(row.get("evidence_type", "") for row in accepts)),
        "benchmark_eligible_accepts": sum(
            1 for row in accepts if row.get("benchmark_eligible_proposed") == "true"
        ),
        "reject_reason_counts": dict(
            Counter(row.get("audit_note", "") for row in rows if row.get("curator_decision") == "reject")
        ),
        "policy": (
            "Strict abstract-level batch011 screen: no curator_id column; accepts require explicit "
            "off-target evidence plus a molecule/target/cohort and are not benchmark eligible without "
            "full-text verification."
        ),
    }
    args.summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--summary-json", type=Path, required=True)
    parser.add_argument("--report-csv", type=Path, required=True)
    parser.add_argument("--fetch-pubmed", action="store_true")
    parser.add_argument("--pubmed-limit", type=int, default=0)
    parser.add_argument("--progress-every", type=int, default=1000)
    curate(parser.parse_args())


if __name__ == "__main__":
    main()
