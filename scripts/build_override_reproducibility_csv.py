"""Build the human override reproducibility CSV (n=2,003) requested by NAR Referee 2.

Joins:
  - data/generated/v2_offtarget_review_final.csv  (565 rows)
  - data/generated/v2_toxicity_review_final.csv   (1,438 rows)
  - data/oligosafety.db (live tables + curation_audit)

Output:
  04_delivery/v2_human_override_decisions.csv

Columns:
  candidate_id, entity_table, entity_id, pmid, doi, source_location,
  v1_keyword_decision, v2_llm_proposal, human_decision, human_grade,
  is_observed_experimental, is_computational_prediction,
  current_validation_status, curator_id

Notes
-----
v1_keyword_decision is always 'accept' for the 2,003 candidates because each
row in the two review CSVs corresponds to an entity v1 had already promoted
into the release DB; the v2 LLM + human pass re-curates exactly that set.

For rows that human_decision='reject', the live entity row has been deleted
(see apply_recuration_verdicts.py); for those rows source_location is taken
from v1_claimed_location in the review CSV and is_observed_experimental /
is_computational_prediction are left empty (cannot be reconstructed without
the pre-recuration DB snapshot beyond what's already in /data/generated).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

REPO = Path(r"C:/Users/Jie/Desktop/NAR_OligoSafetyDB/repo_ready")
OFF_CSV = REPO / "data/generated/v2_offtarget_review_final.csv"
TOX_CSV = REPO / "data/generated/v2_toxicity_review_final.csv"
DB_PATH = REPO / "data/oligosafety.db"
OUT_CSV = REPO / "04_delivery/v2_human_override_decisions.csv"


def load_reviews() -> pd.DataFrame:
    off = pd.read_csv(OFF_CSV)
    tox = pd.read_csv(TOX_CSV)
    df = pd.concat([off, tox], ignore_index=True)
    # canonicalize
    df["v1_keyword_decision"] = "accept"  # all 2,003 were promoted by v1
    df["v2_llm_proposal"] = df["v2_proposed_decision"].str.lower().str.strip()
    df["human_decision"] = df["human_decision"].str.lower().str.strip()
    df["human_grade"] = df["human_evidence_grade"]
    return df


def load_db_lookups() -> tuple[dict, dict, dict, dict]:
    """Return four dicts keyed by (entity_table, entity_id):
       - source_location, is_observed_experimental, is_computational_prediction,
         current_validation_status (from latest ni_jie audit row).
       Also a (pmid -> doi) map from source_document.
    """
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    src_loc, is_obs, is_comp = {}, {}, {}
    for tbl in ("offtarget_evidence", "toxicity_endpoint"):
        for row in cur.execute(f"SELECT id, source_location, is_observed_experimental FROM {tbl}"):
            ent_id, loc, obs = row
            src_loc[(tbl, ent_id)] = loc
            is_obs[(tbl, ent_id)] = obs
        if tbl == "offtarget_evidence":
            for row in cur.execute(f"SELECT id, is_computational_prediction FROM {tbl}"):
                ent_id, comp = row
                is_comp[("offtarget_evidence", ent_id)] = comp

    # latest validation_status per (entity_table, entity_id) for curator_id='ni_jie'
    status = {}
    for row in cur.execute(
        """
        SELECT entity_table, entity_id, validation_status, audited_at
          FROM curation_audit
         WHERE curator_id='ni_jie'
           AND entity_table IN ('offtarget_evidence','toxicity_endpoint')
        """
    ):
        et, eid, vs, ts = row
        key = (et, eid)
        prev = status.get(key)
        if prev is None or ts > prev[1]:
            status[key] = (vs, ts)
    status = {k: v[0] for k, v in status.items()}

    # pmid -> doi
    pmid_to_doi = {}
    for row in cur.execute(
        "SELECT pmid, doi FROM source_document WHERE pmid IS NOT NULL AND doi IS NOT NULL"
    ):
        pmid, doi = row
        if pmid and doi:
            pmid_to_doi.setdefault(str(pmid), doi)
    con.close()
    return src_loc, is_obs, is_comp, status, pmid_to_doi  # type: ignore[return-value]


def main() -> None:
    df = load_reviews()
    src_loc, is_obs, is_comp, status, pmid_to_doi = load_db_lookups()

    rows = []
    for i, r in df.iterrows():
        et = r["entity_table"]
        eid = int(r["entity_id"])
        key = (et, eid)
        # DOI: prefer the value already in the review CSV; fall back to source_document via pmid
        doi = r.get("doi") if isinstance(r.get("doi"), str) and r.get("doi") else ""
        if not doi and pd.notna(r.get("pmid")):
            doi = pmid_to_doi.get(str(int(r["pmid"])), "") if pd.notna(r["pmid"]) else ""

        # source_location: live DB if still present, else v1_claimed_location
        loc = src_loc.get(key)
        if not loc:
            loc = r.get("v1_claimed_location") or ""

        # observed / computational flags: only available for entities still in live tables (accepted)
        obs_flag = is_obs.get(key, "")
        if et == "offtarget_evidence":
            comp_flag = is_comp.get(key, "")
        else:
            comp_flag = ""  # toxicity has no such field

        validation = status.get(key, "")
        rows.append(
            {
                "candidate_id": f"{et}:{eid}",
                "entity_table": et,
                "entity_id": eid,
                "pmid": int(r["pmid"]) if pd.notna(r["pmid"]) else "",
                "doi": doi,
                "source_location": loc,
                "v1_keyword_decision": r["v1_keyword_decision"],
                "v2_llm_proposal": r["v2_llm_proposal"],
                "human_decision": r["human_decision"],
                "human_grade": r["human_grade"] if pd.notna(r["human_grade"]) else "",
                "is_observed_experimental": obs_flag,
                "is_computational_prediction": comp_flag,
                "current_validation_status": validation,
                "curator_id": "ni_jie",
            }
        )

    out = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)

    # --- sanity / headcount ---
    print(f"Wrote {OUT_CSV}  rows={len(out)}")
    assert len(out) == 2003, f"expected 2003 rows, got {len(out)}"

    def n(mask):
        return int(mask.sum())

    v2 = out["v2_llm_proposal"]
    hd = out["human_decision"]
    print(f"  v2=accept   & human=reject  -> {n((v2=='accept')&(hd=='reject'))}  (target 20)")
    print(f"  v2=reject   & human=accept  -> {n((v2=='reject')&(hd=='accept'))}  (target 7)")
    print(f"  v2=abstain  & human=accept  -> {n((v2=='abstain')&(hd=='accept'))}  (target 33)")
    print(f"  v2=abstain  & human=reject  -> {n((v2=='abstain')&(hd=='reject'))}")
    print(f"  v2=accept   & human=accept  -> {n((v2=='accept')&(hd=='accept'))}")
    print(f"  v2=reject   & human=reject  -> {n((v2=='reject')&(hd=='reject'))}")
    print(f"  total LLM-vs-human flips (v2!=human, excl abstain) -> "
          f"{n(((v2=='accept')&(hd=='reject'))|((v2=='reject')&(hd=='accept')))}  (target 27)")
    print(f"  abstain count -> {n(v2=='abstain')}  (target 92? -- per stat 33 abstain->accept)")

    # empty-cell flags
    for col in ("doi", "source_location", "is_observed_experimental",
                "is_computational_prediction", "current_validation_status"):
        empties = (out[col].isna() | (out[col].astype(str).str.strip() == "")).sum()
        print(f"  empty {col}: {int(empties)}")

    # per-table breakdown
    print("\n  by entity_table x human_decision:")
    print(out.groupby(["entity_table", "human_decision"]).size())

    print("\n  by current_validation_status:")
    print(out["current_validation_status"].value_counts(dropna=False))


if __name__ == "__main__":
    main()
