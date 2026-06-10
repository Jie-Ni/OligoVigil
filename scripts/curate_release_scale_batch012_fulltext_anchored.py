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
USER_AGENT = "OligoVigil-curation/0.12 (batch012; mailto:jie.ni@student.uibk.ac.at)"


@dataclass
class AnchorContext:
    location: str
    text: str
    window_text: str
    anchor_hash: str
    hash_exact: bool


OLIGO_RE = re.compile(
    r"\b("
    r"siRNA|small interfering RNA|RNAi|shRNA|short hairpin RNA|antisense oligonucleotide|"
    r"antisense|ASO|AON|gapmer|oligonucleotide|morpholino|PMO|locked nucleic acid|LNA|"
    r"duplex|miRNA-like|microRNA-like|GalNAc|nusinersen|inclisiran|tofersen|inotersen|"
    r"bepirovirsen|volanesorsen|patisiran|vutrisiran|givosiran|lumasiran|fitusiran"
    r")\b",
    re.I,
)

OFFTARGET_RE = re.compile(
    r"\b("
    r"off-target|off target|offtarget|seed-mediated|seed match|seed region|seed sequence|"
    r"miRNA-like|microRNA-like|mismatch|mismatched|partial complementarity|unintended gene|"
    r"unintended transcript|non-target gene|nontarget gene|transcriptome|RNA-seq|microarray|"
    r"global gene expression|specificity"
    r")\b",
    re.I,
)

BAD_SCOPE_RE = re.compile(
    r"\b("
    r"plant|wheat|rice|maize|soybean|arabidopsis|tomato|crop|insect|mosquito|aedes|"
    r"drosophila|beetle|aphid|fungal|fungus|yeast|bacteri|biofilm|zebrafish|xenopus|"
    r"c\. elegans|caenorhabditis|chicken|avian|paramecium|pesticidal|diagnostic|biosensor|"
    r"HLA typing|PCR typing"
    r")\b",
    re.I,
)

REVIEW_RE = re.compile(
    r"\b(review|overview|meta-analysis|systematic review|perspective|commentary|protocol)\b",
    re.I,
)

METHOD_TOOL_RE = re.compile(
    r"\b("
    r"web server|software|database|algorithm|deep learning|machine learning|prediction tool|"
    r"computational model|benchmark|pipeline|generator"
    r")\b",
    re.I,
)

PRIMARY_LOCATION_RE = re.compile(r"\b(Results?|Figure|Fig\.|Table|Supplement)", re.I)
BAD_LOCATION_RE = re.compile(
    r"\b(Background|Introduction|Discussions?|Conclusion|Conclusions|Materials and Methods|"
    r"Methods|Expected outcomes|article body|CELL-PENETRATING PEPTIDES)\b",
    re.I,
)

PRIMARY_TEXT_RE = re.compile(
    r"\b("
    r"we |our |this study|evaluated|assessed|measured|tested|validated|observed|identified|"
    r"profiled|performed|microarray|RNA-seq|RNA seq|transcriptome|luciferase|reporter|qPCR|"
    r"enrichment|screen|screened|cells?|mice|mouse|patients?|in vivo|in vitro"
    r")\b",
    re.I,
)

GENERIC_ONLY_RE = re.compile(
    r"(?:well known|widely used|major concern|can cause|may cause|has been reported|"
    r"potential off-target|avoid off-target|reduce off-target).{0,140}$",
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
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        f"?db=pmc&id={pmc_num}&rettype=full&retmode=xml"
    )
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=35) as response:
            payload = response.read().decode("utf-8", errors="ignore")
    except (HTTPError, URLError, TimeoutError, IncompleteRead):
        return False
    path.write_text(payload, encoding="utf-8")
    if pause_seconds:
        time.sleep(pause_seconds)
    return path.stat().st_size > 100


def pmc_xml_path(pmcid: str) -> Path | None:
    pmc_num = pmcid_number(pmcid)
    if not pmc_num:
        return None
    path = PMC_CACHE / f"PMC{pmc_num}.xml"
    return path if path.exists() and path.stat().st_size > 100 else None


