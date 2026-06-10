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
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from build_verified_batch1_packet import compact_text, iter_text_anchors, pmcid_number


ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = ROOT / "data" / "generated"
DELIVERY_DIR = ROOT.parent / "04_delivery"
DEFAULT_INPUT = DELIVERY_DIR / "release_scale_review_batch003_template.csv"
DEFAULT_OUTPUT = Path("C:/Users/Jie/Desktop/release_scale_review_batch003.csv")
DEFAULT_SUMMARY = Path("C:/Users/Jie/Desktop/release_scale_review_batch003_summary.json")
DEFAULT_REPORT = Path("C:/Users/Jie/Desktop/release_scale_batch003_decision_report.csv")
PMC_CACHE = GENERATED_DIR / "pmc_xml_cache"
PUBMED_ABSTRACT_CACHE = GENERATED_DIR / "pubmed_abstract_cache_batch003.json"
CURATOR_ID = "codex_assist_20260602"
USER_AGENT = "OligoVigil-curation/0.3 (batch003; mailto:jie.ni@student.uibk.ac.at)"


OLIGO_TERMS = [
    "antisense oligonucleotide",
    "antisense",
    "oligonucleotide",
    "ASOs",
    "ASO-based",
    "ASO-associated",
    "ASO therapeutics",
    "ASO drug",
    "gapmer",
    "sirna",
    "small interfering rna",
    "rnai",
    "rna interference",
    "galnac",
    "locked nucleic acid",
    "lna",
    "phosphorothioate",
    "morpholino oligomer",
    "morpholino oligo",
    "phosphorodiamidate morpholino",
    "pmo",
    "nanp",
    "dna origami",
    "aptamer",
    "nusinersen",
    "inotersen",
    "inclisiran",
    "patisiran",
    "vutrisiran",
    "givosiran",
    "lumasiran",
    "fitusiran",
    "volanesorsen",
    "olezarsen",
    "pelacarsen",
    "danvatirsen",
    "casimersen",
    "eteplirsen",
    "golodirsen",
    "viltolarsen",
    "tofersen",
    "bepirovirsen",
    "mipomersen",
    "fomivirsen",
    "drisapersen",
    "milasen",
    "SLN360",
    "SPC5001",
    "GTI-2040",
    "CDR132L",
]

THERAPEUTIC_OLIGO_TERMS = [
    "antisense oligonucleotide",
    "antisense",
    "ASOs",
    "ASO-based",
    "ASO-associated",
    "ASO therapeutics",
    "ASO drug",
    "gapmer",
    "sirna",
    "small interfering rna",
    "rnai therapeutic",
    "galnac",
    "locked nucleic acid",
    "lna",
    "phosphorothioate",
    "morpholino oligomer",
    "morpholino oligo",
    "phosphorodiamidate morpholino",
    "pmo",
    "nusinersen",
    "inotersen",
    "inclisiran",
    "patisiran",
    "vutrisiran",
    "givosiran",
    "lumasiran",
    "fitusiran",
    "volanesorsen",
    "olezarsen",
    "pelacarsen",
    "danvatirsen",
    "casimersen",
    "eteplirsen",
    "golodirsen",
    "viltolarsen",
    "tofersen",
    "bepirovirsen",
    "mipomersen",
    "fomivirsen",
    "drisapersen",
    "milasen",
    "SLN360",
    "SPC5001",
    "GTI-2040",
    "CDR132L",
]

SAFETY_TERMS = [
    "safety",
    "safe",
    "tolerability",
    "tolerated",
    "adverse",
    "toxicity",
    "toxic",
    "cytotoxicity",
    "cell viability",
    "viability",
    "hemolysis",
    "hemocompatibility",
    "immunotoxicity",
    "immunogenicity",
    "immune activation",
    "cytokine",
    "interferon",
    "complement",
    "tlr",
    "platelet",
    "thrombocytopenia",
    "liver",
    "hepatic",
    "hepatotoxicity",
    "alt",
    "ast",
    "kidney",
    "renal",
    "histology",
    "body weight",
    "mortality",
    "genotoxicity",
    "dna damage",
]

OFFTARGET_TERMS = [
    "off-target",
    "off target",
    "offtarget",
    "seed",
    "seed-mediated",
    "mismatch",
    "mismatched",
    "hybridization",
    "partially complementary",
    "transcriptome",
    "rna-seq",
    "microarray",
    "unintended",
    "non-target",
]

STRICT_OFFTARGET_TERMS = [
    "off-target",
    "off target",
    "offtarget",
    "seed-mediated",
    "6-mer seed",
    "6mer seed",
    "mismatch",
    "mismatched",
    "hybridization-dependent",
    "partially complementary",
    "unintended",
]

PRIMARY_TERMS = [
    "we observed",
    "we found",
    "we evaluated",
    "we investigated",
    "we tested",
    "we assessed",
    "we measured",
    "we administered",
    "we performed",
    "study showed",
    "results showed",
    "was well tolerated",
    "were well tolerated",
    "no adverse",
    "adverse events",
    "no toxicity",
    "no significant toxicity",
    "no signs of toxicity",
    "no indication",
    "cell viability",
    "hemolysis",
    "histology",
    "rna-seq",
    "luciferase",
    "reporter",
    "transcriptome",
    "microarray",
    "mice",
    "mouse",
    "rat",
    "rats",
    "patients",
    "phase",
    "clinical trial",
]

REVIEW_TERMS = [
    "review",
    "reviews",
    "overview",
    "systematic review",
    "systematic reviews",
    "meta-analysis",
    "guidance",
    "recommendation",
    "recommendations",
    "perspective",
    "commentary",
    "protocol",
    "methods in molecular biology",
]

