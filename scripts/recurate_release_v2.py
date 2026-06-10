"""recurate_release_v2.py — local, sequential, rate-safe v2 re-curation of EXISTING release rows.

WHY: the parallel Claude-Code workflow hit API rate limits at 565-way concurrency. The fix is
volume-agnostic: run sequentially (low/no concurrency) with retry+backoff. This script re-curates
the release rows listed in a re-curate JSONL (built from the DB) using the SAME source-grounded
v2 contract as curate_v2_llm.py, and writes an entity-keyed human-review CSV (machine proposal +
verbatim grounding + EMPTY human columns). It NEVER writes curator_decision/curator_id/
validation_status — those stay for human sign-off (red-line safe).

Resumable: appends to the output CSV and skips entity_ids already present, so an interrupted run
(or a rate-limit pause) can be re-launched and continues where it stopped.

USAGE:
    setx ANTHROPIC_API_KEY "sk-ant-..."        # once (new shells inherit it), or set in-session
    pip install anthropic
    python scripts/recurate_release_v2.py \
        --input-jsonl data/generated/v2_recurate_offtarget_input.jsonl \
        --output-csv  data/generated/v2_offtarget_human_review.csv \
        --model claude-opus-4-8 [--limit N] [--sleep 0.4]
    # then the same for v2_recurate_toxicity_input.jsonl
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from curate_v2_llm import (  # noqa: E402
    CURATOR_SYSTEM, CURATOR_RUBRIC, DECISION_TOOL,
    load_abstract_cache, pmc_text, verify_grounding,
)

OUT_COLS = [
    "entity_id", "entity_table", "sid", "molecule", "pmid", "pmcid", "doi", "title",
    "v1_claimed_evidence_type", "v1_grade", "v1_claimed_location",
    "v2_proposed_decision", "v2_evidence_type", "v2_domain_match", "v2_in_scope", "v2_grade",
    "v2_confidence", "v2_passage_kind", "v2_grounding_verified", "v2_grounding_quote", "v2_reason",
    "extractor_model",
    "human_decision", "human_curator_id", "human_evidence_grade", "human_note",
]


def passage_for(row: dict, abstracts: dict) -> tuple[str, str]:
    ft = pmc_text(row.get("pmcid", ""))
    if ft:
        return ft, "pmc_full_text"
    ab = (abstracts.get(str(row.get("pmid", "")), {}) or {}).get("abstract", "")
    if ab:
        return ab, "pubmed_abstract"
    return "", "none"


def call_with_backoff(client, model: str, domain: str, passage: str, tries: int = 5) -> dict:
    user = (
        f"DOMAIN REQUESTED: {domain}\n\nThis is an EXISTING release row produced by a crude v1 "
        f"keyword classifier; re-judge from the passage and do NOT trust prior labels.\n\n"
        f"SOURCE PASSAGE (decide strictly from this text only):\n\"\"\"\n{passage[:48000]}\n\"\"\"\n\n"
        f"{CURATOR_RUBRIC}\n\nCall emit_curation_decision with your verdict."
    )
    last = None
    for attempt in range(tries):
        try:
            resp = client.messages.create(
                model=model, max_tokens=1024,
                system=[{"type": "text", "text": CURATOR_SYSTEM, "cache_control": {"type": "ephemeral"}}],
                tools=[DECISION_TOOL], tool_choice={"type": "tool", "name": "emit_curation_decision"},
                messages=[{"role": "user", "content": user}],
            )
            for block in resp.content:
                if getattr(block, "type", None) == "tool_use":
                    return dict(block.input)
            raise RuntimeError("no tool_use block")
        except Exception as exc:  # noqa: BLE001 — includes RateLimit, APIError, timeouts
            last = exc
            wait = min(60, 2 ** attempt * 2)
            print(f"    retry {attempt + 1}/{tries} after {wait}s ({type(exc).__name__})", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"all retries failed: {last}")


def call_gemini_with_backoff(client, model: str, domain: str, passage: str, tries: int = 6) -> dict:
    from google.genai import types  # noqa: WPS433
    prompt = (
        f"DOMAIN REQUESTED: {domain}\n\nThis is an EXISTING release row produced by a crude v1 "
        f"keyword classifier; re-judge from the passage and do NOT trust prior labels.\n\n"
        f"SOURCE PASSAGE (decide strictly from this text only):\n\"\"\"\n{passage[:48000]}\n\"\"\"\n\n"
        f"{CURATOR_RUBRIC}\n\n"
        "Return ONLY a JSON object with EXACTLY these keys: decision (one of accept|reject|abstain), "
        "molecule_in_scope (boolean), molecule_name (string), modality (string), primary_result (boolean), "
        "acronym_ok (boolean), evidence_type (one of safety_tox|offtarget_observed|efficacy|knockdown_potency|"
        "pk_biodistribution|computational_designonly|other|none), domain_match (boolean), "
        "grounding_quote (string: an exact verbatim span copied from the passage, or NONE), "
        "source_location (string), grade (one of A|B|C|NA), confidence (number 0..1), reason (string)."
    )
    last = None
    for attempt in range(tries):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=CURATOR_SYSTEM,
                    response_mime_type="application/json",
                    temperature=0,
                    max_output_tokens=2048,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            return json.loads(resp.text)
        except Exception as exc:  # noqa: BLE001 — includes rate limits, blocked responses, parse errors
            last = exc
            wait = min(90, 2 ** attempt * 3)
            print(f"    gemini retry {attempt + 1}/{tries} after {wait}s ({type(exc).__name__})", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"gemini retries failed: {last}")


def done_entity_ids(out_path: Path) -> set[str]:
    if not out_path.exists():
        return set()
    with out_path.open(encoding="utf-8", newline="") as fh:
        return {r["entity_id"] for r in csv.DictReader(fh)
                if r.get("v2_proposed_decision") not in ("", "PENDING_RERUN", "llm_error", None)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-jsonl", required=True, type=Path)
    ap.add_argument("--output-csv", required=True, type=Path)
    ap.add_argument("--provider", choices=["anthropic", "gemini"], default="gemini")
    ap.add_argument("--model", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.4, help="pause between calls (rate-safety)")
    args = ap.parse_args()

    if args.provider == "gemini":
        try:
            from google import genai  # noqa: WPS433
        except ImportError:
            sys.exit("pip install google-genai")
        if not os.environ.get("GEMINI_API_KEY"):
            sys.exit("set GEMINI_API_KEY")
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        model = args.model or "gemini-2.5-flash"
        caller = call_gemini_with_backoff
    else:
        try:
            import anthropic  # noqa: WPS433
        except ImportError:
            sys.exit("pip install anthropic")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit("set ANTHROPIC_API_KEY")
        client = anthropic.Anthropic()
        model = args.model or "claude-opus-4-8"
        caller = call_with_backoff

    rows = [json.loads(line) for line in args.input_jsonl.open(encoding="utf-8")]
    if args.limit:
        rows = rows[: args.limit]
    abstracts = load_abstract_cache()

    already = done_entity_ids(args.output_csv)
    new_file = not args.output_csv.exists()
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    fh = args.output_csv.open("a", encoding="utf-8", newline="")
    w = csv.DictWriter(fh, fieldnames=OUT_COLS, extrasaction="ignore")
    if new_file:
        w.writeheader()

    counts = {"accept": 0, "reject": 0, "abstain": 0, "skipped": 0}
    for i, row in enumerate(rows):
        eid = str(row.get("entity_id"))
        if eid in already:
            counts["skipped"] += 1
            continue
        domain = (row.get("domain") or "toxicity").strip()
        passage, kind = passage_for(row, abstracts)
        if not passage:
            d = {"decision": "abstain", "evidence_type": "none", "grade": "NA", "confidence": 0.0,
                 "grounding_quote": "NONE", "domain_match": False, "molecule_in_scope": False,
                 "reason": "no source passage available (no cached full text or abstract)"}
        else:
            try:
                d = caller(client, model, domain, passage)
                d = verify_grounding(d, passage)
            except Exception as exc:  # noqa: BLE001 — one bad row must not kill a 2000-row run
                d = {"decision": "llm_error", "evidence_type": "none", "grade": "NA", "confidence": 0.0,
                     "grounding_quote": "NONE", "domain_match": False, "molecule_in_scope": False,
                     "grounding_verified": False, "reason": f"llm_error: {type(exc).__name__}: {exc}"}
        w.writerow({
            "entity_id": row.get("entity_id"), "entity_table": row.get("entity_table"), "sid": row.get("sid"),
            "molecule": row.get("molecule"), "pmid": row.get("pmid"), "pmcid": row.get("pmcid"),
            "doi": row.get("doi"), "title": (row.get("title") or "")[:200],
            "v1_claimed_evidence_type": row.get("claimed_evidence_type"), "v1_grade": row.get("v1_grade"),
            "v1_claimed_location": (row.get("claimed_location") or "")[:160],
            "v2_proposed_decision": d.get("decision"), "v2_evidence_type": d.get("evidence_type"),
            "v2_domain_match": d.get("domain_match"), "v2_in_scope": d.get("molecule_in_scope"),
            "v2_grade": d.get("grade"), "v2_confidence": d.get("confidence"), "v2_passage_kind": kind,
            "v2_grounding_verified": d.get("grounding_verified", ""), "v2_grounding_quote": (d.get("grounding_quote") or "")[:500],
            "v2_reason": (d.get("reason") or "")[:600], "extractor_model": f"recurate_release_v2:{model}",
            "human_decision": "", "human_curator_id": "", "human_evidence_grade": "", "human_note": "",
        })
        fh.flush()
        counts[d.get("decision", "abstain")] = counts.get(d.get("decision", "abstain"), 0) + 1
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(rows)} {counts}", file=sys.stderr)
        if args.sleep:
            time.sleep(args.sleep)
    fh.close()
    print(json.dumps({"input": str(args.input_jsonl), "output": str(args.output_csv),
                      "model": model, "counts": counts,
                      "note": "MACHINE pre-curation; human_* columns empty for review."}, indent=2))


if __name__ == "__main__":
    main()
