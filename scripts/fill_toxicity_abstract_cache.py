"""Fetch PubMed abstracts for the 402 toxicity candidate PMIDs that currently have no
cached source passage, so a future EXPAND-2 round can curate them.

Procedure (HONESTY LOCK):
  - NCBI E-utilities only (no scraping, no LLM re-write).
  - Rate limit: 3 req/s without API key. Default to 3 req/s.
  - Identify ourselves in User-Agent.
  - Cache abstracts EXACTLY as returned by efetch (concatenate AbstractText elements, preserving
    Label="..." labels). No editorial changes.
  - DO NOT touch pubmed_abstract_cache_batch003.json. Write a NEW timestamped file under
    data/generated/pubmed_abstract_cache_toxicity_round2_<UTC>.json.
  - Cache file shape matches the existing loader expectation: {"<pmid>": {"abstract": "<text>"}}.
  - Idempotent: re-running picks up any previously written entries and skips them.

Usage:
    python scripts/fill_toxicity_abstract_cache.py
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "oligosafety.db"
GENERATED = ROOT / "data" / "generated"
EXISTING_CACHE = GENERATED / "pubmed_abstract_cache_batch003.json"

USER_AGENT = "OligoVigil-public-resource (mailto:njie@seu.edu.cn)"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
BATCH_SIZE = 200
SLEEP_BETWEEN_BATCHES = 0.34  # ~3 req/s ceiling without API key
RETRY_PER_BATCH = 3

QUERY_SQL = """
SELECT DISTINCT cc.pmid
  FROM curation_candidate cc
 WHERE cc.evidence_domain = 'toxicity'
   AND cc.validation_status = 'candidate_needs_curator_review'
   AND cc.pmid IS NOT NULL
 ORDER BY cc.pmid