BAD_SCOPE_TERMS = [
    "plant",
    "plants",
    "crop",
    "crops",
    "cotton",
    "rice",
    "wheat",
    "maize",
    "soybean",
    "rapeseed",
    "grapevine",
    "fungal",
    "fungus",
    "insect",
    "insects",
    "mosquito",
    "beetle",
    "honey bee",
    "drosophila",
    "plutella",
    "bemisia",
    "aphid",
    "pest",
    "rhodnius",
    "helicoverpa",
    "tribulium",
    "kosteletzkya",
    "foxtail millet",
    "anopheles",
    "heterodera",
    "periplaneta",
    "mikania",
    "duck",
    "c. elegans",
    "caenorhabditis",
    "nematode",
    "grapholita",
    "nilaparvata",
    "locusta",
    "pesticide",
    "food safety",
    "hla",
    "typing",
    "diagnostic",
    "diagnosis",
    "detection",
    "sensor",
    "biosensor",
    "biosensing",
    "probe",
    "probes",
    "fluorescence in situ",
    "assay for",
    "single-antigen bead",
    "pcr",
    "qpcr",
    "genotyping",
    "genome editing",
    "crispr",
    "aav",
    "shrna",
    "mirna scaffold",
    "artificial mirna delivered by aav",
    "mrna delivery",
    "mrna",
    "messenger rna",
    "polyphyllin",
    "cisplatin",
    "folic acid",
    "aromatase inhibitor",
    "statin",
    "natural product",
]

EXTERNAL_TOXIN_TERMS = [
    "alnps",
    "zno",
    "arsenite",
    "arsenic",
    "lead",
    "cadmium",
    "cry1ac",
    "triptolide",
    "chlorpyrifos",
    "organophosphorus",
    "pesticide",
    "amyloid beta",
    "lithocholic acid",
    "anit",
]

NON_OLIGO_DRUG_TERMS = [
    "risdiplam",
    "apitegromab",
    "belzutifan",
    "cilostazol",
    "paclitaxel",
    "trastuzumab",
    "doxorubicin",
]

EFFICACY_ONLY_TERMS = [
    "antitumor",
    "anti-tumor",
    "anticancer",
    "anti-cancer",
    "apoptosis",
    "proliferation",
    "migration",
    "invasion",
    "tumor growth",
    "cell death",
]

MOLECULE_PATTERNS = [
    r"\b[A-Z]{2,}[0-9][A-Z0-9-]*\b",
    r"\b[A-Za-z0-9-]+(?:virsen|arsen|acarsen|ersen|siran|zarsen)\b",
    r"\b(?:nusinersen|inotersen|volanesorsen|pelacarsen|danvatirsen|tofersen|inclisiran|vutrisiran|patisiran|givosiran|lumasiran|fitusiran|bepirovirsen|olezarsen|IONIS-[A-Z0-9-]+|SLN360|ION-682884|ISIS\\s?2302)\b",
]


@dataclass
class EvidenceContext:
    location: str
    text: str
    source_kind: str
    article_type: str = ""
    anchor_hash: str = ""
    hash_exact: bool = False


def term_re(term: str) -> re.Pattern[str]:
    escaped = re.escape(term)
    if re.fullmatch(r"[A-Za-z0-9]+", term):
        return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", flags=re.I)
    return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", flags=re.I)


def has_any(text: str, terms: list[str]) -> bool:
    return any(term_re(term).search(text) for term in terms)


def term_hits(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term_re(term).search(text)]


def sentence_split(text: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", compact_text(text))
    return [piece.strip() for piece in pieces if len(piece.strip()) >= 20]


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def pmc_xml_path(pmcid: str) -> Path | None:
    number = pmcid_number(pmcid)
    if not number:
        return None
    path = PMC_CACHE / f"PMC{number}.xml"
    return path if path.exists() and path.stat().st_size > 100 else None


def article_type_from_root(root: ET.Element) -> str:
    article = root.find(".//article")
    return article.attrib.get("article-type", "") if article is not None else ""


def load_xml_contexts(row: dict[str, str]) -> list[EvidenceContext]:
    path = pmc_xml_path(row.get("pmcid", ""))
    if path is None:
        return []
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8", errors="ignore"))
    except ET.ParseError:
        return []
    article_type = article_type_from_root(root)
    target_hash = (row.get("source_anchor_hash") or "").strip()
    contexts: list[EvidenceContext] = []
    for anchor in iter_text_anchors(root):
        contexts.append(
            EvidenceContext(
                location=anchor["location"],
                text=anchor["text"],
                source_kind="pmc_full_text",
                article_type=article_type,
                anchor_hash=anchor["anchor_hash"],
                hash_exact=bool(target_hash and anchor["anchor_hash"] == target_hash),
            )
        )
    return contexts


def load_abstract_cache(path: Path) -> dict[str, dict[str, str]]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_abstract_cache(path: Path, cache: dict[str, dict[str, str]]) -> None:
    path.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_pubmed_articles(payload: str) -> dict[str, dict[str, str]]:
    root = ET.fromstring(payload)
    parsed: dict[str, dict[str, str]] = {}
    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//MedlineCitation/PMID")
        if pmid_el is None or not pmid_el.text:
            continue
        pmid = pmid_el.text.strip()
        abstract_parts: list[str] = []
        for abstract_el in article.findall(".//Abstract/AbstractText"):
            label = abstract_el.attrib.get("Label", "").strip()
            text = compact_text("".join(abstract_el.itertext()))
            if not text:
                continue
            abstract_parts.append(f"{label}: {text}" if label else text)
        pub_types = [
            compact_text("".join(el.itertext()))
            for el in article.findall(".//PublicationTypeList/PublicationType")
        ]
        parsed[pmid] = {
            "abstract": " ".join(abstract_parts),
            "publication_types": "; ".join(pub_types),
        }
    return parsed


def fetch_pubmed_abstracts(pmids: list[str], cache_path: Path, pause_seconds: float = 0.35) -> dict[str, dict[str, str]]:
    cache = load_abstract_cache(cache_path)
    missing = [pmid for pmid in sorted(set(pmids)) if pmid and pmid not in cache]
    for offset in range(0, len(missing), 100):
        chunk = missing[offset : offset + 100]
        if not chunk:
            continue
        query = urlencode({"db": "pubmed", "id": ",".join(chunk), "retmode": "xml"})
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?{query}"
        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=35) as response:
                payload = response.read().decode("utf-8", errors="ignore")
            cache.update(parse_pubmed_articles(payload))
            for pmid in chunk:
                cache.setdefault(pmid, {"abstract": "", "publication_types": ""})
            save_abstract_cache(cache_path, cache)
            time.sleep(pause_seconds)
        except (HTTPError, URLError, TimeoutError, IncompleteRead, ET.ParseError) as exc:
            for pmid in chunk:
                cache.setdefault(pmid, {"abstract": "", "publication_types": f"fetch_failed:{type(exc).__name__}"})
            save_abstract_cache(cache_path, cache)
    return cache