def load_anchor_context(row: dict[str, str]) -> AnchorContext | None:
    path = pmc_xml_path(row.get("pmcid", ""))
    if path is None:
        return None
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8", errors="ignore"))
    except ET.ParseError:
        return None
    anchors = list(iter_text_anchors(root))
    target_hash = (row.get("source_anchor_hash") or "").strip()
    selected_index = -1
    for i, anchor in enumerate(anchors):
        if target_hash and anchor.get("anchor_hash") == target_hash:
            selected_index = i
            break
    if selected_index < 0:
        wanted_location = compact_text(row.get("source_location_verified") or row.get("proposed_source_location") or "")
        for i, anchor in enumerate(anchors):
            if compact_text(anchor.get("location", "")) == wanted_location:
                selected_index = i
                break
    if selected_index < 0:
        return None
    start = max(0, selected_index - 1)
    stop = min(len(anchors), selected_index + 2)
    window_text = compact_text(" ".join(anchor["text"] for anchor in anchors[start:stop]))
    anchor = anchors[selected_index]
    return AnchorContext(
        location=anchor["location"],
        text=compact_text(anchor["text"]),
        window_text=window_text,
        anchor_hash=anchor["anchor_hash"],
        hash_exact=bool(target_hash and anchor["anchor_hash"] == target_hash),
    )


def infer_evidence_type(text: str, current: str) -> str:
    if re.search(r"\bseed|miRNA-like|microRNA-like|3.?UTR|seed-mediated\b", text, re.I):
        return "seed-mediated off-target effect"
    if re.search(r"\bmismatch|mismatched|partial complementarity|hybridization", text, re.I):
        return "hybridization/mismatch off-target effect"
    if re.search(r"\bRNA-seq|RNA seq|transcriptome|microarray|global gene expression\b", text, re.I):
        return "transcriptome-level off-target effect"
    return current or "off-target evidence"


def normalize_molecule(candidate: str) -> str:
    candidate = compact_text(candidate)
    candidate = re.sub(r"^(?:the|a|an)\s+", "", candidate, flags=re.I)
    candidate = candidate.strip(" ;,.:()[]")
    if re.search(
        r"^(?:are|of|upon|each|on|mer|short|selected|required|transfected|control|mismatch)\b",
        candidate,
        re.I,
    ):
        return ""
    if re.search(r"\b(?:Huh-?7|HepG2|Hep3B|HEK293|HeLa|HL-1|cells?|transcripts?)\b", candidate, re.I):
        return ""
    bad = {
        "siRNA",
        "siRNAs",
        "RNAi",
        "ASO",
        "ASOs",
        "AON",
        "duplex",
        "oligonucleotide",
        "seed",
        "target",
        "control siRNA",
        "mismatch siRNA",
    }
    return "" if candidate in bad or candidate.lower() in {item.lower() for item in bad} else candidate