"""


# --------------------------------------------------------------------------- #
# HTTP layer: prefer requests, fall back to urllib.                            #
# --------------------------------------------------------------------------- #
def _post(url: str, data: dict, timeout: int = 60) -> bytes:
    try:
        import requests  # type: ignore

        resp = requests.post(
            url, data=data, headers={"User-Agent": USER_AGENT}, timeout=timeout
        )
        resp.raise_for_status()
        return resp.content
    except ImportError:
        from urllib.parse import urlencode
        from urllib.request import Request, urlopen

        req = Request(
            url,
            data=urlencode(data).encode("ascii"),
            headers={"User-Agent": USER_AGENT},
            method="POST",
        )
        with urlopen(req, timeout=timeout) as r:
            return r.read()


# --------------------------------------------------------------------------- #
# XML parsing — preserve Label="..." prefixes, no LLM re-write.                #
# --------------------------------------------------------------------------- #
def _node_text(node: ET.Element) -> str:
    """Return the concatenated text content of an XML node, including text inside child tags."""
    return "".join(node.itertext())


def _abstract_from_article(article: ET.Element) -> str:
    """Build the abstract string from a PubmedArticle / BookDocument node, exactly as returned.

    For a Structured Abstract we preserve the Label="..." prefix (e.g. "BACKGROUND: ...").
    Multiple AbstractText elements are joined with a single space.
    """
    pieces: list[str] = []
    for at in article.iter("AbstractText"):
        body = _node_text(at).strip()
        if not body:
            continue
        label = at.attrib.get("Label")
        if label:
            pieces.append(f"{label.strip()}: {body}")
        else:
            pieces.append(body)
    return " ".join(pieces)


def parse_efetch_xml(xml_bytes: bytes) -> dict[str, str]:
    """Return {pmid: abstract_text}. abstract_text == '' iff the record has no Abstract."""
    out: dict[str, str] = {}
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        print(f"[warn] efetch XML parse error: {exc}", file=sys.stderr)
        return out

    # Iterate both PubmedArticle and PubmedBookArticle records.
    for tag in ("PubmedArticle", "PubmedBookArticle"):
        for art in root.iter(tag):
            pmid_node = art.find(".//PMID")
            if pmid_node is None or not (pmid_node.text or "").strip():
                continue
            pmid = pmid_node.text.strip()
            out[pmid] = _abstract_from_article(art)
    return out


# --------------------------------------------------------------------------- #
# Driver                                                                       #
# --------------------------------------------------------------------------- #
def fetch_batch(pmids: list[str]) -> tuple[dict[str, str], str]:
    """Return (parsed_map, error_string_or_empty)."""
    data = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "abstract",
        "retmode": "xml",
    }
    last_err = ""
    for attempt in range(1, RETRY_PER_BATCH + 1):
        try:
            xml_bytes = _post(EFETCH_URL, data, timeout=90)
            parsed = parse_efetch_xml(xml_bytes)
            return parsed, ""
        except Exception as exc:  # noqa: BLE001
            last_err = f"{type(exc).__name__}: {exc}"
            sleep_s = 2.0 * attempt
            print(
                f"[warn] efetch attempt {attempt}/{RETRY_PER_BATCH} failed ({last_err}); "
                f"sleeping {sleep_s:.1f}s",
                file=sys.stderr,
            )
            time.sleep(sleep_s)
    return {}, last_err


def main() -> int:
    if not DB_PATH.exists():
        print(f"[fatal] DB not found: {DB_PATH}", file=sys.stderr)
        return 2

    # (1) Get the 402 target PMIDs from the DB.
    con = sqlite3.connect(str(DB_PATH))
    target_pmids = [str(r[0]).strip() for r in con.execute(QUERY_SQL).fetchall() if r[0] is not None]
    con.close()
    requested = len(target_pmids)
    print(f"[info] requested PMIDs from DB: {requested}")

    # (2) Load existing cache (read-only) — skip any PMID already cached.
    existing: dict = {}
    if EXISTING_CACHE.exists():
        try:
            existing = json.loads(EXISTING_CACHE.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"[warn] could not parse existing cache, treating as empty: {exc}", file=sys.stderr)
    skipped_already_cached = 0
    todo: list[str] = []
    for pmid in target_pmids:
        if pmid in existing:
            skipped_already_cached += 1
        else:
            todo.append(pmid)
    print(
        f"[info] already in batch003 cache: {skipped_already_cached} "
        f"(defensive — expected ~0)"
    )

    # (5) Output cache path — timestamped so we never collide with the existing file.
    GENERATED.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = GENERATED / f"pubmed_abstract_cache_toxicity_round2_{stamp}.json"

    # (6) Idempotence: if this exact file was started by an earlier interrupted run
    # (i.e. same UTC second), pick up where we left off. Also support resuming from
    # any earlier round2 file the user passes via env var OLIGO_RESUME_FROM.
    new_cache: dict[str, dict] = {}
    resume_from = os.environ.get("OLIGO_RESUME_FROM", "").strip()
    if resume_from and Path(resume_from).exists():
        try:
            prev = json.loads(Path(resume_from).read_text(encoding="utf-8"))
            new_cache.update(prev)
            print(f"[info] resumed {len(prev)} entries from {resume_from}")
        except json.JSONDecodeError as exc:
            print(f"[warn] could not resume from {resume_from}: {exc}", file=sys.stderr)
    if out_path.exists():
        try:
            prev = json.loads(out_path.read_text(encoding="utf-8"))
            new_cache.update(prev)
            print(f"[info] resumed {len(prev)} entries from existing {out_path.name}")
        except json.JSONDecodeError:
            pass

    todo = [p for p in todo if p not in new_cache]
    print(f"[info] need to fetch: {len(todo)} PMIDs in batches of {BATCH_SIZE}")

    returned_with_abstract = sum(1 for v in new_cache.values() if v.get("abstract"))
    returned_without_abstract = sum(1 for v in new_cache.values() if not v.get("abstract"))
    network_errors = 0

    # (3,4) Fetch + parse in batches.
    for i in range(0, len(todo), BATCH_SIZE):
        chunk = todo[i : i + BATCH_SIZE]
        batch_no = (i // BATCH_SIZE) + 1
        print(f"[info] batch {batch_no}: fetching {len(chunk)} PMIDs "
              f"(progress {i}/{len(todo)})")
        parsed, err = fetch_batch(chunk)
        if err:
            network_errors += 1
            print(f"[error] batch {batch_no} failed permanently: {err}", file=sys.stderr)
        # Even if some PMIDs are missing from the response (efetch sometimes drops a few),
        # we record every PMID we asked for. Missing → empty abstract, counted as no_abstract.
        for pmid in chunk:
            text = parsed.get(pmid, "")
            new_cache[pmid] = {"abstract": text}
            if text:
                returned_with_abstract += 1
            else:
                returned_without_abstract += 1
        # Persist after every batch so an interrupted run can resume.
        out_path.write_text(
            json.dumps(new_cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        time.sleep(SLEEP_BETWEEN_BATCHES)

    # (6) Final headcount report.
    n_in_cache = len(new_cache)
    n_with = sum(1 for v in new_cache.values() if v.get("abstract"))
    n_without = n_in_cache - n_with

    print("=" * 70)
    print(f"requested:                {requested}")
    print(f"skipped (already cached): {skipped_already_cached}")
    print(f"newly cached PMIDs:       {n_in_cache}")
    print(f"  - with abstract:        {n_with}")
    print(f"  - no_abstract:          {n_without}")
    print(f"network errors (batches): {network_errors}")
    print(f"output cache:             {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