def abstract_contexts(row: dict[str, str], abstract_cache: dict[str, dict[str, str]]) -> list[EvidenceContext]:
    pmid = row.get("pmid", "").strip()
    data = abstract_cache.get(pmid, {})
    abstract = data.get("abstract", "")
    if not abstract:
        return []
    contexts: list[EvidenceContext] = []
    for i, sentence in enumerate(sentence_split(abstract), start=1):
        contexts.append(
            EvidenceContext(
                location=f"PubMed abstract sentence {i}",
                text=sentence,
                source_kind="pubmed_abstract",
                article_type=data.get("publication_types", ""),
            )
        )
    contexts.append(
        EvidenceContext(
            location="PubMed abstract",
            text=abstract,
            source_kind="pubmed_abstract",
            article_type=data.get("publication_types", ""),
        )
    )
    return contexts


def context_score(row: dict[str, str], context: EvidenceContext) -> int:
    text = context.text
    score = 0
    oligo_hits = term_hits(text, OLIGO_TERMS)
    primary_hits = term_hits(text, PRIMARY_TERMS)
    score += 5 * len(oligo_hits)
    score += 2 * len(primary_hits)
    if row["evidence_domain"] == "toxicity":
        score += 6 * len(term_hits(text, SAFETY_TERMS))
    else:
        score += 8 * len(term_hits(text, OFFTARGET_TERMS))
    if context.hash_exact:
        score += 10
    if re.search(r"\bResults?\b|Figure|Fig\.|Table|Supplement", context.location, flags=re.I):
        score += 12
    if re.search(r"\bAbstract\b", context.location, flags=re.I):
        score += 2
    if re.search(r"\bIntroduction\b", context.location, flags=re.I):
        score -= 10
    if re.search(r"\bDiscussion\b|\bConclusion", context.location, flags=re.I):
        score -= 5
    if has_any(text, REVIEW_TERMS):
        score -= 8
    return score


def best_context(row: dict[str, str], contexts: list[EvidenceContext]) -> EvidenceContext | None:
    if not contexts:
        return None
    exact = [context for context in contexts if context.hash_exact]
    if exact:
        strongest = sorted(contexts, key=lambda item: context_score(row, item), reverse=True)[0]
        exact_is_intro = re.search(r"\bIntroduction\b", exact[0].location, flags=re.I)
        strongest_is_intro = re.search(r"\bIntroduction\b", strongest.location, flags=re.I)
        if exact_is_intro and not strongest_is_intro and context_score(row, strongest) > 0:
            return strongest
        if context_score(row, strongest) >= context_score(row, exact[0]) + 12:
            return strongest
        return exact[0]
    return sorted(contexts, key=lambda item: context_score(row, item), reverse=True)[0]


def title_scope_reject_reason(title: str) -> str:
    if re.search(r"\b(probiotic|probiotics|Lactiplantibacillus|Lactobacillus|kimchi|virulence factor|toxin-encoding genes?)\b", title, flags=re.I):
        return "reject reason: probiotic/genome safety study, not therapeutic oligonucleotide evidence"
    if re.search(r"\baptamer\b", title, flags=re.I) and re.search(
        r"\b(hydrogels?|nanoparticles?|nanosystems?|nanocarriers?|chitosan|photothermal|camptothecin|palladium|gold|biosensors?|sensors?|theranostic|imaging)\b",
        title,
        flags=re.I,
    ):
        return "reject reason: aptamer material/drug-delivery safety, not core ASO/siRNA therapeutic oligo evidence"
    if re.search(r"\bmRNA-based therapy\b|\bmRNA delivery\b", title, flags=re.I):
        return "reject reason: mRNA delivery context, not ASO/siRNA/off-target evidence"
    if re.search(r"\bplatelet depletion method\b", title, flags=re.I):
        return "reject reason: oligo used as experimental depletion tool, not safety evidence"
    if re.search(r"c\.\s*elegans|caenorhabditis|nematode", title, flags=re.I):
        return "reject reason: agricultural/plant/insect/non-therapeutic RNAi context"
    if re.search(r"\b(theranostic|light controlled imaging|imaging)\b", title, flags=re.I) and not has_any(title, ["safety", "toxicity", "toxicology", "tolerability", "adverse"]):
        return "reject reason: imaging/theranostic delivery study, not primary safety/off-target evidence"
    if re.search(r"\b(spectral|fluorescence|time-resolved fluorescence|exciton)\b", title, flags=re.I) and not has_any(title, ["toxicity", "safety", "tolerability", "adverse"]):
        return "reject reason: physicochemical/fluorescence assay, not primary safety/off-target evidence"
    if re.search(r"\bASO\b.{0,60}\b(femoral|popliteal|arter(?:y|ies)|arteriosclerosis|obliterans)\b", title, flags=re.I):
        return "reject reason: ASO is vascular disease abbreviation, not antisense oligonucleotide"
    if re.search(r"\b(systematic reviews?|meta-analysis|overview of systematic|risk assessment strategy|points to consider|safe starting dose|industry perspective)\b", title, flags=re.I):
        return "reject reason: review/guidance/protocol rather than primary safety/off-target evidence"
    if re.search(r"\b(lead-caused|unknown waters|effect-directed monitoring)\b", title, flags=re.I):
        return "reject reason: environmental/diagnostic toxicity assay, not therapeutic oligo safety evidence"
    if re.search(r"\b(assay|monitoring|quantification|biosensing|sensor|probe|probes|fluorescence in situ)\b", title, flags=re.I) and not has_any(title, ["therapeutic", "therapy", "delivery", "safety", "toxicity", "toxicological"]):
        return "reject reason: diagnostic or assay-development article, not therapeutic oligo safety evidence"
    if has_any(title, BAD_SCOPE_TERMS):
        if has_any(title, ["plant", "plants", "crop", "crops", "cotton", "rice", "wheat", "maize", "soybean", "rapeseed", "grapevine", "fungal", "fungus", "insect", "insects", "mosquito", "beetle", "honey bee", "drosophila", "plutella", "bemisia", "aphid", "pest", "pesticide", "food safety"]):
            return "reject reason: agricultural/plant/insect/non-therapeutic RNAi context"
        if has_any(title, ["diagnostic", "diagnosis", "detection", "sensor", "biosensor", "hla", "typing", "pcr", "genotyping", "single-antigen bead"]):
            return "reject reason: diagnostic or assay-development article, not therapeutic oligo safety evidence"
        if has_any(title, ["crispr", "genome editing", "aav", "shrna", "mirna scaffold"]):
            return "reject reason: viral/gene-editing/shRNA modality outside core therapeutic oligo evidence"
        if has_any(title, ["polyphyllin", "cisplatin", "folic acid", "aromatase inhibitor", "statin", "natural product"]):
            return "reject reason: toxicity endpoint belongs to non-oligonucleotide drug or exposure"
        if has_any(title, ["mrna", "messenger rna"]):
            return "reject reason: mRNA delivery context, not ASO/siRNA/off-target evidence"
        return "reject reason: out-of-scope modality or source context"
    if has_any(title, REVIEW_TERMS):
        return "reject reason: review/guidance/protocol rather than primary safety/off-target evidence"
    return ""


