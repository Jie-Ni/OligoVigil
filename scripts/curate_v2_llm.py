"""curate_v2_llm.py — v2 source-grounded LLM pre-curator for OligoVigil.

WHY THIS EXISTS
---------------
v1 (`curate_release_scale_batch003.py` et al.) decides accept/reject by keyword/regex
term scoring. An independent re-adjudication of a 125-record stratified sample measured a
**74.2% false-accept rate** (accept precision 0.258): 70% of the false accepts were in-scope
oligos whose evidence was efficacy/knockdown/PK mislabeled into the toxicity/off-target domain,
plus boilerplate `audit_note` strings asserting endpoints absent from the source text, plus
scope leakage (CRISPR/shRNA/lncRNA/small molecules) and acronym collisions (ASO = atrial septal
occluder / Annals of Surgical Oncology).

v2 replaces the term-scorer with an LLM that reads the actual source passage and must:
  1. confirm a THERAPEUTIC oligonucleotide (ASO/siRNA/PMO/LNA/gapmer/aptamer/GalNAc-siRNA) is the
     agent under study  (exclusion-first: reject CRISPR/shRNA/AAV/mRNA/lncRNA/small-molecule/TCM/
     G4-ligand/agricultural-RNAi, and reject oligo-as-knockdown-tool);
  2. confirm the evidence is a PRIMARY observed/measured result (not background/methods/review);
  3. classify the EVIDENCE TYPE and require it to MATCH the domain
     (toxicity => safety/tox endpoint linked to the oligo; offtarget => OBSERVED seed/mismatch/
     transcriptome/RNA-seq unintended effect; reject efficacy / knockdown-potency / PK / design-only);
  4. emit a GROUNDING QUOTE: an exact verbatim span of the source supporting the accept. The span
     is verified in code to be a substring of the supplied source text; if it is not, the decision
     is forced to reject ("ungrounded"). This makes hallucinated rationales impossible.

RED-LINE COMPLIANCE (do not remove)
-----------------------------------
This script is a MACHINE PRE-CURATOR. It writes ONLY *_proposed columns plus
proposed_decision / grounding_quote / llm_confidence / extractor_model. It NEVER writes
curator_decision, curator_id, or validation_status='curator_verified'. Those are filled only by a
human reviewer downstream; `promote_curator_review.py` hard-requires validation_status==
'curator_verified', so nothing this script emits can reach the release tables without human sign-off.

USAGE
-----
    export ANTHROPIC_API_KEY=...          # run on HPC; heavy I/O -> /local, stage out to /scratch
    python scripts/curate_v2_llm.py \
        --input-csv  data/generated/release_scale_review_batchNNN_template.csv \
        --output-csv data/generated/curate_v2_batchNNN_proposed.csv \
        --model claude-opus-4-8 \
        [--limit N] [--abstain-conf 0.55]

Requires: `pip install anthropic`. No network is used except the Anthropic API and (optionally)
NCBI efetch for abstracts not already cached.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "data" / "generated"
PMC_CACHE = GENERATED / "pmc_xml_cache"
ABSTRACT_CACHE = GENERATED / "pubmed_abstract_cache_batch003.json"

EXTRACTOR_TAG = "curate_v2_llm.py"

# --------------------------------------------------------------------------- #
# The curator contract: identical wording is used by the demo workflow so the  #
# demonstration faithfully reflects this production script.                    #
# --------------------------------------------------------------------------- #
CURATOR_SYSTEM = """You are a strict curator for OligoVigil, a database of curator-reviewed \
THERAPEUTIC oligonucleotide (ASO / siRNA / PMO / LNA / gapmer / morpholino / aptamer / \
GalNAc-siRNA) SAFETY and OFF-TARGET evidence. You read one source passage and decide whether it \
contains primary evidence that belongs in the database. You are conservative: when the passage \
does not clearly support an accept, you reject or abstain. You never invent content; every accept \
must quote an exact verbatim span of the supplied passage."""

CURATOR_RUBRIC = """Decide ACCEPT only if ALL of the following hold, judged strictly from the \
SUPPLIED PASSAGE (not outside knowledge):

