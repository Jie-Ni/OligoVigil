# Supplementary Materials

**OligoVigil: a curator-verified, source-anchored database of safety and off-target evidence for therapeutic oligonucleotides**

*Author information removed for blinded review*

*Current release snapshot: 737 curator-verified evidence records (626 toxicity and 111 off-target) from 660 primary sources. All current release counts were re-verified against `data/oligosafety.db` on 2026-06-10.*

## Supplementary contents

- **S1:** Full curation protocol and grounding gate.
- **S2:** Database schema and candidate-to-release firewall.
- **S3:** Comparator matrix.
- **S4:** Deterministic benchmark baselines.
- **S5:** Proposal-to-human decision provenance.
- **S6:** Backup chain and source-license/reuse classifications.
- **S7:** Excluded and residual-record inventory.
- **S8:** Closest-work feature audit underlying Figure 5.

---

## S1. Curation protocol — full v2 curator rubric

This is the verbatim curator-rubric prompt used by the v2 source-grounded LLM pre-curator (`scripts/curate_v2_llm.py`). It is reproduced exactly as implemented in the curator system prompt, with the four gates that the manuscript Methods Stage 3 summarises in plain English. The grounding gate is enforced **in code** (see snippet at the bottom of this section): an LLM accept whose `grounding_quote` is not a verbatim substring of the supplied passage is forced to a reject.

> *Curator system message (verbatim from `curate_v2_llm.py`):*
>
> You are a strict curator for OligoVigil, a database of curator-reviewed THERAPEUTIC oligonucleotide (ASO / siRNA / PMO / LNA / gapmer / morpholino / aptamer / GalNAc-siRNA) SAFETY and OFF-TARGET evidence. You read one source passage and decide whether it contains primary evidence that belongs in the database. You are conservative: when the passage does not clearly support an accept, you reject or abstain. You never invent content; every accept must quote an exact verbatim span of the supplied passage.

> *Curator rubric (verbatim from `curate_v2_llm.py`):*
>
> Decide ACCEPT only if ALL of the following hold, judged strictly from the SUPPLIED PASSAGE (not outside knowledge):
>
> **GATE 1 — MOLECULE IN SCOPE (exclusion-first).** A therapeutic oligonucleotide must be the agent UNDER STUDY: antisense oligonucleotide / ASO / gapmer / siRNA / RNAi therapeutic / morpholino (PMO) / LNA / aptamer / GalNAc-siRNA, or a delivery vehicle carrying such an oligo. REJECT if the agent is: CRISPR/Cas, shRNA, AAV/viral gene therapy, mRNA therapeutic, endogenous lncRNA/circRNA/miRNA biology, a small molecule / natural product / TCM, a G-quadruplex small-molecule ligand, agricultural/insect/nematode RNAi, or an oligo used merely as a lab knockdown TOOL rather than as the therapeutic under study. Disambiguate acronyms by sense: "ASO" must mean antisense oligonucleotide here, NOT atrial septal occluder, arteriosclerosis obliterans, or the journal Annals of Surgical Oncology; "mismatch" must mean oligo hybridization mismatch, NOT dMMR/MSI-H tumor status.
>
> **GATE 2 — PRIMARY RESULT.** The passage must report an actually observed/measured/administered result. REJECT background, introduction, motivation/hypothesis, methods/protocol descriptions, prior-work recaps, and review/meta-analysis/guidance text.
>
> **GATE 3 — EVIDENCE TYPE MATCHES DOMAIN.** First classify the evidence type, then require it to match the requested domain:
>   - *toxicity domain:* ACCEPT only a safety/tolerability/toxicity endpoint (hepatic, renal, platelet, immune/cytokine/complement, hemolysis, cell-viability/cytotoxicity, genotoxicity, body weight, mortality, adverse events) LINKED to the oligo or its delivery product. REJECT if the evidence type is efficacy / target knockdown potency / pharmacokinetics / biodistribution / on-target activity, or if the toxicity belongs to an external toxin or disease-injury model where the oligo is only a knockdown tool, or if "cytotoxicity" is a cancer-cell-killing efficacy readout.
>   - *offtarget domain:* ACCEPT only an OBSERVED unintended-effect result: seed-mediated, mismatch/hybridization-dependent, transcriptome-wide, RNA-seq, or microarray off-target evidence. REJECT computational/design-only specificity screens, PK/biodistribution, and on-target/efficacy "specificity".
>
> **GATE 4 — GROUNDING.** Provide grounding_quote: an EXACT verbatim span copied from the supplied passage that simultaneously establishes the in-scope oligo and the domain-matched primary result. If no single passage supports the accept, set grounding_quote to "NONE" and do not accept.
>
> If the passage is too truncated/ambiguous to apply the gates, set decision="abstain".
>
> **GRADE** (only when decision=accept): A = full-text Results/Figure/Table/Supplement section AND a NAMED therapeutic oligo AND correct evidence type; B = therapeutic oligo but abstract-only or weaker location; C = in-scope but generic/unnamed oligo or weak support.