def article_reject_reason(row: dict[str, str], context: EvidenceContext | None) -> str:
    article_type = ((context.article_type if context else row.get("article_type", "")) or "").lower()
    title = row.get("title", "")
    if has_any(title, ["risdiplam", "onasemnogene", "apitegromab"]) and not re.search(r"\bnusinersen\b", title, flags=re.I):
        return "reject reason: safety endpoint belongs to non-oligonucleotide therapeutic"
    if has_any(title, ["risdiplam", "onasemnogene"]) and re.search(r"\b(safety concerns|safety of risdiplam|after short-term treatment)\b", title, flags=re.I):
        return "reject reason: mixed SMA therapy safety is not oligo-specific"
    if has_any(title, ["paclitaxel", "doxorubicin", "trastuzumab"]) and re.search(r"\b(co-delivery|targeted delivery|delivery)\b", title, flags=re.I) and not has_any(title, ["toxicology", "toxicological", "toxicity study", "toxicokinetics", "safety"]):
        return "reject reason: chemotherapy co-delivery/efficacy study, not oligo safety evidence"
    if has_any(title, NON_OLIGO_DRUG_TERMS) and not has_any(title, OLIGO_TERMS):
        return "reject reason: safety endpoint belongs to non-oligonucleotide therapeutic"
    if re.search(r"\b(antisense noncoding|antisense non-coding|lncRNA|long noncoding|long non-coding)\b", title, flags=re.I) and not has_any(title, ["oligonucleotide", "ASOs", "ASO-based", "siRNA"]):
        return "reject reason: endogenous antisense/lncRNA biology, not therapeutic oligo evidence"
    if re.search(r"\b(promotes?|regulates?|mediates?|axis|signature|biomarker|prognostic|knockdown of|senescence|hub genes|renal denervation|dipyridamole|qingshen|NUAK1)\b", title, flags=re.I) and not has_any(title, OLIGO_TERMS):
        return "reject reason: disease-mechanism study using RNA perturbation, not oligo safety evidence"
    if article_type in {"review-article", "systematic-review"}:
        return "reject reason: review or systematic review, not primary evidence"
    if "review" in article_type or "meta-analysis" in article_type:
        return "reject reason: review/meta-analysis, not primary evidence"
    if "comment" in article_type or "correction" in article_type:
        return "reject reason: commentary/correction, not primary evidence"
    return title_scope_reject_reason(title)


def is_primary_context(text: str) -> bool:
    return has_any(text, PRIMARY_TERMS) or bool(re.search(r"\b(no|not|well|safe|tolerated|increased|decreased|significant|observed|measured|assessed|evaluated|administered)\b", text, flags=re.I))


def oligo_supported(row: dict[str, str], text: str) -> bool:
    combined = f"{row.get('title', '')} {text}"
    return has_any(combined, OLIGO_TERMS)


def therapeutic_oligo_supported(row: dict[str, str], text: str) -> bool:
    combined = f"{row.get('title', '')} {text}"
    return has_any(combined, THERAPEUTIC_OLIGO_TERMS)


def safety_supported(text: str) -> bool:
    return has_any(text, SAFETY_TERMS)


def offtarget_supported(text: str) -> bool:
    if has_any(text, STRICT_OFFTARGET_TERMS):
        return True
    lowered = text.lower()
    return "seed" in lowered and has_any(text, ["sirna", "small interfering rna", "mirna", "microRNA"])


def title_has_direct_safety(row: dict[str, str]) -> bool:
    title = row.get("title", "")
    if re.search(r"\b(suppress(?:es)?|attenuat(?:e|ed|es)|neutralize[sd]?|protects?|ameliorat(?:e|ed|es)|improves?)\b.{0,80}\b(neurotoxicity|toxicity|toxic RNA|injury|damage)\b", title, flags=re.I):
        if not has_any(title, ["safety", "tolerability", "toxicology", "toxicological", "toxicokinetics", "adverse", "cytotoxicity"]):
            return False
    return oligo_supported(row, "") and has_any(
        title,
        [
            "safety",
            "tolerability",
            "toxicology",
            "toxicological",
            "toxicity",
            "toxicokinetics",
            "cytotoxicity",
            "hemolysis",
            "biodistribution",
            "adverse",
        ],
    )


