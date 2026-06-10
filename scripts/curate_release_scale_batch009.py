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

from build_verified_batch1_packet import compact_text, iter_text_anchors, pmcid_number


ROOT = Path(__file__).resolve().parents[1]
PMC_CACHE = ROOT / "data" / "generated" / "pmc_xml_cache"
ABSTRACT_CACHE = ROOT / "data" / "generated" / "pubmed_abstract_cache_batch009.json"
FALLBACK_ABSTRACT_CACHE = ROOT / "data" / "generated" / "pubmed_abstract_cache_batch003.json"
USER_AGENT = "OligoVigil-curation/0.9 (batch009; mailto:jie.ni@student.uibk.ac.at)"


@dataclass
class Context:
    location: str
    text: str
    source_kind: str
    article_type: str = ""
    anchor_hash: str = ""
    hash_exact: bool = False


OLIGO_RE = re.compile(
    r"\b("
    r"siRNA|small interfering RNA|RNAi|shRNA|antisense oligonucleotide|antisense|ASO|gapmer|"
    r"oligonucleotide|oligodeoxynucleotide|ODN|CpG|morpholino|PMO|phosphorodiamidate|"
    r"locked nucleic acid|LNA|GalNAc|inclisiran|patisiran|vutrisiran|givosiran|lumasiran|"
    r"fitusiran|olezarsen|volanesorsen|tofersen|nusinersen|inotersen|bepirovirsen|milasen|"
    r"elebsiran|pelacarsen|danvatirsen|mipomersen|eteplirsen|drisapersen"
    r")\b",
    re.I,
)

BAD_SCOPE_RE = re.compile(
    r"\b("
    r"wheat|soybean|rice|maize|cotton|arabidopsis|plant|plants|crop|crops|seedling|"
    r"tomato|tuta|spodoptera|bemisia|planthopper|pest|pests|sap-sucking|fungal|fungus|"
    r"insect|cockroach|drosophila|drosophilid|aphid|mosquito|honeybee|beetle|locust|"
    r"hyphantria|henosepilachna|eucryptorrhynchus|schistosoma|cryptosporidium|"
    r"nematode|worm|flatworm|planarian|zebrafish|xenopus|c\\. elegans|"
    r"caenorhabditis|duck|goose|chicken|livestock|bacteri|biofilm|Prevotella|"
    r"HLA typing|PCR typing|diagnostic|biosensor|sensor|food safety|metabolic engineering of soybean"
    r")\b",
    re.I,
)

REVIEW_RE = re.compile(
    r"\b(review|reviews|overview|meta-analysis|systematic review|perspective|commentary|protocol|"
    r"roadblocks|recent advances|delivery of therapeutic oligonucleotides|basic principles)\b",
    re.I,
)

NONTHERAPEUTIC_TITLE_RE = re.compile(
    r"\b("
    r"generator|suite|software|web server|database|algorithm|deep learning|machine learning|"
    r"in silico|computational study|computational design|bioinformat|probe|primer|typing|"
    r"diagnos|detection|biosensor|microarray|phosphoramidites"
    r")\b",
    re.I,
)

SAFETY_RE = re.compile(
    r"\b("
    r"safety|safe|tolerability|tolerated|well tolerated|adverse|toxicity|toxic|cytotoxicity|"
    r"cytotoxic|cell viability|viability|hemolysis|haemolysis|hemocompatibility|immunotoxicity|"
    r"immunogenicity|immune activation|cytokine|interferon|complement|platelet|thrombocytopenia|"
    r"ALT|AST|alanine transaminase|aspartate transaminase|bilirubin|TBIL|BUN|creatinine|Scr|"
    r"serum chemistry|blood chemistry|histology|histological|H&E|body weight|organ index|"
    r"pathology|pathological|mortality|DNA damage|genotoxicity|no observable adverse"
    r")\b",
    re.I,
)

STRONG_SAFETY_RESULT_RE = re.compile(
    r"("
    r"no significant (?:change|difference|cytotoxicity|toxicity)|no (?:observable )?adverse|"
    r"well tolerated|no signs? of toxicity|did not (?:affect|induce|cause)|"
    r"remained (?:stable|unchanged)|normal (?:ALT|AST|liver enzymes|serum)|"
    r"hemolysis rate|cell viability (?:was |remained |above)|viability (?:was |remained |above)|"
    r"platelet .*<|thrombocytopenia|ALT|AST|BUN|creatinine|histolog|H&E|body weight"
    r")",
    re.I,
)