GATE 1 — MOLECULE IN SCOPE (exclusion-first). A therapeutic oligonucleotide must be the agent \
UNDER STUDY: antisense oligonucleotide / ASO / gapmer / siRNA / RNAi therapeutic / morpholino \
(PMO) / LNA / aptamer / GalNAc-siRNA, or a delivery vehicle carrying such an oligo. REJECT if the \
agent is: CRISPR/Cas, shRNA, AAV/viral gene therapy, mRNA therapeutic, endogenous lncRNA/circRNA/\
miRNA biology, a small molecule / natural product / TCM, a G-quadruplex small-molecule ligand, \
agricultural/insect/nematode RNAi, or an oligo used merely as a lab knockdown TOOL rather than as \
the therapeutic under study. Disambiguate acronyms by sense: "ASO" must mean antisense \
oligonucleotide here, NOT atrial septal occluder, arteriosclerosis obliterans, or the journal \
Annals of Surgical Oncology; "mismatch" must mean oligo hybridization mismatch, NOT dMMR/MSI-H \
tumor status.

GATE 2 — PRIMARY RESULT. The passage must report an actually observed/measured/administered \
result. REJECT background, introduction, motivation/hypothesis, methods/protocol descriptions, \
prior-work recaps, and review/meta-analysis/guidance text.

GATE 3 — EVIDENCE TYPE MATCHES DOMAIN. First classify the evidence type, then require it to match \
the requested domain:
  - toxicity domain: ACCEPT only a safety/tolerability/toxicity endpoint (hepatic, renal, platelet, \
    immune/cytokine/complement, hemolysis, cell-viability/cytotoxicity, genotoxicity, body weight, \
    mortality, adverse events) LINKED to the oligo or its delivery product. REJECT if the evidence \
    type is efficacy / target knockdown potency / pharmacokinetics / biodistribution / on-target \
    activity, or if the toxicity belongs to an external toxin or disease-injury model where the \
    oligo is only a knockdown tool, or if "cytotoxicity" is a cancer-cell-killing efficacy readout.
  - offtarget domain: ACCEPT only an OBSERVED unintended-effect result: seed-mediated, mismatch/\
    hybridization-dependent, transcriptome-wide, RNA-seq, or microarray off-target evidence. REJECT \
    computational/design-only specificity screens, PK/biodistribution, and on-target/efficacy \
    "specificity".

GATE 4 — GROUNDING. Provide grounding_quote: an EXACT verbatim span copied from the supplied \
passage that simultaneously establishes the in-scope oligo and the domain-matched primary result. \
If no single passage supports the accept, set grounding_quote to "NONE" and do not accept.

If the passage is too truncated/ambiguous to apply the gates, set decision="abstain".

