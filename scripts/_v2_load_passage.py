"""Helper for the v2 re-curation demo workflow: load one input row by sid and print the
source passage (cached PMC full text preferred, else PubMed abstract). Reuses the production
loaders in curate_v2_llm so the demo and the production script see identical passages.

Usage:  python scripts/_v2_load_passage.py <sid> <input_jsonl_path>
"""
from __future__ import annotations

import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from curate_v2_llm import pmc_text, load_abstract_cache  # noqa: E402


def main() -> None:
    sid = int(sys.argv[1])
    path = sys.argv[2]
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    row = next(x for x in rows if x["sid"] == sid)
    ft = pmc_text(row.get("pmcid", ""))
    if ft:
        passage, kind = ft, "pmc_full_text"
    else:
        ab = load_abstract_cache()
        passage = (ab.get(str(row.get("pmid", "")), {}) or {}).get("abstract", "")
        kind = "pubmed_abstract" if passage else "none"
    keep = ("sid", "entity_id", "entity_table", "domain", "molecule",
            "claimed_evidence_type", "v1_grade", "claimed_location", "pmid", "pmcid", "title")
    out = {k: row.get(k) for k in keep}
    out["passage_kind"] = kind
    out["passage"] = passage[:48000]
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