### S1.1 Grounding-gate enforcement (verbatim Python from `scripts/curate_v2_llm.py`)

```python
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
```

The check is intentionally strict: whitespace is collapsed, comparison is case-insensitive, and a minimum 12-character quote is required. An LLM that confabulates a rationale cannot pass this gate, because no such verbatim span exists in the cached source.

### S1.2 Stage 3 human-adjudication contract

The LLM **never** writes to `curation_audit.curator_id`, `curator_decision`, or `validation_status='curator_verified'`. The downstream promoter (`scripts/promote_curator_review.py`) hard-requires `validation_status='curator_verified'`, so no machine output can reach the release tables without a human accept. The sole human curator adjudicated each LLM proposal row by row.

---

## S2. Database schema (text tree)

The release schema is the single SQLite file `data/oligosafety.db` (full DDL at `data/schema_sqlite.sql`). The text-tree below shows the in-scope tables and the foreign-key paths a downstream user follows from a primary source to released evidence; `curation_audit` is shown on the side as it cross-references every other table by `(entity_table, entity_id)`.

```
source_document  (36,245 rows; PMID / PMCID / DOI / title / venue / license)
   |
   v
curation_queue  (70,283 rows; per-(source, evidence_domain) task)
   |
   v
curation_candidate  (41,114 rows; matched_terms / source_location / status
                     in { machine_precurated_v1,
                          candidate_needs_curator_review,
                          curator_rejected,
                          recurated_rejected })
   |
   +--> toxicity_endpoint   (release: 626 curator-verified rows)
   |        molecule_id  --> molecule
   |        assay_id     --> assay
   |        source_document_id --> source_document
   |        endpoint_name / endpoint_category / direction /
   |        significance_label / is_observed_experimental /
   |        source_location / evidence_grade
   |
   +--> offtarget_evidence  (release: 111 curator-verified rows)
            molecule_id  --> molecule
            assay_id     --> assay
            source_document_id --> source_document
            offtarget_gene_symbol / offtarget_transcript_id /
            evidence_type / match_type / seed_match_length /
            is_observed_experimental / is_computational_prediction /
            source_location / evidence_grade

molecule         (1,012 rows in the current molecule table)
   modality_id  --> modality   (e.g., ASO, siRNA, PMO, CpG ODN, aptamer)
   canonical_name / target_gene_symbol / disease_context /
   therapeutic_status / external_ids /
   sense_sequence / antisense_sequence / guide_sequence /
   passenger_sequence / seed_region /
   backbone_chemistry / sugar_modification / base_modification /
   conjugate_delivery /
   sequence_annotation_status / modification_annotation_status

assay            (per-experiment context: species, route, dose, duration)
modality         (controlled vocabulary; in_core_scope flag)

benchmark_split  (344 rows; task_name {toxicity_safety_v0_1, offtarget_safety_v0_1};
                  split_name {train, validation, test};
                  entity_table + entity_id -> toxicity_endpoint / offtarget_evidence;
                  split_strategy = 'source_plus_molecule_grouped_*';
                  leakage_group keyed at (source_id, molecule_id) pair)

---- audit cross-cut ---------------------------------------------
curation_audit   (one row per curator decision)
   entity_table   { 'toxicity_endpoint' | 'offtarget_evidence' | 'curation_candidate' }
   entity_id      (FK into the addressed table)
   validation_status
     { 'curator_verified'        -- 737 current release rows
     , 'curator_rejected'        -- 28,908 rows (mixed source)
     , 'machine_precurated_v1'   -- 1,983 historical rows (never released)
     , 'recurated_rejected'      -- 1,345 rows (demoted after source review)
     , 'verified'                -- 3 rows, editorial_seed_nonhuman }
   curator_decision  { 'accept' | 'reject' | NULL for machine rows }
   curator_id        { human curator id | 'machine_v1_keyword_classifier' |
                       'editorial_seed_nonhuman' | NULL }
   audit_note / audited_at
```