PRIMARY_RE = re.compile(
    r"\b(we |our |this study|results?|methods?|treated|administered|measured|assessed|evaluated|"
    r"tested|observed|showed|demonstrated|quantified|phase [123]|clinical trial|patients?|mice|mouse|"
    r"rats?|monkeys?|cells?)\b",
    re.I,
)

EFFICACY_ONLY_RE = re.compile(
    r"\b("
    r"tumou?r growth|anti-?tumou?r|anticancer|cell death|apoptosis|proliferation|migration|"
    r"invasion|disease model|inflammation|fibrosis|injury|viral replication|knockdown protects|"
    r"ameliorates|attenuates|rescues|therapeutic efficacy|reduced cell viability|"
    r"decreased cell viability|impedes viability|inhibited cell viability|suppressed cell viability"
    r")\b",
    re.I,
)

OFFTARGET_RE = re.compile(
    r"\b("
    r"off-target|off target|offtarget|seed-mediated|seed region|seed match|seed sequence|"
    r"miRNA-like|microRNA-like|mismatch|mismatched|hybridization|partial complementarity|"
    r"partially complementary|unintended|non-target|nontarget|transcriptome|RNA-seq|RNA seq|"
    r"microarray|gene expression profiling|global expression|genome-wide|specificity|cross-react"
    r")\b",
    re.I,
)

OFFTARGET_EXPLICIT_RE = re.compile(
    r"\b("
    r"off-target|off target|offtarget|seed-mediated|seed match|seed region|seed sequence|"
    r"miRNA-like|microRNA-like|mismatch|mismatched|hybridization|partial complementarity|"
    r"partially complementary|unintended|non-target|nontarget|specificity|cross-react"
    r")\b",
    re.I,
)

OFFTARGET_CONCRETE_RE = re.compile(
    r"\b("
    r"off-target|off target|offtarget|seed-mediated|seed match|miRNA-like|microRNA-like|"
    r"mismatch|mismatched|hybridization|partial complementarity|partially complementary|"
    r"unintended gene|unintended transcript|non-target gene|nontarget gene|cross-react"
    r")\b",
    re.I,
)

OFFTARGET_STRONG_RE = re.compile(
    r"(off-target|off target|seed-mediated|seed match|mismatch|mismatched|hybridization|"
    r"transcriptome|RNA-seq|microarray|global gene expression|unintended gene|genome-wide)",
    re.I,
)

TRANSCRIPTOME_OFFTARGET_RE = re.compile(
    r"(?:RNA-seq|RNA seq|transcriptome|microarray|global gene expression|gene expression profiling|"
    r"genome-wide).{0,160}(?:off-target|off target|specificity|unintended|non-target|nontarget|"
    r"mismatch|seed|hybridization)|"
    r"(?:off-target|off target|specificity|unintended|non-target|nontarget|mismatch|seed|"
    r"hybridization).{0,160}(?:RNA-seq|RNA seq|transcriptome|microarray|global gene expression|"
    r"gene expression profiling|genome-wide)",
    re.I,
)

COMPUTATIONAL_RE = re.compile(
    r"\b(in silico|software|algorithm|model|deep learning|machine learning|predict|prediction|"
    r"design|designer|suite|tool|web server|database|benchmark)\b",
    re.I,
)