GRADE (only when decision=accept): A = full-text Results/Figure/Table/Supplement section AND a \
NAMED therapeutic oligo AND correct evidence type; B = therapeutic oligo but abstract-only or \
weaker location; C = in-scope but generic/unnamed oligo or weak support."""

# JSON schema for the structured decision (Anthropic tool use).
DECISION_TOOL = {
    "name": "emit_curation_decision",
    "description": "Emit the structured pre-curation decision for one source passage.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "decision", "molecule_in_scope", "molecule_name", "modality",
            "primary_result", "acronym_ok", "evidence_type", "domain_match",
            "grounding_quote", "source_location", "grade", "confidence", "reason",
        ],
        "properties": {
            "decision": {"type": "string", "enum": ["accept", "reject", "abstain"]},
            "molecule_in_scope": {"type": "boolean"},
            "molecule_name": {"type": "string"},
            "modality": {"type": "string"},
            "primary_result": {"type": "boolean"},
            "acronym_ok": {"type": "boolean", "description": "true if oligo acronyms resolve to oligonucleotide sense in context"},
            "evidence_type": {
                "type": "string",
                "enum": ["safety_tox", "offtarget_observed", "efficacy", "knockdown_potency",
                         "pk_biodistribution", "computational_designonly", "other", "none"],
            },
            "domain_match": {"type": "boolean"},
            "grounding_quote": {"type": "string", "description": "exact verbatim span from the passage, or NONE"},
            "source_location": {"type": "string"},
            "grade": {"type": "string", "enum": ["A", "B", "C", "NA"]},
            "confidence": {"type": "number"},
            "reason": {"type": "string"},
        },
    },
}


def load_abstract_cache() -> dict:
    """Merge every PubMed abstract cache file under data/generated.

    Files matching pubmed_abstract_cache_*.json are loaded in lexicographic order.
    Later files OVERRIDE earlier ones on key collision, so any future re-fetch with a
    corrected abstract takes precedence over the original batch003 cache. Each value is
    expected to be {"abstract": "<text>"} to match the existing batch003 file shape.
    """
    merged: dict = {}
    # Defensive: keep the explicit batch003 path first so even an oddly-named file
    # cannot accidentally suppress the original cache.
    candidates = []
    if ABSTRACT_CACHE.exists():
        candidates.append(ABSTRACT_CACHE)
    for p in sorted(GENERATED.glob("pubmed_abstract_cache_*.json")):
        if p == ABSTRACT_CACHE:
            continue
        candidates.append(p)
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        merged.update(data)
    return merged


def pmc_text(pmcid: str) -> str:
    """Return concatenated full-text passage text from the local PMC XML cache, if present."""
    m = re.search(r"(\d+)", pmcid or "")
    if not m:
        return ""
    path = PMC_CACHE / f"PMC{m.group(1)}.xml"
    if not (path.exists() and path.stat().st_size > 200):
        return ""
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8", errors="ignore"))
    except ET.ParseError:
        return ""
    parts = []
    for el in root.iter():
        tag = el.tag.lower()
        if tag in {"title", "p", "caption", "td", "abstract"} and el.text:
            txt = " ".join("".join(el.itertext()).split())
            if len(txt) >= 30:
                parts.append(txt)
    text = "\n".join(parts)
    return text[:60000]  # bound prompt size


def source_passage(row: dict, abstracts: dict) -> tuple[str, str]:
    """Prefer cached PMC full text; fall back to the cached PubMed abstract."""
    ft = pmc_text(row.get("pmcid", ""))
    if ft:
        return ft, "pmc_full_text"
    pmid = (row.get("pmid") or "").strip()
    ab = (abstracts.get(pmid, {}) or {}).get("abstract", "")
    if ab:
        return ab, "pubmed_abstract"
    # last resort: whatever candidate-level location/snippet the template carries
    snippet = " ".join(
        str(row.get(k, "")) for k in ("candidate_source_location", "proposed_source_location", "title")
    ).strip()
    return snippet, "candidate_snippet"


def call_anthropic(client, model: str, domain: str, passage: str) -> dict:
    user = (
        f"DOMAIN REQUESTED: {domain}\n\n"
        f"SOURCE PASSAGE (decide strictly from this text only):\n\"\"\"\n{passage}\n\"\"\"\n\n"
        f"{CURATOR_RUBRIC}\n\nCall emit_curation_decision with your verdict."
    )
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=[{"type": "text", "text": CURATOR_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=[DECISION_TOOL],
        tool_choice={"type": "tool", "name": "emit_curation_decision"},
        messages=[{"role": "user", "content": user}],
    )
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use":
            return dict(block.input)
    raise RuntimeError("model did not return a tool_use block")


def verify_grounding(decision: dict, passage: str) -> dict:
    """Force reject if an accept is not grounded in a verbatim substring of the passage."""
    if decision.get("decision") != "accept":
        return decision
    quote = (decision.get("grounding_quote") or "").strip()
    norm_p = " ".join(passage.split()).lower()
    norm_q = " ".join(quote.split()).lower()
    grounded = bool(norm_q) and norm_q != "none" and len(norm_q) >= 12 and norm_q in norm_p
    decision["grounding_verified"] = grounded
    if not grounded:
        decision["decision"] = "reject"
        decision["grade"] = "NA"
        decision["reason"] = "ungrounded: grounding_quote is not a verbatim span of the source passage; " + decision.get("reason", "")
    return decision


def write_proposed(out_path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    extra = [
        "proposed_decision", "proposed_evidence_type", "proposed_grade", "grounding_quote",
        "grounding_source_location", "grounding_verified", "llm_confidence", "extractor_model",
        "molecule_name_proposed_llm", "modality_proposed_llm", "proposed_reason",
    ]
    cols = list(fieldnames) + [c for c in extra if c not in fieldnames]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-csv", required=True, type=Path)
    ap.add_argument("--output-csv", required=True, type=Path)
    ap.add_argument("--model", default="claude-opus-4-8")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--abstain-conf", type=float, default=0.0,
                    help="downgrade accepts below this confidence to abstain (route to human)")
    args = ap.parse_args()

    try:
        import anthropic  # noqa: WPS433
    except ImportError:
        sys.exit("pip install anthropic  (and set ANTHROPIC_API_KEY)")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("set ANTHROPIC_API_KEY")
    client = anthropic.Anthropic()

    abstracts = load_abstract_cache()
    with args.input_csv.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if args.limit:
        rows = rows[: args.limit]

    counts = {"accept": 0, "reject": 0, "abstain": 0}
    for i, row in enumerate(rows):
        domain = (row.get("evidence_domain") or "").strip() or "toxicity"
        passage, kind = source_passage(row, abstracts)
        if not passage:
            decision = {"decision": "abstain", "reason": "no source passage available",
                        "grade": "NA", "confidence": 0.0, "evidence_type": "none",
                        "grounding_quote": "NONE", "molecule_name": "", "modality": "",
                        "source_location": ""}
        else:
            for attempt in range(3):
                try:
                    decision = call_anthropic(client, args.model, domain, passage)
                    break
                except Exception as exc:  # noqa: BLE001
                    if attempt == 2:
                        decision = {"decision": "abstain", "reason": f"llm_error:{exc}",
                                    "grade": "NA", "confidence": 0.0, "evidence_type": "none",
                                    "grounding_quote": "NONE", "molecule_name": "", "modality": "",
                                    "source_location": ""}
                    else:
                        time.sleep(2 * (attempt + 1))
            decision = verify_grounding(decision, passage)
        if (decision["decision"] == "accept"
                and args.abstain_conf
                and float(decision.get("confidence") or 0) < args.abstain_conf):
            decision["decision"] = "abstain"
            decision["reason"] = "low_confidence_routed_to_human: " + decision.get("reason", "")

        # write ONLY proposed/machine columns; human columns stay empty
        row["proposed_decision"] = decision["decision"]
        row["proposed_evidence_type"] = decision.get("evidence_type", "")
        row["proposed_grade"] = decision.get("grade", "NA")
        row["grounding_quote"] = decision.get("grounding_quote", "")
        row["grounding_source_location"] = decision.get("source_location", "") + f" [{kind}]"
        row["grounding_verified"] = str(decision.get("grounding_verified", False)).lower()
        row["llm_confidence"] = decision.get("confidence", "")
        row["extractor_model"] = f"{EXTRACTOR_TAG}:{args.model}"
        row["molecule_name_proposed_llm"] = decision.get("molecule_name", "")
        row["modality_proposed_llm"] = decision.get("modality", "")
        row["proposed_reason"] = decision.get("reason", "")
        # explicit red-line guard: never let this script populate human/release columns
        for human_col in ("curator_decision", "curator_id", "validation_status"):
            if human_col in row and row.get(human_col):
                row[human_col] = ""
        counts[decision["decision"]] = counts.get(decision["decision"], 0) + 1
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(rows)} {counts}", file=sys.stderr)

    write_proposed(args.output_csv, fieldnames, rows)
    print(json.dumps({
        "input": str(args.input_csv), "output": str(args.output_csv),
        "model": args.model, "rows": len(rows), "proposed_counts": counts,
        "note": "MACHINE pre-curation only; curator_decision/curator_id/validation_status left empty for human review.",
    }, indent=2))


if __name__ == "__main__":
    main()