The candidate-to-release firewall is enforced by:

1. status enums (`machine_precurated_v1` is never `'curator_verified'`),
2. the `promote_curator_review.py` precondition (only `'curator_verified'` rows enter the release tables), and
3. an automated QA assertion in `scripts/final_delivery_check.py` that every release row has a matching `validation_status='curator_verified'` audit by a human curator id.

---

\clearpage

## S3. Comparator matrix

| Dimension | theRNA (NAR 2026) | siRNAEfficacyDB (IET 2024) | CMsiRNAdb (BMC 2026) | siRNAmod (Scientific Reports 2016) | CRISPRoffT (NAR 2025) | **OligoVigil (this work)** |
| --- | --- | --- | --- | --- | --- | --- |
| Primary scope | Broad functional RNA therapeutics catalogue | siRNA on-target silencing efficacy | Chemically modified siRNA efficacy | Chemically modified siRNA catalogue (efficacy) | CRISPR/Cas guide off-targets (different molecular class) | **Safety + off-target evidence for therapeutic oligonucleotides (ASO / siRNA / PMO / LNA / aptamer / GalNAc-siRNA)** |
| Evidence type | Curated efficacy entries | Silencing efficacy measurements | Modification-aware efficacy | Modification annotations + efficacy | Off-target observations for Cas9/Cas12 | **Observed safety endpoints + observed off-target results (737/737 observed experimental rows)** |
| Source anchoring (exact in-source location) | Reference-level | Reference-level | Reference-level | Reference-level | Reference-level | **Source-localised: section / figure / table / paragraph captured per release row; 74.2% (547/737) full-text PMC-anchored; 100% PMID, 99.5% DOI** |
| Audit trail (machine-vs-human separation) | Not provided | Not provided | Not provided | Not provided | Not provided | **Three-stage pipeline: candidate → v1 machine pre-curation → v2 source-grounded LLM proposal → single-human accept/reject + grade; full `curation_audit` table downloadable; 1,345 demoted candidates retained as `recurated_rejected`** |
| Benchmark splits | Not provided | Not provided | Not provided | Not provided | Not provided | **344 Grade A/B records split 218/23/22 (toxicity) + 66/5/10 (off-target); `source_plus_molecule_grouped_*` strategy; 4 deterministic prior baselines provided** |
| No-login web access | Browser UI (catalogue) | Browser UI | Browser UI | Browser UI | Browser UI | **No-login portal + documented REST API + OpenAPI + MCP server + `llms.txt` + Bioschemas JSON-LD + W3C PROV; bulk CSV/ZIP downloads** |

**Bottom line:** none of the comparators ship a curator-verified, source-anchored, graded, audited safety/off-target evidence layer with a leakage-aware benchmark. OligoVigil targets a complementary niche to all five.

---

## S4. Reproducibility — deterministic prior baselines on the fixed splits

Source: `data/generated/benchmark_baseline_results_v1.csv` (16 rows = 4 baselines × 2 tasks × 2 evaluation splits = validation + test). Reproduced verbatim below.