WET_ASSAY_RE = re.compile(
    r"\b(RNA-seq|transcriptome|microarray|luciferase|reporter|qPCR|RT-qPCR|western blot|"
    r"cell viability|CCK-8|MTT|LDH|flow cytometry|ELISA|histology|H&E|ALT|AST|clinical|patients?)\b",
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


def fetch_pmc_xml(pmcid: str, pause_seconds: float = 0.12) -> bool:
    pmc_num = pmcid_number(pmcid)
    if not pmc_num:
        return False
    PMC_CACHE.mkdir(parents=True, exist_ok=True)
    path = PMC_CACHE / f"PMC{pmc_num}.xml"
    if path.exists() and path.stat().st_size > 100:
        return True
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={pmc_num}&rettype=full&retmode=xml"
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8", errors="ignore")
    except (HTTPError, URLError, TimeoutError, IncompleteRead):
        return False
    path.write_text(payload, encoding="utf-8")
    if pause_seconds:
        time.sleep(pause_seconds)
    return path.stat().st_size > 100


def pmc_xml_path(pmcid: str) -> Path | None:
    number = pmcid_number(pmcid)
    if not number:
        return None
    path = PMC_CACHE / f"PMC{number}.xml"
    return path if path.exists() and path.stat().st_size > 100 else None


def load_xml_contexts(row: dict[str, str]) -> list[Context]:
    path = pmc_xml_path(row.get("pmcid", ""))
    if path is None:
        return []
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8", errors="ignore"))
    except ET.ParseError:
        return []
    article = root.find(".//article")
    article_type = article.attrib.get("article-type", "") if article is not None else ""
    target_hash = (row.get("source_anchor_hash") or "").strip()
    contexts: list[Context] = []
    for anchor in iter_text_anchors(root):
        contexts.append(
            Context(
                location=anchor["location"],
                text=anchor["text"],
                source_kind="pmc_full_text",
                article_type=article_type,
                anchor_hash=anchor["anchor_hash"],
                hash_exact=bool(target_hash and anchor["anchor_hash"] == target_hash),
            )
        )
    return contexts


def sentence_split(text: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", compact_text(text))
    return [piece for piece in pieces if len(piece) >= 20]


def load_abstract_cache() -> dict[str, dict[str, str]]:
    if ABSTRACT_CACHE.exists():
        return json.loads(ABSTRACT_CACHE.read_text(encoding="utf-8"))
    if FALLBACK_ABSTRACT_CACHE.exists():
        return json.loads(FALLBACK_ABSTRACT_CACHE.read_text(encoding="utf-8"))
    return {}


def save_abstract_cache(cache: dict[str, dict[str, str]]) -> None:
    ABSTRACT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    ABSTRACT_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


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
            if not text:
                continue
            abstract_parts.append(f"{label}: {text}" if label else text)
        publication_types = [
            compact_text("".join(item.itertext()))
            for item in article.findall(".//PublicationTypeList/PublicationType")
        ]
        parsed[pmid] = {
            "abstract": " ".join(abstract_parts),
            "publication_types": "; ".join(publication_types),
        }
    return parsed


def fetch_pubmed_abstracts(pmids: list[str], cache: dict[str, dict[str, str]]) -> None:
    missing = [pmid for pmid in sorted(set(pmids)) if pmid and pmid not in cache]
    for start in range(0, len(missing), 200):
        chunk = missing[start : start + 200]
        if not chunk:
            continue
        ids = ",".join(chunk)
        url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            f"?db=pubmed&id={ids}&retmode=xml"
        )
        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=45) as response:
                payload = response.read().decode("utf-8", errors="ignore")
            cache.update(parse_pubmed_articles(payload))
            save_abstract_cache(cache)
        except (HTTPError, URLError, TimeoutError, IncompleteRead, ET.ParseError):
            continue
        time.sleep(0.2)


def abstract_contexts(row: dict[str, str], cache: dict[str, dict[str, str]]) -> list[Context]:
    data = cache.get((row.get("pmid") or "").strip(), {})
    abstract = data.get("abstract", "")
    if not abstract:
        return []
    contexts = [
        Context(
            location=f"PubMed abstract sentence {i}",
            text=sentence,
            source_kind="pubmed_abstract",
            article_type=data.get("publication_types", ""),
        )
        for i, sentence in enumerate(sentence_split(abstract), start=1)
    ]
    contexts.append(
        Context(
            location="PubMed abstract",
            text=abstract,
            source_kind="pubmed_abstract",
            article_type=data.get("publication_types", ""),
        )
    )
    return contexts


def overlay_checkpoint(rows: list[dict[str, str]], checkpoint_rows: list[dict[str, str]]) -> None:
    by_id = {row["candidate_id"]: row for row in checkpoint_rows}
    overlay_cols = [
        "pmc_full_text_available",
        "fetch_status",
        "article_type",
        "pmc_license",
        "proposed_source_location",
        "source_anchor_hash",
        "machine_matched_terms",
        "candidate_source_location",
    ]
    for row in rows:
        checkpoint = by_id.get(row.get("candidate_id", ""))
        if not checkpoint:
            continue
        if checkpoint.get("source_anchor_hash"):
            for col in overlay_cols:
                row[col] = checkpoint.get(col, row.get(col, ""))
            row["risk_flags"] = re.sub(
                r"(?:^|; )no_machine_full_text_anchor(?:; |$)",
                "; ",
                row.get("risk_flags", ""),
            ).strip("; ")


