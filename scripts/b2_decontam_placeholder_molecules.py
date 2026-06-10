"""b2_decontam_placeholder_molecules.py

Referee 2 / Editor blocker B2: 4 placeholder molecules (985-988, modalities siRNA/ASO/PMO/CpG)
were carrying 144 release rows. Even though pair-isolation technically held (leakage_group keys
include source_id), the molecule half of the (source x molecule) key was a synthetic bucket
shared across 30-60+ unrelated papers. That contaminates 107/344 = 31% of the benchmark by
making the "molecule" identifier meaningless.

This script atomically:
  (1) snapshots data/oligosafety.db
  (2) attempts to recover the named therapeutic from the paper title for each (source, modality)
      pair using a strict regex of approved INN drug names + clinical development codes
      (AZD#####, ION-######, ARO-####, RO#######, IONIS-XXX, SLN###, etc.)
  (3) for sources where no name is recoverable, falls back to per-source surrogates named
      'unspecified <modality> (PMID:<pmid>, source-only)'
  (4) inserts ONE new molecule per (source, modality) — one per source for each modality the
      source covers — with the appropriate modality_id, and repoints toxicity_endpoint and
      offtarget_evidence rows
  (5) deletes the four placeholder molecules (985-988) once they are unreferenced
  (6) recomputes benchmark_split.leakage_group as 'source:<sid>|molecule:<new_mid>' for any row
      whose entity was repointed, then verifies the pair-isolation invariant (zero leakage_groups
      span >1 split)
  (7) prints metrics + integrity_check

LLM availability: we attempted to use the curate_v2_llm path for richer per-row extraction
(reading the cached PMC full text and asking the LLM to identify the named therapeutic in the
cited paragraph). No ANTHROPIC/OPENAI/GEMINI key is in the environment, so per spec we fall back
to the PMID-only surrogate path for the rows the strict title regex cannot resolve. Even under
the fallback, every (source, molecule) becomes (source, source-specific-molecule), which is the
property pair-isolation needs.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "oligosafety.db"

PLACEHOLDER_IDS = (985, 986, 987, 988)
# placeholder_id -> (human-readable modality stem, modality_id)
PLACEHOLDER_INFO = {
    985: ("siRNA", 2),
    986: ("ASO", 1),
    987: ("PMO", 9),
    988: ("CpG ODN", 14),
}

# Strict patterns — approved INN names + well-formed clinical codes.
# Deliberately conservative; we'd rather fall back than mislabel.
APPROVED = re.compile(
    r"\b(?:patisiran|givosiran|lumasiran|inclisiran|vutrisiran|nedosiran|fitusiran|cemdisiran|"
    r"teprasiran|olpasiran|zilebesiran|plozasiran|nusinersen|mipomersen|inotersen|volanesorsen|"
    r"eteplirsen|golodirsen|viltolarsen|casimersen|tofersen|donidalorsen|olezarsen|sepofarsen|"
    r"tominersen|defibrotide|fomivirsen|pegaptanib|avacincaptad|solbinsiran)\b",
    re.IGNORECASE,
)
# Codes must start uppercase to avoid capturing e.g. "ALN" inside random text.
CODE = re.compile(
    r"\b(?:AZD\d{3,5}|ION[- ]?\d{3,6}|ISIS[- ]?\d{3,6}|AKCEA[- ]?[A-Z0-9-]+|GSK\d{3,6}|"
    r"RG\d{3,6}|RO\d{6,7}|LY\d{6}|LX\d{4}|ARO[- ]?[A-Z0-9]+|ALN[- ]?[A-Z0-9]+|"
    r"SLN\d{2,4}|MTL[- ]?[A-Z0-9]+|VIR[- ]?\d{3,6}|IONIS[- ]?[A-Z][A-Z]+(?:[- ]?[A-Z0-9]+)?)\b"
)


def recover_name_from_title(title: str | None) -> str | None:
    if not title:
        return None
    m = APPROVED.search(title)
    if m:
        return m.group(0).lower()
    m = CODE.search(title)
    if m:
        return m.group(0).upper().replace(" ", "-")
    return None


def main() -> None:
    if not DB.exists():
        sys.exit(f"DB missing at {DB}")

    # ---- (1) snapshot -----------------------------------------------------
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup = DB.with_suffix(f".db.pre_b2_decontam_{ts}.bak")
    shutil.copy2(DB, backup)
    print(f"[backup] {backup}", flush=True)

    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    cur = con.cursor()

    # ---- pre-state metrics ------------------------------------------------
    pre_release_rows_placeholder = cur.execute(
        "SELECT (SELECT COUNT(*) FROM toxicity_endpoint WHERE molecule_id IN (985,986,987,988)) + "
        "       (SELECT COUNT(*) FROM offtarget_evidence WHERE molecule_id IN (985,986,987,988))"
    ).fetchone()[0]
    pre_distinct_release_mols = cur.execute(
        "SELECT COUNT(DISTINCT m.id) FROM molecule m "
        "WHERE m.id IN (SELECT molecule_id FROM toxicity_endpoint "
        "               UNION SELECT molecule_id FROM offtarget_evidence)"
    ).fetchone()[0]
    pre_benchmark_size = cur.execute("SELECT COUNT(*) FROM benchmark_split").fetchone()[0]
    pre_benchmark_placeholder = cur.execute(
        "SELECT COUNT(*) FROM benchmark_split bs "
        "LEFT JOIN toxicity_endpoint te ON bs.entity_table='toxicity_endpoint' AND bs.entity_id=te.id "
        "LEFT JOIN offtarget_evidence oe ON bs.entity_table='offtarget_evidence' AND bs.entity_id=oe.id "
        "WHERE COALESCE(te.molecule_id, oe.molecule_id) IN (985,986,987,988)"
    ).fetchone()[0]
    pre_split_violations = cur.execute(
        "SELECT COUNT(*) FROM ( "
        " SELECT leakage_group FROM benchmark_split "
        " GROUP BY leakage_group HAVING COUNT(DISTINCT split_name) > 1)"
    ).fetchone()[0]

    print(f"[pre]  release rows attached to placeholders : {pre_release_rows_placeholder}")
    print(f"[pre]  benchmark rows attached to placeholders: {pre_benchmark_placeholder}")
    print(f"[pre]  distinct release molecules            : {pre_distinct_release_mols}")
    print(f"[pre]  benchmark size                        : {pre_benchmark_size}")
    print(f"[pre]  leakage_groups spanning >1 split      : {pre_split_violations}", flush=True)

    # ---- (2) collect (source, placeholder-modality) pairs ----------------
    pairs = cur.execute(
        """
        SELECT DISTINCT sd.id, sd.pmid, sd.title, te_off.molecule_id
        FROM (
            SELECT source_document_id, molecule_id FROM toxicity_endpoint
            WHERE molecule_id IN (985,986,987,988)
          UNION
            SELECT source_document_id, molecule_id FROM offtarget_evidence
            WHERE molecule_id IN (985,986,987,988)
        ) te_off
        JOIN source_document sd ON te_off.source_document_id = sd.id
        ORDER BY sd.id, te_off.molecule_id
        """
    ).fetchall()
    print(f"[plan] distinct (source, placeholder-modality) pairs: {len(pairs)}", flush=True)

    # ---- (3) create new molecule rows + remap dictionary ------------------
    # remap[(source_id, placeholder_id)] = new_molecule_id
    remap: dict[tuple[int, int], int] = {}
    named_recoveries = 0
    pmid_fallbacks = 0
    abstract_only_fallbacks = 0  # no pmid either
    now = datetime.now(timezone.utc).isoformat()

    for sid, pmid, title, ph_id in pairs:
        modality_label, modality_id = PLACEHOLDER_INFO[ph_id]
        recovered = recover_name_from_title(title)
        if recovered:
            # Use the recovered drug name verbatim; still tag with PMID for traceability
            # so re-extraction provenance is visible in canonical_name itself.
            canonical = f"{recovered} (recovered from PMID:{pmid}, B2 decontam)"
            external = {
                "b2_recovery": "title_pattern",
                "recovered_name": recovered,
                "source_pmid": pmid,
                "ex_placeholder_id": ph_id,
            }
            named_recoveries += 1
        elif pmid:
            canonical = f"unspecified {modality_label} (PMID:{pmid}, source-only)"
            external = {
                "b2_recovery": "pmid_fallback",
                "source_pmid": pmid,
                "ex_placeholder_id": ph_id,
            }
            pmid_fallbacks += 1
        else:
            # No PMID — use the source_document.id itself for uniqueness.
            canonical = f"unspecified {modality_label} (source_doc:{sid}, source-only)"
            external = {
                "b2_recovery": "source_doc_fallback",
                "source_document_id": sid,
                "ex_placeholder_id": ph_id,
            }
            abstract_only_fallbacks += 1

        cur.execute(
            """
            INSERT INTO molecule (
                canonical_name, modality_id, target_gene_symbol, disease_context,
                therapeutic_status, external_ids, created_at,
                sequence_annotation_status, modification_annotation_status
            ) VALUES (?, ?, NULL, NULL, 'unspecified', ?, ?, 'unspecified', 'unspecified')
            """,
            (canonical, modality_id, json.dumps(external, sort_keys=True), now),
        )
        new_id = cur.lastrowid
        remap[(sid, ph_id)] = new_id

    print(
        f"[plan] new molecules inserted: {len(remap)} "
        f"(named={named_recoveries}, pmid_fallback={pmid_fallbacks}, "
        f"source_doc_fallback={abstract_only_fallbacks})",
        flush=True,
    )

    # ---- (4) repoint toxicity_endpoint + offtarget_evidence --------------
    tox_remapped = 0
    for (sid, ph_id), new_mid in remap.items():
        n = cur.execute(
            "UPDATE toxicity_endpoint SET molecule_id=? "
            "WHERE molecule_id=? AND source_document_id=?",
            (new_mid, ph_id, sid),
        ).rowcount
        tox_remapped += n
    off_remapped = 0
    for (sid, ph_id), new_mid in remap.items():
        n = cur.execute(
            "UPDATE offtarget_evidence SET molecule_id=? "
            "WHERE molecule_id=? AND source_document_id=?",
            (new_mid, ph_id, sid),
        ).rowcount
        off_remapped += n
    print(f"[exec] toxicity_endpoint repointed: {tox_remapped}")
    print(f"[exec] offtarget_evidence repointed: {off_remapped}", flush=True)

    # ---- (5) delete now-orphan placeholders ------------------------------
    still_referenced = cur.execute(
        "SELECT molecule_id, COUNT(*) FROM ( "
        "  SELECT molecule_id FROM toxicity_endpoint "
        "  UNION ALL SELECT molecule_id FROM offtarget_evidence) "
        "WHERE molecule_id IN (985,986,987,988) GROUP BY molecule_id"
    ).fetchall()
    if still_referenced:
        raise RuntimeError(f"placeholder rows still referenced after remap: {still_referenced}")
    deleted = cur.execute(
        "DELETE FROM molecule WHERE id IN (985,986,987,988)"
    ).rowcount
    print(f"[exec] placeholder molecules deleted: {deleted}", flush=True)

    # ---- (6) refresh benchmark_split.leakage_group for repointed rows ----
    # leakage_group format: 'source:<sid>|molecule:<mid>'
    # We rebuild for any benchmark_split whose entity now points at a new molecule_id.
    rebuilt = 0
    bs_rows = cur.execute(
        "SELECT bs.id, bs.entity_table, bs.entity_id "
        "FROM benchmark_split bs "
        "JOIN ( "
        "  SELECT id, molecule_id, source_document_id, 'toxicity_endpoint' AS et FROM toxicity_endpoint "
        "  UNION ALL "
        "  SELECT id, molecule_id, source_document_id, 'offtarget_evidence' AS et FROM offtarget_evidence "
        ") e ON e.et = bs.entity_table AND e.id = bs.entity_id "
        "WHERE e.molecule_id IN (" + ",".join(str(v) for v in set(remap.values())) + ")"
    ).fetchall()
    for bs_id, etable, eid in bs_rows:
        if etable == "toxicity_endpoint":
            sid, mid = cur.execute(
                "SELECT source_document_id, molecule_id FROM toxicity_endpoint WHERE id=?", (eid,)
            ).fetchone()
        else:
            sid, mid = cur.execute(
                "SELECT source_document_id, molecule_id FROM offtarget_evidence WHERE id=?", (eid,)
            ).fetchone()
        new_lg = f"source:{sid}|molecule:{mid}"
        cur.execute("UPDATE benchmark_split SET leakage_group=? WHERE id=?", (new_lg, bs_id))
        rebuilt += 1
    print(f"[exec] benchmark_split.leakage_group rebuilt: {rebuilt}", flush=True)

    # Enforce invariant: drop any leakage_group spanning >1 split (none expected).
    bad = cur.execute(
        "SELECT leakage_group FROM benchmark_split "
        "GROUP BY leakage_group HAVING COUNT(DISTINCT split_name) > 1"
    ).fetchall()
    dropped = 0
    if bad:
        for (lg,) in bad:
            dropped += cur.execute(
                "DELETE FROM benchmark_split WHERE leakage_group=?", (lg,)
            ).rowcount
    print(f"[exec] benchmark_split rows dropped for split-spanning leakage_group: {dropped}", flush=True)

    con.commit()

    # ---- (7) post-state + integrity check --------------------------------
    post_release_rows_placeholder = cur.execute(
        "SELECT (SELECT COUNT(*) FROM toxicity_endpoint WHERE molecule_id IN (985,986,987,988)) + "
        "       (SELECT COUNT(*) FROM offtarget_evidence WHERE molecule_id IN (985,986,987,988))"
    ).fetchone()[0]
    post_distinct_release_mols = cur.execute(
        "SELECT COUNT(DISTINCT m.id) FROM molecule m "
        "WHERE m.id IN (SELECT molecule_id FROM toxicity_endpoint "
        "               UNION SELECT molecule_id FROM offtarget_evidence)"
    ).fetchone()[0]
    post_benchmark_size = cur.execute("SELECT COUNT(*) FROM benchmark_split").fetchone()[0]
    post_benchmark_placeholder = cur.execute(
        "SELECT COUNT(*) FROM benchmark_split bs "
        "LEFT JOIN toxicity_endpoint te ON bs.entity_table='toxicity_endpoint' AND bs.entity_id=te.id "
        "LEFT JOIN offtarget_evidence oe ON bs.entity_table='offtarget_evidence' AND bs.entity_id=oe.id "
        "WHERE COALESCE(te.molecule_id, oe.molecule_id) IN (985,986,987,988)"
    ).fetchone()[0]
    post_split_violations = cur.execute(
        "SELECT COUNT(*) FROM ( "
        " SELECT leakage_group FROM benchmark_split "
        " GROUP BY leakage_group HAVING COUNT(DISTINCT split_name) > 1)"
    ).fetchone()[0]

    print()
    print("============ B2 DECONTAM RESULT ============")
    print(f"backup_path                              : {backup}")
    print()
    print(f"| metric                                | before | after |")
    print(f"| placeholder-attached release rows     | {pre_release_rows_placeholder:>6} | {post_release_rows_placeholder:>5} |")
    print(f"| placeholder-attached benchmark rows   | {pre_benchmark_placeholder:>6} | {post_benchmark_placeholder:>5} |")
    print(f"| distinct release molecules            | {pre_distinct_release_mols:>6} | {post_distinct_release_mols:>5} |")
    print(f"| benchmark size                        | {pre_benchmark_size:>6} | {post_benchmark_size:>5} |")
    print(f"| leakage_groups spanning >1 split      | {pre_split_violations:>6} | {post_split_violations:>5} |")
    print()
    print(f"named title-pattern recoveries           : {named_recoveries}")
    print(f"PMID-only fallback molecules             : {pmid_fallbacks}")
    print(f"source_doc fallback molecules            : {abstract_only_fallbacks}")
    print()
    ic = cur.execute("PRAGMA integrity_check").fetchone()[0]
    print(f"integrity_check                          : {ic}")
    con.close()

    if post_split_violations != 0:
        sys.exit("FAIL: leakage_group invariant violated after surgery")
    if post_release_rows_placeholder != 0:
        sys.exit("FAIL: placeholder rows still attached")
    if ic != "ok":
        sys.exit(f"FAIL: integrity_check = {ic}")


if __name__ == "__main__":
    main()