| task_name | baseline_model | split | train n | eval n | majority_label | majority_frac_train | accuracy | macro-F1 | coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| offtarget_safety_v0_1 | train_majority_class | validation | 66 | 5 | seed-mediated off-target effect | 0.3788 | 0.2000 | 0.1111 | 1.00 |
| offtarget_safety_v0_1 | modality_prior_class | validation | 66 | 5 | seed-mediated off-target effect | 0.3788 | 0.2000 | 0.1250 | 1.00 |
| offtarget_safety_v0_1 | evidence_grade_prior_class | validation | 66 | 5 | seed-mediated off-target effect | 0.3788 | 0.2000 | 0.1111 | 1.00 |
| offtarget_safety_v0_1 | target_prior_class | validation | 66 | 5 | seed-mediated off-target effect | 0.3788 | 0.2000 | 0.1111 | 1.00 |
| offtarget_safety_v0_1 | train_majority_class | test | 66 | 10 | seed-mediated off-target effect | 0.3788 | 0.4000 | 0.1429 | 1.00 |
| offtarget_safety_v0_1 | modality_prior_class | test | 66 | 10 | seed-mediated off-target effect | 0.3788 | 0.6000 | 0.3667 | 0.90 |
| offtarget_safety_v0_1 | evidence_grade_prior_class | test | 66 | 10 | seed-mediated off-target effect | 0.3788 | 0.4000 | 0.1429 | 1.00 |
| offtarget_safety_v0_1 | target_prior_class | test | 66 | 10 | seed-mediated off-target effect | 0.3788 | 0.4000 | 0.1429 | 0.90 |
| toxicity_safety_v0_1 | train_majority_class | validation | 218 | 23 | hepatic | 0.4954 | 0.6087 | 0.1261 | 1.00 |
| toxicity_safety_v0_1 | modality_prior_class | validation | 218 | 23 | hepatic | 0.4954 | 0.5652 | 0.1204 | 1.00 |
| toxicity_safety_v0_1 | evidence_grade_prior_class | validation | 218 | 23 | hepatic | 0.4954 | 0.6087 | 0.1261 | 1.00 |
| toxicity_safety_v0_1 | target_prior_class | validation | 218 | 23 | hepatic | 0.4954 | 0.6087 | 0.1261 | 0.9565 |
| toxicity_safety_v0_1 | train_majority_class | test | 218 | 22 | hepatic | 0.4954 | 0.6364 | 0.2593 | 1.00 |
| toxicity_safety_v0_1 | modality_prior_class | test | 218 | 22 | hepatic | 0.4954 | 0.6364 | 0.2593 | 0.9545 |
| toxicity_safety_v0_1 | evidence_grade_prior_class | test | 218 | 22 | hepatic | 0.4954 | 0.6364 | 0.2593 | 1.00 |
| toxicity_safety_v0_1 | target_prior_class | test | 218 | 22 | hepatic | 0.4954 | 0.6364 | 0.2593 | 0.7727 |

### S4.1 One-line summary per baseline

- **`train_majority_class`** — predicts the global training-set majority label for every evaluation row. Sanity floor. Coverage 1.00 by construction.
- **`modality_prior_class`** — predicts the training-set majority label *within the evaluation row's modality*; falls back to the global majority when the modality is unseen. Coverage drops below 1.00 only when the held-out test row contains a modality with no training-set support (one off-target test row at coverage 0.90; one toxicity test row at coverage 0.9545).
- **`evidence_grade_prior_class`** — predicts the training-set majority label *within the same evidence grade* (A or B). Acts as a difficulty diagnostic: identical to `train_majority_class` here because the train-set majority label is the same in both grades.
- **`target_prior_class`** — predicts the training-set majority label *within the same target gene symbol*; coverage falls when the test row's target is unseen in training (off-target test 0.90; toxicity test 0.7727), serving as a leakage check.

All four baselines tie at macro-F1 = 0.2593 on the toxicity test set (n=22), reflecting the dominance of the "hepatic" class and the small n; off-target test macro-F1 spans 0.1429–0.3667 (n=10). These are reported only as difficulty diagnostics, not as method benchmarks.