def title_scope_reject(row: dict[str, str], contexts: list[Context]) -> str:
    title = row.get("title", "")
    scope_text = (
        f"{title} {row.get('candidate_modality', '')} {row.get('modality_name', '')} "
        f"{row.get('machine_matched_terms', '')}"
    )
    article_types = " ".join(context.article_type for context in contexts)
    if REVIEW_RE.search(title) or re.search(r"\bReview\b", article_types, flags=re.I):
        return "reject reason: review/background article, not primary release evidence"
    if BAD_SCOPE_RE.search(scope_text):
        return "reject reason: out-of-scope organism or non-therapeutic oligonucleotide context"
    if NONTHERAPEUTIC_TITLE_RE.search(title) and not re.search(
        r"\b(clinical|patients?|mice|mouse|rats?|monkeys?|in vivo|toxicity|hepatotoxicity|"
        r"safety|tolerability|off-target activit|off-target effect)\b",
        title,
        re.I,
    ):
        return "reject reason: non-therapeutic oligonucleotide method/tool source"
    if re.search(r"\bmRNA\b", title, re.I) and not re.search(r"\b(siRNA|ASO|antisense|CpG|oligonucleotide)\b", title, re.I):
        return "reject reason: mRNA-only source, not ASO/siRNA/oligonucleotide safety or off-target evidence"
    return ""


def context_bad_location(context: Context) -> bool:
    if context.source_kind == "pubmed_abstract":
        return False
    return bool(
        re.search(
            r"\bIntroduction\b|\bBackground\b|COMMENTARY|Key Summary Points|"
            r"Emerging therapeutic approaches|Therapeutic Perspective|Perspectives and Significance",
            context.location,
            flags=re.I,
        )
    )


def context_score(row: dict[str, str], context: Context) -> int:
    text = context.text
    score = 0
    if context.hash_exact:
        score += 20
    if context.source_kind == "pmc_full_text":
        score += 4
    if re.search(r"\bResults?\b|Figure|Fig\.|Table|Supplement|Methods?", context.location, re.I):
        score += 12
    if re.search(r"\bSafety|Toxicity|Cytotoxicity|Off-target|Off target|Specificity", context.location, re.I):
        score += 12
    if re.search(r"\bIntroduction\b", context.location, re.I):
        score -= 18
    if re.search(r"\bDiscussion\b|Conclusion", context.location, re.I):
        score -= 5
    if OLIGO_RE.search(text):
        score += 10
    if PRIMARY_RE.search(text):
        score += 5
    if row.get("evidence_domain") == "toxicity":
        score += 8 if SAFETY_RE.search(text) else 0
        score += 12 if STRONG_SAFETY_RESULT_RE.search(text) else 0
    else:
        score += 10 if OFFTARGET_RE.search(text) else 0
        score += 18 if OFFTARGET_CONCRETE_RE.search(text) else 0
        score += 12 if TRANSCRIPTOME_OFFTARGET_RE.search(text) else 0
        score += 5 if WET_ASSAY_RE.search(text) else 0
    return score


def best_context(row: dict[str, str], contexts: list[Context]) -> Context | None:
    if not contexts:
        return None
    domain = row.get("evidence_domain")
    if domain == "toxicity":
        relevant = [context for context in contexts if SAFETY_RE.search(context.text)]
    else:
        relevant = [
            context
            for context in contexts
            if OFFTARGET_CONCRETE_RE.search(context.text) or TRANSCRIPTOME_OFFTARGET_RE.search(context.text)
        ]
    candidates = relevant or contexts
    return max(candidates, key=lambda context: context_score(row, context))