def explicit_safety_result(text: str) -> bool:
    patterns = [
        r"\b(no|not|without|low|lower|minimal|negligible|acceptable|favorable|favourable|excellent|improved|reduced|limited|non[- ]?toxic|biocompatible|well tolerated)\b.{0,90}\b(toxicity|cytotoxicity|toxic|adverse|hemolysis|haemolysis|immunogenicity|safety|tolerability|tolerated|biocompatibility)\b",
        r"\b(toxicity|cytotoxicity|toxic|adverse|hemolysis|haemolysis|immunogenicity|safety|tolerability|tolerated|biocompatibility)\b.{0,90}\b(no|not|without|low|lower|minimal|negligible|acceptable|favorable|favourable|excellent|improved|reduced|limited|non[- ]?toxic|biocompatible|well tolerated)\b",
        r"\b(safety|tolerability|toxicology|toxicokinetics|adverse event|adverse events|platelet count|complement activation|hepatic safety|renal safety)\b.{0,130}\b(evaluated|assessed|reported|observed|measured|profile|study|trial|phase|patients|mice|monkeys|rats)\b",
        r"\b(evaluated|assessed|reported|observed|measured)\b.{0,130}\b(safety|tolerability|toxicology|toxicokinetics|adverse event|adverse events|platelet count|complement activation|hepatic safety|renal safety)\b",
    ]
    return any(re.search(pattern, text, flags=re.I) for pattern in patterns)


def linked_safety_to_oligo(row: dict[str, str], text: str) -> bool:
    oligo_or_product = (
        r"(?:antisense oligonucleotide|oligonucleotide|ASO|gapmer|siRNA|small interfering RNA|"
        r"RNAi therapeutic|GalNAc|LNP|lipid nanoparticle|nanoparticle|nanocomplex|polyplex|"
        r"liposome|carrier|delivery vector|aptamer|NANP|DNA origami)"
    )
    safety = (
        r"(?:safety|safe|tolerab|adverse|toxicity|toxic|cytotoxicity|viability|hemolysis|"
        r"hemocompatibility|immunogenicity|immunotoxicity|cytokine|interferon|complement|"
        r"platelet|thrombocytopenia|ALT|AST|histology|body weight|mortality|renal|kidney|liver)"
    )
    combined = compact_text(f"{row.get('title', '')}. {text}")
    if re.search(oligo_or_product + r".{0,120}" + safety, combined, flags=re.I):
        return True
    if re.search(safety + r".{0,120}" + oligo_or_product, combined, flags=re.I):
        return True
    if title_has_direct_safety(row):
        return True
    return False


def toxicity_is_tool_or_external_exposure(row: dict[str, str], text: str) -> bool:
    if title_has_direct_safety(row):
        return False
    combined = compact_text(f"{row.get('title', '')}. {text}")
    title = row.get("title", "")
    if has_any(combined, EXTERNAL_TOXIN_TERMS) and not title_has_direct_safety(row):
        return True
    if re.search(r"\b(knockdown|silencing|inhibition|downregulation|down-regulation|attenuat(?:e|ed|es)|protects? against|mediates?|suppress(?:es)?)\b.{0,100}\b(neurotoxicity|toxicity|toxic|injury|damage|inflammation|fibrosis)\b", combined, flags=re.I):
        if not has_any(title, ["safety", "tolerability", "toxicology", "toxicokinetics", "adverse"]):
            return True
    if re.search(r"\b(neurotoxicity|toxicity|toxic|injury|damage|inflammation|fibrosis)\b.{0,100}\b(knockdown|silencing|inhibition|downregulation|down-regulation|attenuat(?:e|ed|es)|protects?|suppress(?:es)?)\b", combined, flags=re.I):
        if not has_any(title, ["safety", "tolerability", "toxicology", "toxicokinetics", "adverse"]):
            return True
    return False


def efficacy_only_reject(row: dict[str, str], text: str) -> bool:
    combined = f"{row.get('title', '')} {text}"
    lowered = combined.lower()
    if not has_any(combined, EFFICACY_ONLY_TERMS):
        return False
    if has_any(combined, ["normal cell", "healthy", "hemolysis", "hemocompatibility", "adverse", "safety", "tolerability", "off-target", "off target", "no observable organ toxicity", "no toxicity", "low toxicity", "no cytotoxicity", "well tolerated", "toxicokinetics"]):
        return False
    if row.get("evidence_domain") == "offtarget":
        return not has_any(combined, STRICT_OFFTARGET_TERMS)
    return "cytotoxic" in lowered or "toxicity" in lowered or "cell viability" in lowered or "off-target toxicity" in lowered