---

## S5. Provenance of `v2_human_override_decisions.csv`

`04_delivery/v2_human_override_decisions.csv` provides the per-candidate decision triple for every row in the v1 pre-curation pool, so the human-vs-model statistics in Methods Stage 3 are reproducible. Schema (14 columns, 2,003 rows):

| column | description |
| --- | --- |
| `candidate_id` | stable id of the v1 candidate (`<entity_table>:<entity_id>`) |
| `entity_table` | `toxicity_endpoint` or `offtarget_evidence` |
| `entity_id` | row id in the addressed release table |
| `pmid` | source PubMed id |
| `doi` | source DOI (99.7% populated) |
| `source_location` | exact in-source pointer (section / paragraph / figure / table) |
| `v1_keyword_decision` | v1 keyword classifier verdict (`accept` / `reject`) |
| `v2_llm_proposal` | v2 source-grounded LLM verdict (`accept` / `reject` / `abstain`) |
| `human_decision` | the curator-of-record's final verdict (`accept` / `reject`) |
| `human_grade` | final grade (A/B/C/NA) — only for accepts |
| `is_observed_experimental` | 0/1, copied from the release table after promotion |
| `is_computational_prediction` | 0/1 (only the single Grade-C off-target row id 156 is 1) |
| `current_validation_status` | `curator_verified` for accepts; `recurated_rejected` for human rejects of v1 accepts; `curator_rejected` for v1 rejects |
| `curator_id` | `[CURATOR]` for every human-touched row |

### S5.1 v2 LLM proposal × human decision cross-tabulation (n = 2,003)

|  | human=accept | human=reject | row total |
| --- | --- | --- | --- |
| **v2=accept** | 618 | **20** | 638 |
| **v2=reject** | **7** | 523 | 530 |
| **v2=abstain** | **33** | 802 | 835 |
| column total | 658 | 1,345 | 2,003 |

**Highlighted cells reproduced exactly:**

- v2 accept × human reject = **20** (over-accepts caught)
- v2 reject × human accept = **7** (over-rejects recovered)
- v2 abstain × human accept = **33** (abstains promoted on reading)

Firm-decision overrides = 20 + 7 = 27 of 1,168 firm calls = **2.3%** divergence (Methods Stage 3). The 33 abstain-to-accept recoveries are reported separately because abstain is the model's explicit "ask a human" signal, not a substantive disagreement.

The historical Stage-3 decision table contains **658 human accepts and 1,345 rejects** from the original 2,003-candidate pool. One computational accept was subsequently removed, leaving 657 rows from that pool; later curator-verified expansion rounds added 80 observed rows, producing the current 737-row release.

### S5.2 Cell-count re-verification command

```python
import csv
from collections import Counter
with open("04_delivery/v2_human_override_decisions.csv", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
c = Counter()
for r in rows:
    c[(r["v2_llm_proposal"], r["human_decision"])] += 1
# Reproduces the table above exactly (2,003 rows, 6 occupied cells).
```

---

## S6. Backup chain — DB integrity restoration points

Each backup is a `.bak` snapshot of `data/oligosafety.db` taken immediately before a curation-integrity edit, so any contested edit can be inspected by diff. Output of `ls data/oligosafety.db.pre_*.bak` (sorted lexicographically; 14 snapshots):

```
data/oligosafety.db.pre_audit_reconcile_20260607_052436.bak
data/oligosafety.db.pre_batch008_20260602.bak
data/oligosafety.db.pre_batch009_mega_fast_20260602.bak
data/oligosafety.db.pre_candidate_enum_20260607_025745.bak
data/oligosafety.db.pre_curator_identity_20260607_032934.bak
data/oligosafety.db.pre_enum_rename_20260606_122249.bak
data/oligosafety.db.pre_enum_rename_20260607_022138.bak
data/oligosafety.db.pre_full_rebuild_20260607_022009.bak
data/oligosafety.db.pre_garbage_molecule_fix_20260607_052332.bak
data/oligosafety.db.pre_status_relabel_20260604.bak
data/oligosafety.db.pre_leakage_relabel_20260607_053524.bak
data/oligosafety.db.pre_recuration_demote_20260606_121506.bak
data/oligosafety.db.pre_recuration_demote_20260606_121512.bak
data/oligosafety.db.pre_recuration_demote_20260607_022035.bak
```