def infer_modality(row: dict[str, str], text: str) -> str:
    combined = f"{row.get('title', '')} {row.get('candidate_modality', '')} {row.get('modality_name', '')} {text}"
    if re.search(r"\bCpG|ODN|oligodeoxynucleotide", combined, re.I):
        return "CpG oligodeoxynucleotide"
    if re.search(r"\bPMO|morpholino|phosphorodiamidate", combined, re.I):
        return "PMO"
    if re.search(r"\bsiRNA|small interfering|RNAi|shRNA", combined, re.I):
        return "siRNA"
    if re.search(r"\bantisense|ASO|gapmer|LNA", combined, re.I):
        return "ASO"
    existing = row.get("modality_name") or row.get("candidate_modality") or "oligonucleotide"
    return "ASO/siRNA mixed context" if existing == "ASO/siRNA" else existing


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
        "elebsiran",
        "ISIS 405879",
        "CpG ODN 1826",
        "CpG 1018",
    ]
    for token in known:
        if re.search(rf"\b{re.escape(token)}\b", combined, re.I):
            return token
    for pattern in [
        r"\bsi[A-Z0-9][A-Za-z0-9-]{1,20}\b",
        r"\b[A-Za-z0-9-]+-siRNA\b",
        r"\b[A-Za-z0-9-]+ ASO\b",
        r"\b[A-Z0-9-]+-ASO\b",
        r"\banti-miR-[0-9A-Za-z-]+\b",
        r"\b[A-Z]{2,}[0-9][A-Z0-9-]*\b",
    ]:
        match = re.search(pattern, combined, re.I)
        if match:
            return match.group(0)
    target = row.get("target_gene_symbol") or row.get("target_gene_symbol_proposed") or ""
    if target:
        return f"{target} {modality}"
    return f"unspecified {modality}"


def infer_endpoint(text: str) -> tuple[str, str]:
    if re.search(r"\bALT|AST|bilirubin|TBIL|liver|hepatic|hepatotoxic", text, re.I):
        return "hepatotoxicity", "hepatic"
    if re.search(r"\bkidney|renal|creatinine|BUN|Scr\b", text, re.I):
        return "renal safety", "renal"
    if re.search(r"\bplatelet|thrombocytopenia|hematolog", text, re.I):
        return "thrombocytopenia", "hematological"
    if re.search(r"\bimmune|immunogenicity|cytokine|interferon|complement|TLR|MCP-1", text, re.I):
        return "immune activation", "immunotoxicity"
    if re.search(r"\bDNA damage|genotoxic", text, re.I):
        return "DNA damage response", "genotoxicity"
    if re.search(r"\bcell viability|cytotoxic|hemolysis|haemolysis|hemocompat", text, re.I):
        return "cell viability/cytotoxicity", "general safety"
    if re.search(r"\badverse|tolerability|tolerated|well tolerated|safety|biocompat", text, re.I):
        return "systemic safety/tolerability", "general safety"
    return "toxicity", "general toxicity"


def infer_offtarget(text: str) -> tuple[str, str, str]:
    seed = re.search(r"\b([67])-?mer seed\b|\bseed (?:match|region|sequence)\b|seed-mediated|miRNA-like|microRNA-like", text, re.I)
    if seed:
        seed_len = seed.group(1) if seed.group(1) else ""
        return "seed-mediated off-target effect", "seed", seed_len
    if re.search(r"\bRNA-seq|RNA seq|transcriptome|microarray|global gene expression|gene expression profiling\b", text, re.I):
        return "transcriptome-level off-target effect", "transcriptome", ""
    if re.search(r"\bmismatch|mismatched|hybridization|partial complementarity|partially complementary|cross-react", text, re.I):
        return "hybridization/mismatch off-target effect", "mismatch", ""
    return "off-target evidence", "off-target", ""


def infer_assay(row: dict[str, str], text: str, context: Context) -> str:
    if row.get("evidence_domain") == "offtarget":
        if re.search(r"\bRNA-seq|RNA seq|transcriptome\b", text, re.I):
            return "RNA-seq/transcriptome profiling"
        if re.search(r"\bmicroarray\b", text, re.I):
            return "microarray"
        if re.search(r"\bluciferase|reporter\b", text, re.I):
            return "luciferase reporter"
        if COMPUTATIONAL_RE.search(f"{row.get('title', '')} {text}") and not WET_ASSAY_RE.search(text):
            return "computational off-target prediction"
        return "off-target assessment"
    if re.search(r"\bclinical|phase [123]|patients?\b", text, re.I):
        return "clinical safety assessment"
    if re.search(r"\bRNA-seq|transcriptome\b", text, re.I):
        return "RNA-seq"
    if re.search(r"\bMTT|CCK-8|CellTiter|cell viability\b", text, re.I):
        return "cell viability assay"
    if re.search(r"\bLDH\b", text, re.I):
        return "LDH cytotoxicity assay"
    if re.search(r"\bALT|AST|BUN|creatinine|serum|blood chemistry|histolog|H&E|body weight\b", text, re.I):
        return "in vivo toxicity"
    if re.search(r"\bhemolysis|haemolysis\b", text, re.I):
        return "hemolysis assay"
    return row.get("assay_type_proposed") or "experimental safety assessment"