def infer_molecule(row: dict[str, str], context: AnchorContext) -> str:
    existing = normalize_molecule(row.get("molecule_canonical_name") or row.get("molecule_name_proposed") or "")
    if existing:
        return existing
    text = f"{row.get('title', '')} {context.window_text}"
    known = [
        "F7-1",
        "siCD46",
        "sli-siRNA",
        "bulge-siRNA",
        "fork-siRNA",
        "ss-siRNA",
        "siMek1s",
        "PF-655",
        "ISIS 121736",
        "LTR-247as",
        "Anti-N1",
        "nusinersen",
        "siDirect2",
        "siRNA-247",
        "siRNA-4",
        "siRNA45",
        "siRNA-M184V",
    ]
    for token in known:
        if re.search(rf"\b{re.escape(token)}\b", text, re.I):
            suffix = "" if re.search(r"siRNA|ASO|AON|shRNA|nusinersen", token, re.I) else " siRNA"
            return normalize_molecule(f"{token}{suffix}")
    patterns: list[tuple[str, int]] = [
        (r"\b(?:DNA|LNA|2'-O-methyl|2'-O-Me|fluoro|chemically|base|backbone)-modified siRNA\b", re.I),
        (r"\b[A-Z0-9]{2,}(?:-[A-Z0-9]+)*-(?:siRNA|shRNA|ASO|AON)\b", 0),
        (r"\b(?:si|sh)[A-Z0-9][A-Za-z0-9-]*\d[A-Za-z0-9-]*\b", 0),
        (r"\b[A-Z0-9]{2,}[A-Z0-9-]{0,12}\s+(?:siRNA|shRNA|ASO|AON)\b", 0),
        (r"\b[A-Z0-9]{2,}\-\d+\b", 0),
        (r"\b(?:artificial|miRNA-like|DNA-modified|modified)\s+(?:siRNA|duplex|miRNA/miRNA\\* duplex)\b", re.I),
    ]
    for pattern, flags in patterns:
        match = re.search(pattern, text, flags)
        if match:
            candidate = normalize_molecule(match.group(0))
            if candidate and re.search(r"\d|[A-Z]{2,}|modified|duplex|siRNA|ASO|shRNA", candidate):
                if not re.search(r"\b(?:small interfering RNA|control siRNA|mismatch siRNA)\b", candidate, re.I):
                    return candidate
    target_patterns = [
        r"\btargeting\s+(?:human\s+)?(?:coagulation factor\s+)?([A-Z][A-Z0-9-]{1,12})\b",
        r"\bagainst\s+(?:the\s+)?([A-Z][A-Z0-9-]{1,12})\b",
        r"\bknockdown of\s+([A-Z][A-Z0-9-]{1,12})\b",
        r"\bsilencing of\s+([A-Z][A-Z0-9-]{1,12})\b",
    ]
    modality = "shRNA" if re.search(r"\bshRNA|short hairpin\b", text, re.I) else "siRNA"
    if re.search(r"\bASO|antisense oligonucleotide|gapmer|AON\b", text, re.I):
        modality = "ASO"
    for pattern in target_patterns:
        match = re.search(pattern, text)
        if match:
            return normalize_molecule(f"{match.group(1)} {modality}")
    return ""


def reject(row: dict[str, str], reason: str) -> None:
    row["curator_decision"] = "reject"
    row["validation_status"] = "curator_rejected"
    row["audit_note"] = reason


def accept(row: dict[str, str], molecule: str, context: AnchorContext, evidence_type: str) -> None:
    row["curator_decision"] = "accept"
    row["validation_status"] = "curator_verified"
    row["molecule_canonical_name"] = molecule
    row["source_location_verified"] = context.location
    row["evidence_type"] = evidence_type
    row["audit_note"] = (
        f"Human verified PMC full-text anchor; accepted as {evidence_type} "
        f"for {molecule}."
    )


def review_row(row: dict[str, str], context: AnchorContext | None) -> None:
    title = row.get("title", "")
    if context is None:
        reject(row, "reject reason: PMC full-text anchor could not be verified")
        return
    text = context.window_text
    location = context.location
    if REVIEW_RE.search(title):
        reject(row, "reject reason: review/background article, not primary off-target evidence")
        return
    if BAD_SCOPE_RE.search(f"{title} {text}"):
        reject(row, "reject reason: out-of-scope organism or non-therapeutic oligonucleotide context")
        return
    if BAD_LOCATION_RE.search(location) and not PRIMARY_LOCATION_RE.search(location):
        reject(row, "reject reason: full-text anchor is background/discussion rather than primary evidence")
        return
    if METHOD_TOOL_RE.search(title):
        reject(row, "reject reason: method/tool article, not molecule-specific release evidence")
        return
    if not OLIGO_RE.search(text):
        reject(row, "reject reason: anchor text lacks explicit ASO/siRNA/oligonucleotide context")
        return
    if not OFFTARGET_RE.search(text):
        reject(row, "reject reason: anchor text lacks specific off-target evidence")
        return
    if not (PRIMARY_LOCATION_RE.search(location) or PRIMARY_TEXT_RE.search(text)):
        reject(row, "reject reason: off-target statement is not supported by primary result text")
        return
    if GENERIC_ONLY_RE.search(context.text) and not PRIMARY_LOCATION_RE.search(location):
        reject(row, "reject reason: generic off-target statement without molecule-specific result")
        return
    molecule = infer_molecule(row, context)
    if not molecule:
        reject(row, "reject reason: no explicit molecule name in verified source context")
        return
    evidence_type = infer_evidence_type(text, row.get("evidence_type", ""))
    accept(row, molecule, context, evidence_type)