### S6.1 What each backup precedes

- `pre_batch008_20260602.bak`, `pre_batch009_mega_fast_20260602.bak` — pre-batch candidate-ingestion snapshots from the June-02 release-scale pre-curation runs.
- `pre_status_relabel_20260604.bak` — pre-relabel snapshot before the v1 status enum was renamed to make `machine_precurated_v1` distinct from any human verdict.
- `pre_enum_rename_20260606_122249.bak`, `pre_enum_rename_20260607_022138.bak` — pre-rename snapshots for the candidate-status enum normalisations.
- `pre_recuration_demote_20260606_121506.bak`, `pre_recuration_demote_20260606_121512.bak`, `pre_recuration_demote_20260607_022035.bak` — snapshots immediately before the v2+human-driven demotions wrote `validation_status='recurated_rejected'` on the 1,345 unsupported candidates.
- `pre_full_rebuild_20260607_022009.bak` — pre-rebuild snapshot before the 2026-06-07 historical 658-record provisional release.
- `pre_candidate_enum_20260607_025745.bak` — pre-cleanup snapshot before the final candidate-enum migration.
- `pre_curator_identity_20260607_032934.bak` — snapshot taken before the curator-id merge (`[CURATOR]` and `[CURATOR]` collapsed to canonical `[CURATOR]`).
- `pre_garbage_molecule_fix_20260607_052332.bak` — snapshot taken before merging 45 v1-extraction-artefact molecule_ids into 4 placeholder `unspecified <modality>` molecules (S7 item 2).
- `pre_audit_reconcile_20260607_052436.bak` — snapshot before pruning duplicate audit rows and 2 orphan audits, leaving one curator-verified accept audit per then-current release row; the current release contains 737 such audits.
- `pre_leakage_relabel_20260607_053524.bak` — snapshot before re-keying `benchmark_split.leakage_group` to canonical placeholder identifiers and dropping the offending test row from the cross-split (source × molecule) group (Methods, Benchmark construction; S7 item 3).

---

## S6.2 Source-license / reuse-category per-class counts


Query:

```sql
SELECT license_status, reuse_category, COUNT(*) FROM source_document
 GROUP BY license_status, reuse_category ORDER BY 3 DESC;
```

**Table S6.2a — all 36,245 indexed sources:**

| license_status | reuse_category | n |
| --- | --- | --- |
| abstract_metadata_only | derived_annotations_only | 36,238 |
| open_access | query_linkout_only | 3 |
| cc_by_nc_nd | query_linkout_only | 1 |
| official_guideline | derived_annotations_only | 1 |
| official_notice | derived_annotations_only | 1 |
| open_access | derived_annotations_only | 1 |
| **total** | | **36,245** |

**Table S6.2b — 660 current release-anchored sources:**

| license_status | reuse_category | n |
| --- | --- | --- |
| abstract_metadata_only | derived_annotations_only | 660 |
| **total** | | **660** |

Interpretation: the indexed pool is overwhelmingly PubMed-abstract-derived (36,238 / 36,245 = 99.98%) with derived-annotations-only redistribution scope. The 7 exceptions are open-access full-text or official-guideline / official-notice sources that we either link out to or extract under derived-annotations-only terms. **Every release-anchored source falls under `abstract_metadata_only / derived_annotations_only`**, so the entire release rests on the most conservative reuse scope: we do not redistribute raw third-party article text or full-text PDFs; we only store derived annotations (canonical name, endpoint label, evidence grade) and a verbatim grounding-quote span of the length permitted under fair-use / quotation right, together with the exact source location (section / paragraph / figure / table) so users can retrieve the original under their own subscription.


---

## S7. Excluded and residual-record inventory