def context_scope_reject_reason(row: dict[str, str], text: str) -> str:
    combined = f"{row.get('title', '')} {text}"
    if re.search(r"\b(probiotic|probiotics|Lactiplantibacillus|Lactobacillus|kimchi|virulence factor|toxin-encoding genes?)\b", combined, flags=re.I):
        return "reject reason: probiotic/genome safety study, not therapeutic oligonucleotide evidence"
    if re.search(r"\baptamer\b", combined, flags=re.I) and re.search(
        r"\b(hydrogels?|nanoparticles?|nanosystems?|nanocarriers?|chitosan|photothermal|camptothecin|palladium|gold|biosensors?|sensors?|theranostic|imaging)\b",
        combined,
        flags=re.I,
    ):
        return "reject reason: aptamer material/drug-delivery safety, not core ASO/siRNA therapeutic oligo evidence"
    if row.get("evidence_domain") == "offtarget":
        if re.search(r"\b(in this review|we review|systematically discuss|future directions|resources, methods)\b", combined, flags=re.I):
            return "reject reason: review/guidance/protocol rather than primary safety/off-target evidence"
        if re.search(r"\b(computational approach|computational approaches|in silico|machine learning|deep learning|algorithm|predict(?:ing|ion)?|designing siRNA|designed \d+ siRNAs)\b", combined, flags=re.I):
            return "reject reason: computational/design-only off-target prediction without observed evidence"
        if re.search(r"\b(nanomachine|nanodevice|targeting precision|interaction specificity|targeted delivery system|delivery system|nanobubbles|nanocarrier)\b", combined, flags=re.I):
            if not has_any(combined, ["seed-mediated", "mismatch", "unintended transcript", "unintended transcripts", "transcriptome-wide"]):
                return "reject reason: delivery/efficacy specificity rather than oligo off-target evidence"
        if re.search(r"\b(lychee|polyphenol|mycobacterium|tuberculosis|atherosclerosis)\b", combined, flags=re.I):
            return "reject reason: disease-mechanism study using RNA perturbation, not oligo safety evidence"
        if re.search(r"\b(cancer|melanoma|tumou?r|glioma|carcinoma|metastasis|immunotherapy)\b", combined, flags=re.I) and not has_any(combined, ["off-target", "off target", "offtarget", "mismatch", "seed-mediated", "unintended transcript", "unintended transcripts", "transcriptome-wide"]):
            return "reject reason: delivery/efficacy specificity rather than oligo off-target evidence"
    if re.search(r"\bmRNA-based therapy\b|\bmRNA delivery\b", combined, flags=re.I) and not has_any(combined, ["siRNA", "small interfering RNA", "antisense oligonucleotide", "ASOs"]):
        return "reject reason: mRNA delivery context, not ASO/siRNA/off-target evidence"
    if has_any(combined, ["plant", "plants", "crop", "crops", "cotton", "rice", "wheat", "maize", "soybean", "rapeseed", "grapevine", "fungal", "fungus", "insect", "insects", "mosquito", "beetle", "honey bee", "drosophila", "plutella", "bemisia", "aphid", "pest", "pesticide", "rhodnius", "helicoverpa", "tribulium", "grapholita", "nilaparvata", "locusta", "kosteletzkya", "foxtail millet", "anopheles", "heterodera", "periplaneta", "mikania", "duck", "c. elegans", "caenorhabditis", "nematode"]):
        if not has_any(row.get("title", ""), ["nusinersen", "inotersen", "inclisiran", "patisiran", "vutrisiran", "givosiran", "lumasiran", "fitusiran", "volanesorsen", "olezarsen", "pelacarsen", "danvatirsen", "casimersen", "eteplirsen", "golodirsen", "viltolarsen", "tofersen", "bepirovirsen", "SLN360", "SPC5001", "GTI-2040"]):
            return "reject reason: agricultural/plant/insect/non-therapeutic RNAi context"
    return ""


def accept_decision(row: dict[str, str], context: EvidenceContext | None) -> tuple[str, str, str]:
    if context is None:
        return "reject", "reject reason: source location unsupported; no full-text anchor or PubMed abstract evidence", "C"

    text = context.text
    scope_reason = article_reject_reason(row, context)
    if scope_reason:
        return "reject", scope_reason, "C"
    context_scope_reason = context_scope_reject_reason(row, text)
    if context_scope_reason:
        return "reject", context_scope_reason, "C"
    if not oligo_supported(row, text):
        return "reject", "reject reason: no ASO/siRNA/oligonucleotide molecule support in source text", "C"
    if not is_primary_context(text):
        return "reject", "reject reason: source text is background/narrative rather than primary result", "C"
    if context.source_kind == "pmc_full_text" and re.search(r"\bIntroduction\b", context.location, flags=re.I):
        return "reject", "reject reason: introduction/background anchor without primary safety/off-target result", "C"
    if efficacy_only_reject(row, text):
        return "reject", "reject reason: cytotoxicity appears to be efficacy/cancer-killing readout, not safety evidence", "C"

    if row["evidence_domain"] == "toxicity":
        if not safety_supported(text):
            return "reject", "reject reason: no primary safety/toxicity endpoint in verified source text", "C"
        if context.source_kind == "pubmed_abstract" and not title_has_direct_safety(row) and not explicit_safety_result(text):
            return "reject", "reject reason: PubMed abstract does not report a direct oligo/product safety result", "C"
        if toxicity_is_tool_or_external_exposure(row, text):
            return "reject", "reject reason: toxicity belongs to disease/toxin model where oligo is a perturbation tool", "C"
        if not linked_safety_to_oligo(row, text):
            return "reject", "reject reason: safety/toxicity endpoint is not linked to the oligo molecule or delivery product", "C"
        if context.source_kind == "pubmed_abstract":
            grade = "B" if therapeutic_oligo_supported(row, text) and has_any(text, ["phase", "patients", "clinical trial", "adverse events", "well tolerated"]) else "C"
        elif therapeutic_oligo_supported(row, text) and re.search(r"\bResults?\b|Figure|Fig\.|Table|Supplement", context.location, flags=re.I):
            grade = "A"
        elif therapeutic_oligo_supported(row, text):
            grade = "B"
        else:
            grade = "C"
        return "accept", "accept", grade

    if not offtarget_supported(text):
        return "reject", "reject reason: no off-target/seed/mismatch/transcriptome evidence in verified source text", "C"
    if context.source_kind == "pubmed_abstract":
        grade = "B" if therapeutic_oligo_supported(row, text) and has_any(text, ["rna-seq", "transcriptome", "seed", "off-target", "off target"]) else "C"
    elif therapeutic_oligo_supported(row, text) and re.search(r"\bResults?\b|Figure|Fig\.|Table|Supplement", context.location, flags=re.I):
        grade = "A"
    elif therapeutic_oligo_supported(row, text):
        grade = "B"
    else:
        grade = "C"
    return "accept", "accept", grade