def infer_organism(text: str) -> str:
    if re.search(r"\bpatients?|participants?|human\b", text, re.I):
        return "human"
    if re.search(r"\bmonkey|cynomolgus|macaque|non-human primate|NHP\b", text, re.I):
        return "non-human primate"
    if re.search(r"\brats?\b", text, re.I):
        return "rat"
    if re.search(r"\bmice|mouse|murine\b", text, re.I):
        return "mouse"
    if re.search(r"\bcells?|cell line|HepG2|HeLa|A549|HUVEC|PBMC|fibroblast|hepatocyte\b", text, re.I):
        return "cell line"
    return ""


def infer_tissue(text: str) -> str:
    for label, pattern in [
        ("liver", r"\bliver|hepatic|hepatocyte|HepG2|ALT|AST\b"),
        ("kidney", r"\bkidney|renal|BUN|creatinine|Scr\b"),
        ("blood/serum", r"\bserum|blood|platelet|PBMC\b"),
        ("lung", r"\blung|pulmonary|A549\b"),
        ("brain/CNS", r"\bbrain|CNS|neuron|glioma|microglia\b"),
        ("cell line", r"\bcells?|cell line|HeLa|HUVEC|fibroblast\b"),
    ]:
        if re.search(pattern, text, re.I):
            return label
    return ""


def infer_direction(text: str, domain: str) -> str:
    if re.search(r"\b(no significant|no observable|unchanged|remained stable|well tolerated|normal)\b", text, re.I):
        return "no significant change"
    if re.search(r"\bincreased|elevated|induced|higher|upregulated|thrombocytopenia|adverse\b", text, re.I):
        return "increased"
    if re.search(r"\bdecreased|reduced|lower|downregulated|minimized|attenuated\b", text, re.I):
        return "decreased"
    return ""


def grade_for(row: dict[str, str], context: Context, text: str, computational: bool = False) -> str:
    if computational:
        return "C"
    if context.source_kind == "pubmed_abstract":
        return "B" if re.search(r"\bclinical|phase|patients?|well tolerated|adverse|off-target\b", text, re.I) else "C"
    if re.search(r"\bIntroduction\b|\bDiscussion\b|Conclusion", context.location, re.I):
        return "C"
    if re.search(r"\bResults?\b|Figure|Fig\.|Table|Safety|Toxicity|Cytotoxicity|Off-target|Specificity", context.location, re.I):
        return "A"
    return "B"


def toxicity_decision(row: dict[str, str], context: Context) -> tuple[bool, str, str]:
    text = compact_text(context.text)
    combined = f"{row.get('title', '')} {text}"
    if not OLIGO_RE.search(combined):
        return False, "", "reject reason: no therapeutic oligonucleotide/siRNA/ASO safety modality supported by source context"
    if not SAFETY_RE.search(text):
        return False, "", "reject reason: source location does not contain a toxicity or safety endpoint"
    if context_bad_location(context) and not re.search(r"\bSafety|Toxicity|Cytotoxicity\b", context.location, re.I):
        return False, "", "reject reason: source support is introduction/background only"
    if EFFICACY_ONLY_RE.search(text) and not STRONG_SAFETY_RESULT_RE.search(text):
        return False, "", "reject reason: safety-like term is part of disease efficacy/cell-killing readout"
    if not (STRONG_SAFETY_RESULT_RE.search(text) or re.search(r"\bcytotoxicity|cell viability|hemolysis|adverse events?|well tolerated|blood chemistry|serum chemistry|histolog|H&E\b", text, re.I)):
        return False, "", "reject reason: safety endpoint is too generic or unsupported"
    grade = grade_for(row, context, text)
    return True, grade, ""