The current release separates removed rows, residual metadata gaps and benchmark exclusions so that users can reproduce each boundary.

### S7.1 Removed computational off-target row

An earlier release-candidate table contained one Grade-C computational off-target prediction (`offtarget_evidence.id = 156`). It was removed from the release during curation review and was not re-introduced. Consequently, **all 737 current release rows are observed experimental results**.

### S7.2 Residual placeholder molecules

The collaborator B2 recovery pass resolved 110 of 143 v5 placeholder-linked release rows. The current disclosed residual is **31 release rows** on true placeholder or mixed-modality fallback molecules. Within the frozen 344-row benchmark, **14 rows (4.1%)** remain attached to placeholders, down from 107/344 (31.1%) at v5. Users requiring named-molecule isolation should restrict analysis to the 330-row named-molecule benchmark subset.

### S7.3 Grade A/B release rows outside the frozen benchmark

The release contains **508 Grade A/B records**, of which **344** are assigned to the frozen reference benchmark. The remaining **164 Grade A/B rows** are released as evidence but are not benchmark-assigned because they are singleton leakage groups or await promotion of later expansion batches under the pair-level isolation rule.

### S7.4 Pair-level leakage invariant

The current benchmark enforces pair-level isolation at `(source_document_id, molecule_id)`. The release check:

```sql
SELECT leakage_group, COUNT(DISTINCT split_name)
FROM benchmark_split
GROUP BY leakage_group
HAVING COUNT(DISTINCT split_name) > 1;
```

returns no rows. The benchmark is therefore pair-isolated, while the manuscript explicitly discloses that strict molecule-level isolation requires the 330-row named-molecule subset.

---

\clearpage

## S8. Closest-work feature audit underlying Figure 5

Figure 5 separates literature overlap from resource capability. Source-PMID sets were available for OligoVigil, CRISPRoffT and siRNAEfficacyDB; all pairwise and triple intersections were zero. Feature support was assessed conservatively as **yes**, **partial**, or **absent/undocumented** from the corresponding paper or inspectable portal.

| Feature | OligoVigil | theRNA | siRNAEfficacyDB | CMsiRNAdb | siRNAmod | CRISPRoffT |
| --- | --- | --- | --- | --- | --- | --- |
| Total curated records | yes | yes | yes | yes | yes | yes |
| Exact source location | yes | yes | partial | partial | partial | partial |
| Curator audit trail | yes | partial | absent | absent | absent | partial |
| Inter-curator check | yes | absent | absent | absent | absent | absent |
| Machine-stage FAR audit | yes | absent | absent | absent | absent | absent |
| Benchmark splits | yes | absent | partial | absent | absent | partial |
| Deterministic baselines | yes | absent | absent | absent | absent | absent |
| Structured assay metadata | partial | partial | yes | partial | absent | partial |
| Per-position chemistry | absent | partial | absent | yes | yes | absent |
| Off-target gene resolution | partial | absent | absent | absent | absent | yes |
| No-login portal | yes | yes | yes | yes | absent | yes |
| API / OpenAPI | yes | partial | partial | partial | absent | partial |
| Agent-readable metadata | yes | absent | absent | absent | absent | partial |
| Bulk download | yes | partial | partial | partial | partial | partial |
| Versioned release | yes | partial | partial | partial | partial | partial |
| Named maintainer | yes | yes | yes | yes | partial | yes |

**Interpretation.** OligoVigil does not lead on absolute scale, per-position chemistry, dose coverage or gene-level off-target resolution. Its distinguishing combination is exact source-localized evidence, a downloadable human audit trail, measured machine-stage error, inter-curator reliability reporting, a frozen reference split and programmatic reuse surfaces.

The source-data tables used to render Figure 5 are:

- `figures/source_data/FIG5_closest_work_audit_v2_sets.csv`
- `figures/source_data/FIG5_closest_work_audit_v2_intersections.csv`
- `figures/source_data/FIG5_closest_work_audit_v2_features.csv`

---

*End of Supplementary Materials.*