def infer_endpoint(text: str) -> tuple[str, str]:
    lowered = text.lower()
    if re.search(r"\b(alt|ast|alanine transaminase|aspartate transaminase|liver|hepatic|hepatotoxic)\b", lowered):
        return "hepatotoxicity", "hepatic"
    if re.search(r"\b(kidney|renal|creatinine|bun)\b", lowered):
        return "renal safety", "renal"
    if re.search(r"\b(platelet|thrombocytopenia|hematolog)", lowered):
        return "thrombocytopenia", "hematological"
    if re.search(r"\b(immune|immunogenicity|cytokine|interferon|complement|tlr)\b", lowered):
        return "immune activation", "immunotoxicity"
    if re.search(r"\b(dna damage|genotoxic)", lowered):
        return "DNA damage response", "genotoxicity"
    if re.search(r"\b(neuro|cns|neuron)", lowered):
        return "neurotoxicity", "neurological"
    if re.search(r"\b(cell viability|cytotoxic|hemolysis|haemolysis|hemocompatibility)\b", lowered):
        return "cell viability/cytotoxicity", "general safety"
    if re.search(r"\b(adverse|tolerability|safety|tolerated|well tolerated)\b", lowered):
        return "safety/tolerability", "general safety"
    return "toxicity", "general toxicity"


def infer_offtarget_type(text: str) -> tuple[str, str, str]:
    lowered = text.lower()
    if "seed" in lowered:
        return "seed-mediated off-target effect", "seed", ""
    if "rna-seq" in lowered or "transcriptome" in lowered or "microarray" in lowered:
        return "transcriptome-level off-target effect", "transcriptome", ""
    if "mismatch" in lowered or "hybridization" in lowered or "partially complementary" in lowered:
        return "hybridization/mismatch off-target effect", "mismatch", ""
    return "off-target evidence", "off-target", ""


def infer_modality(row: dict[str, str], text: str) -> str:
    combined = f"{row.get('title', '')} {row.get('molecule_name_proposed', '')} {text}".lower()
    if "sirna" in combined or "small interfering" in combined:
        return "siRNA"
    if "pmoplus" in combined:
        return "PMOplus"
    if "antisense" in combined or " aso" in f" {combined}" or "gapmer" in combined:
        return "ASO"
    if "morpholino" in combined or "pmo" in combined:
        return "ASO"
    if "aptamer" in combined:
        return "aptamer"
    if "dna origami" in combined or "nanp" in combined:
        return "DNA nanostructure"
    modality = row.get("modality_name") or row.get("candidate_modality") or "ASO/siRNA mixed context"
    return "ASO/siRNA mixed context" if modality == "ASO/siRNA" else modality


def infer_molecule(row: dict[str, str], text: str) -> str:
    existing = row.get("molecule_canonical_name") or row.get("molecule_name_proposed") or ""
    if existing:
        return existing
    combined = f"{row.get('title', '')} {text}"
    known_names = {
        "inclisiran": "Inclisiran",
        "nusinersen": "Nusinersen",
        "inotersen": "Inotersen",
        "patisiran": "Patisiran",
        "vutrisiran": "Vutrisiran",
        "givosiran": "Givosiran",
        "lumasiran": "Lumasiran",
        "fitusiran": "Fitusiran",
        "tofersen": "Tofersen",
    }
    for token, canonical in known_names.items():
        if re.search(rf"\b{re.escape(token)}\b", combined, flags=re.I):
            return canonical
    if re.search(r"\bAVI-6002\b", combined, flags=re.I) and re.search(r"\bAVI-6003\b", combined, flags=re.I):
        return "AVI-6002/AVI-6003 PMOplus"
    found: list[str] = []
    for pattern in MOLECULE_PATTERNS:
        for match in re.findall(pattern, combined, flags=re.I):
            token = match if isinstance(match, str) else match[0]
            token = token.strip(" ;,().")
            if not token:
                continue
            if token.lower() in {"rna", "dna", "aso", "sirna", "rnai", "alt", "ast", "pcr", "hla"}:
                continue
            found.append(token)
    deduped: list[str] = []
    seen: set[str] = set()
    for token in found:
        key = token.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(token)
    if deduped:
        return "; ".join(deduped[:3])
    modality = infer_modality(row, text)
    if modality == "siRNA":
        return "unspecified siRNA"
    if modality == "ASO":
        return "unspecified antisense oligonucleotide"
    if modality == "aptamer":
        return "unspecified aptamer"
    if modality == "DNA nanostructure":
        return "wireframe DNA origami NANP"
    return "unspecified oligonucleotide"


def infer_assay(text: str, grade: str) -> str:
    lowered = text.lower()
    if "rna-seq" in lowered or "transcriptome" in lowered:
        return "RNA-seq"
    if "luciferase" in lowered or "reporter" in lowered:
        return "luciferase reporter"
    if "phase" in lowered or "patients" in lowered or "clinical trial" in lowered or "adverse events" in lowered:
        return "clinical safety assessment"
    if "mice" in lowered or "mouse" in lowered or "rat" in lowered or "in vivo" in lowered:
        return "in vivo toxicity"
    if "cell viability" in lowered or "cytotoxic" in lowered:
        return "cell viability"
    if "hemolysis" in lowered:
        return "hemolysis assay"
    return "primary safety assessment" if grade in {"A", "B"} else "source-level safety evidence"


def infer_organism(text: str) -> str:
    lowered = text.lower()
    if "patients" in lowered or "human" in lowered or "healthy volunteer" in lowered:
        return "human"
    if "mice" in lowered or "mouse" in lowered:
        return "mouse"
    if "rats" in lowered or "rat" in lowered:
        return "rat"
    if "cell" in lowered or "cells" in lowered:
        return "cell line"
    return ""


def infer_direction(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ["no adverse", "no significant", "no signs", "no indication", "well tolerated", "safe", "low toxicity", "minimal toxicity", "did not"]):
        return "no significant change"
    if any(term in lowered for term in ["increased", "elevated", "induced", "activated"]):
        return "increased"
    if any(term in lowered for term in ["decreased", "reduced", "lowered"]):
        return "decreased"
    return ""