def offtarget_decision(row: dict[str, str], context: Context) -> tuple[bool, str, str, bool]:
    text = compact_text(context.text)
    combined = f"{row.get('title', '')} {text}"
    if not OLIGO_RE.search(combined):
        return False, "", "reject reason: no oligonucleotide modality linked to off-target evidence", False
    has_concrete_offtarget = bool(
        OFFTARGET_CONCRETE_RE.search(text) or TRANSCRIPTOME_OFFTARGET_RE.search(text)
    )
    if not has_concrete_offtarget:
        return False, "", "reject reason: source location does not support specific off-target evidence", False
    if context_bad_location(context):
        return False, "", "reject reason: source support is introduction/background only", False
    if re.search(r"\bDiscussion\b|Conclusion", context.location, re.I) and not re.search(
        r"off-target|off target|offtarget|seed|mismatch|hybridization", context.location, re.I
    ):
        return False, "", "reject reason: source location is discussion-only generic off-target support", False
    if re.search(r"\bMethods?\b|Materials", context.location, re.I) and not re.search(
        r"off-target|off target|offtarget|seed|mismatch|hybridization|RNA-seq|transcriptome",
        context.location,
        re.I,
    ):
        return False, "", "reject reason: methods source location is not an off-target assay result", False
    computational = bool(COMPUTATIONAL_RE.search(combined) and not WET_ASSAY_RE.search(text))
    if computational and not re.search(r"\b(off-target|seed|mismatch|hybridization|specificity)\b", text, re.I):
        return False, "", "reject reason: computational source lacks concrete off-target evidence", False
    if not (WET_ASSAY_RE.search(text) or computational or re.search(r"\bvalidated|evaluated|assessed|identified|profiled|screened\b", text, re.I)):
        return False, "", "reject reason: off-target mention is not supported by primary analysis", False
    grade = grade_for(row, context, text, computational=computational)
    return True, grade, "", computational


def apply_reject(row: dict[str, str], reason: str) -> None:
    row["curator_decision"] = "reject"
    row["validation_status"] = "curator_rejected"
    row["source_location_verified"] = ""
    row["evidence_grade"] = ""
    row["benchmark_eligible_proposed"] = "false"
    row["audit_note"] = reason


def apply_accept(row: dict[str, str], context: Context, grade: str, computational: bool = False) -> None:
    text = compact_text(context.text)
    row["curator_decision"] = "accept"
    row["validation_status"] = "curator_verified"
    row["source_location_verified"] = context.location
    row["evidence_grade"] = grade
    modality = infer_modality(row, text)
    row["modality_name"] = modality
    row["molecule_canonical_name"] = infer_molecule(row, text, modality)
    row["assay_type"] = infer_assay(row, text, context)
    row["organism"] = row.get("organism") or infer_organism(text)
    row["cell_line_or_tissue"] = row.get("cell_line_or_tissue") or infer_tissue(text)
    row["direction"] = row.get("direction") or infer_direction(text, row.get("evidence_domain", ""))
    row["significance_label"] = row.get("significance_label") or (
        "not significant" if row["direction"] == "no significant change" else ""
    )
    row["is_observed_experimental"] = "false" if computational else "true"
    row["is_computational_prediction"] = "true" if computational else "false"
    if row.get("evidence_domain") == "toxicity":
        endpoint, category = infer_endpoint(text)
        row["verified_entity_table"] = "toxicity_endpoint"
        row["endpoint_name"] = endpoint
        row["endpoint_category"] = category
        target = endpoint
    else:
        evidence_type, match_type, seed_len = infer_offtarget(text)
        row["verified_entity_table"] = "offtarget_evidence"
        row["evidence_type"] = evidence_type
        row["match_type"] = match_type
        row["seed_match_length"] = seed_len
        target = evidence_type
    row["benchmark_eligible_proposed"] = (
        "true"
        if grade in {"A", "B"} and context.source_kind == "pmc_full_text" and not computational
        and not re.search(r"\bIntroduction\b|\bDiscussion\b|Conclusion", context.location, re.I)
        else "false"
    )
    source_kind = "full text" if context.source_kind == "pmc_full_text" else "PubMed abstract"
    row["audit_note"] = (
        f"Verified {source_kind} evidence at {context.location}: primary "
        f"{row.get('evidence_domain')} support for {target} in an oligonucleotide context."
    )