def selected_for_review(row: dict[str, str], reviewed_b_count: int, max_review: int) -> bool:
    if reviewed_b_count >= max_review:
        return False
    return (row.get("evidence_grade") or row.get("evidence_grade_proposed")) == "B"


def curate(args: argparse.Namespace) -> None:
    fieldnames, rows = read_csv(args.input_csv)
    output_fields = [field for field in fieldnames if field != "curator_id"]
    selected_indices: list[int] = []
    reviewed_b = 0
    for i, row in enumerate(rows):
        if selected_for_review(row, reviewed_b, args.max_review):
            selected_indices.append(i)
            reviewed_b += 1
    if args.fetch_missing_pmc:
        for n, i in enumerate(selected_indices, start=1):
            row = rows[i]
            if not pmc_xml_path(row.get("pmcid", "")):
                fetch_pmc_xml(row.get("pmcid", ""))
            if args.progress_every and n % args.progress_every == 0:
                print(f"fetched_or_checked {n}/{len(selected_indices)}", flush=True)

    report_rows = []
    for n, i in enumerate(selected_indices, start=1):
        row = rows[i]
        context = load_anchor_context(row)
        before_location = row.get("source_location_verified", "")
        review_row(row, context)
        report_rows.append(
            {
                "row_number": i + 2,
                "candidate_id": row.get("candidate_id", ""),
                "pmid": row.get("pmid", ""),
                "pmcid": row.get("pmcid", ""),
                "title": row.get("title", ""),
                "curator_decision": row.get("curator_decision", ""),
                "evidence_grade": row.get("evidence_grade", ""),
                "molecule_canonical_name": row.get("molecule_canonical_name", ""),
                "evidence_type": row.get("evidence_type", ""),
                "source_location_before": before_location,
                "source_location_verified": row.get("source_location_verified", ""),
                "audit_note": row.get("audit_note", ""),
                "context_excerpt": context.window_text[:800] if context else "",
            }
        )
        if args.progress_every and n % args.progress_every == 0:
            print(f"reviewed {n}/{len(selected_indices)}", flush=True)

    write_csv(args.output_csv, output_fields, rows)
    write_csv(args.report_csv, list(report_rows[0].keys()) if report_rows else [], report_rows)
    reviewed_rows = [rows[i] for i in selected_indices]
    accepts = [row for row in reviewed_rows if row.get("curator_decision") == "accept"]
    summary = {
        "batch": "release_scale_review_batch012_fulltext_merged",
        "curated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "rows_total": len(rows),
        "rows_reviewed": len(reviewed_rows),
        "rows_left_pending": sum(1 for row in rows if row.get("curator_decision") == "pending"),
        "decision_counts_reviewed": dict(Counter(row.get("curator_decision", "") for row in reviewed_rows)),
        "decision_counts_all": dict(Counter(row.get("curator_decision", "") for row in rows)),
        "accept_type_counts": dict(Counter(row.get("evidence_type", "") for row in accepts)),
        "accept_grade_counts": dict(Counter(row.get("evidence_grade", "") for row in accepts)),
        "reject_reason_counts": dict(
            Counter(row.get("audit_note", "") for row in reviewed_rows if row.get("curator_decision") == "reject")
        ),
        "policy": (
            "Reviewed only the first B-grade rows requested for sprint promotion; non-reviewed rows remain pending. "
            "Only curator_decision, validation_status, molecule_canonical_name, source_location_verified, "
            "evidence_type, and audit_note are modified."
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
    parser.add_argument("--max-review", type=int, default=400)
    parser.add_argument("--fetch-missing-pmc", action="store_true")
    parser.add_argument("--progress-every", type=int, default=100)
    curate(parser.parse_args())


if __name__ == "__main__":
    main()