def infer_significance(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ["no significant", "not significant"]):
        return "not significant"
    if "significant" in lowered or "p <" in lowered or "p<" in lowered:
        return "significant"
    return ""


def benchmark_eligible(grade: str, context: EvidenceContext) -> str:
    if grade not in {"A", "B"}:
        return "false"
    if context.source_kind != "pmc_full_text":
        return "false"
    if re.search(r"\bIntroduction\b|\bDiscussion\b|\bConclusion", context.location, flags=re.I):
        return "false"
    return "true"


def apply_accept(row: dict[str, str], context: EvidenceContext, grade: str) -> None:
    text = context.text
    row["curator_decision"] = "accept"
    row["validation_status"] = "curator_verified"
    row["curator_id"] = CURATOR_ID
    row["source_location_verified"] = context.location
    row["evidence_grade"] = grade
    row["molecule_canonical_name"] = infer_molecule(row, text)
    row["modality_name"] = infer_modality(row, text)
    row["assay_type"] = infer_assay(text, grade)
    row["organism"] = row.get("organism") or infer_organism(text)
    row["direction"] = row.get("direction") or infer_direction(text)
    row["significance_label"] = row.get("significance_label") or infer_significance(text)
    row["benchmark_eligible_proposed"] = benchmark_eligible(grade, context)
    if row["evidence_domain"] == "toxicity":
        endpoint, category = infer_endpoint(text)
        row["verified_entity_table"] = "toxicity_endpoint"
        row["endpoint_name"] = endpoint
        row["endpoint_category"] = category
    else:
        evidence_type, match_type, seed_len = infer_offtarget_type(text)
        row["verified_entity_table"] = "offtarget_evidence"
        row["evidence_type"] = evidence_type
        row["match_type"] = match_type
        row["seed_match_length"] = seed_len
    note_target = row["endpoint_name"] if row["evidence_domain"] == "toxicity" else row["evidence_type"]
    note_scope = "full text" if context.source_kind == "pmc_full_text" else "PubMed abstract"
    row["audit_note"] = (
        f"accepted: {note_scope} source supports primary oligonucleotide {row['evidence_domain']} "
        f"evidence for {note_target}; location={context.location}."
    )


def apply_reject(row: dict[str, str], reason: str) -> None:
    row["curator_decision"] = "reject"
    row["validation_status"] = "curator_rejected"
    row["curator_id"] = CURATOR_ID
    row["audit_note"] = reason


def curate(args: argparse.Namespace) -> None:
    input_csv = Path(args.input_csv)
    output_csv = Path(args.output_csv)
    summary_json = Path(args.summary_json)
    report_csv = Path(args.report_csv)
    fieldnames, rows = read_rows(input_csv)
    pmids = [row.get("pmid", "").strip() for row in rows if row.get("pmid", "").strip()]
    abstract_cache = fetch_pubmed_abstracts(pmids, PUBMED_ABSTRACT_CACHE)
    report_rows: list[dict[str, str]] = []

    for row in rows:
        original_anchor = row.get("source_anchor_hash", "")
        contexts = load_xml_contexts(row)
        if not contexts:
            contexts = abstract_contexts(row, abstract_cache)
        context = best_context(row, contexts)
        decision, reason, grade = accept_decision(row, context)
        if decision == "accept" and context is not None:
            apply_accept(row, context, grade)
        else:
            apply_reject(row, reason)
        report_rows.append(
            {
                "candidate_id": row.get("candidate_id", ""),
                "pmid": row.get("pmid", ""),
                "domain": row.get("evidence_domain", ""),
                "decision": row.get("curator_decision", ""),
                "grade": row.get("evidence_grade", ""),
                "title": row.get("title", ""),
                "verified_location": row.get("source_location_verified", ""),
                "source_kind": context.source_kind if context else "",
                "hash_exact": str(context.hash_exact if context else False).lower(),
                "original_anchor_hash": original_anchor,
                "audit_note": row.get("audit_note", ""),
                "context_excerpt": compact_text(context.text[:450]) if context else "",
            }
        )

    write_csv(output_csv, fieldnames, rows)
    write_csv(
        report_csv,
        [
            "candidate_id",
            "pmid",
            "domain",
            "decision",
            "grade",
            "title",
            "verified_location",
            "source_kind",
            "hash_exact",
            "original_anchor_hash",
            "audit_note",
            "context_excerpt",
        ],
        report_rows,
    )

    accepted = [row for row in rows if row["curator_decision"] == "accept"]
    batch_name = args.batch_name or output_csv.stem
    summary = {
        "batch": batch_name,
        "source_csv": str(input_csv),
        "output_csv": str(output_csv),
        "decision_report_csv": str(report_csv),
        "curator_id": CURATOR_ID,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "rows": len(rows),
        "decision_counts": dict(Counter(row["curator_decision"] for row in rows)),
        "accepted_grade_counts": dict(Counter(row["evidence_grade"] for row in accepted)),
        "accepted_domain_counts": dict(Counter(row["evidence_domain"] for row in accepted)),
        "benchmark_eligible_accepts": sum(1 for row in accepted if row.get("benchmark_eligible_proposed") == "true"),
        "non_benchmark_accepts": sum(1 for row in accepted if row.get("benchmark_eligible_proposed") != "true"),
        "accepted_with_full_text_source": sum(1 for item in report_rows if item["decision"] == "accept" and item["source_kind"] == "pmc_full_text"),
        "accepted_with_pubmed_abstract_source": sum(1 for item in report_rows if item["decision"] == "accept" and item["source_kind"] == "pubmed_abstract"),
        "reject_reason_counts": dict(Counter(row["audit_note"] for row in rows if row["curator_decision"] == "reject")),
    }
    summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--summary-json", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--report-csv", default=str(DEFAULT_REPORT))
    parser.add_argument("--batch-name", default="")
    curate(parser.parse_args())


if __name__ == "__main__":
    main()