def curate(args: argparse.Namespace) -> None:
    fieldnames, rows = read_csv(args.input_csv)
    _, checkpoint_rows = read_csv(args.checkpoint_csv) if args.checkpoint_csv else ([], [])
    if checkpoint_rows:
        overlay_checkpoint(rows, checkpoint_rows)

    if args.fetch_missing_pmc:
        unique_pmcids = sorted({row.get("pmcid", "") for row in rows if row.get("pmcid", "")})
        fetched = 0
        for pmcid in unique_pmcids:
            if pmc_xml_path(pmcid):
                continue
            if args.fetch_pmc_limit and fetched >= args.fetch_pmc_limit:
                break
            if fetch_pmc_xml(pmcid):
                fetched += 1

    abstract_cache = load_abstract_cache()
    fetch_pubmed_abstracts([row.get("pmid", "") for row in rows], abstract_cache)

    output_fields = [field for field in fieldnames if field != "curator_id"]
    for col in [
        "curator_decision",
        "validation_status",
        "source_location_verified",
        "audit_note",
        "evidence_grade",
        "verified_entity_table",
        "endpoint_name",
        "endpoint_category",
        "evidence_type",
        "match_type",
        "seed_match_length",
        "molecule_canonical_name",
        "modality_name",
        "assay_type",
        "organism",
        "cell_line_or_tissue",
        "direction",
        "significance_label",
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
        contexts = load_xml_contexts(row)
        contexts.extend(abstract_contexts(row, abstract_cache))
        scope_reason = title_scope_reject(row, contexts)
        context = best_context(row, contexts)
        if scope_reason:
            apply_reject(row, scope_reason)
        elif context is None:
            apply_reject(row, "reject reason: source text unavailable for curator verification")
        elif row.get("evidence_domain") == "toxicity":
            ok, grade, reason = toxicity_decision(row, context)
            apply_accept(row, context, grade) if ok else apply_reject(row, reason)
        else:
            ok, grade, reason, computational = offtarget_decision(row, context)
            apply_accept(row, context, grade, computational=computational) if ok else apply_reject(row, reason)
        report_rows.append(
            {
                "candidate_id": row.get("candidate_id", ""),
                "pmid": row.get("pmid", ""),
                "pmcid": row.get("pmcid", ""),
                "evidence_domain": row.get("evidence_domain", ""),
                "title": row.get("title", ""),
                "curator_decision": row.get("curator_decision", ""),
                "evidence_grade": row.get("evidence_grade", ""),
                "verified_entity_table": row.get("verified_entity_table", ""),
                "endpoint_name": row.get("endpoint_name", ""),
                "evidence_type": row.get("evidence_type", ""),
                "source_location_verified": row.get("source_location_verified", ""),
                "audit_note": row.get("audit_note", ""),
                "context_excerpt": compact_text(context.text)[:600] if context else "",
            }
        )
        if args.progress_every and i % args.progress_every == 0:
            print(f"curated {i}/{len(rows)}", flush=True)

    write_csv(args.output_csv, output_fields, rows)
    report_fields = list(report_rows[0].keys()) if report_rows else []
    write_csv(args.report_csv, report_fields, report_rows)

    accepts = [row for row in rows if row.get("curator_decision") == "accept"]
    summary = {
        "batch": "release_scale_review_batch009_mega_fast",
        "curated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "rows": len(rows),
        "decision_counts": dict(Counter(row.get("curator_decision", "") for row in rows)),
        "domain_decision_counts": {
            domain: dict(Counter(row.get("curator_decision", "") for row in rows if row.get("evidence_domain") == domain))
            for domain in sorted({row.get("evidence_domain", "") for row in rows})
        },
        "accept_grade_counts": dict(Counter(row.get("evidence_grade", "") for row in accepts)),
        "accept_domain_counts": dict(Counter(row.get("evidence_domain", "") for row in accepts)),
        "accept_source_counts": dict(
            Counter("full_text" if row.get("source_location_verified", "").lower() != "pubmed abstract" and not row.get("source_location_verified", "").startswith("PubMed abstract") else "pubmed_abstract" for row in accepts)
        ),
        "benchmark_eligible_accepts": sum(1 for row in accepts if row.get("benchmark_eligible_proposed") == "true"),
        "reject_reason_counts": dict(Counter(row.get("audit_note", "") for row in rows if row.get("curator_decision") == "reject")),
        "accepted_candidate_ids": sorted([row.get("candidate_id", "") for row in accepts], key=lambda value: int(value) if value.isdigit() else value),
        "policy": "Conservative batch009 mega review with checkpoint full-text anchors overlaid; no curator_id column is emitted.",
    }
    args.summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--checkpoint-csv", type=Path)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--summary-json", type=Path, required=True)
    parser.add_argument("--report-csv", type=Path, required=True)
    parser.add_argument("--fetch-missing-pmc", action="store_true")
    parser.add_argument("--fetch-pmc-limit", type=int, default=0)
    parser.add_argument("--progress-every", type=int, default=500)
    curate(parser.parse_args())


if __name__ == "__main__":
    main()
