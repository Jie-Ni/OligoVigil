# OligoVigil: a curator-verified, source-anchored database of safety and off-target evidence for therapeutic oligonucleotides

Authors: Jie Ni¹,²,³,\*, Xinting Zhang¹, Zhuoying Xie¹, Shan Lu⁴, Yun Liu¹,⁵,\*, and Adam Jatowt²,\*

¹ State Key Laboratory of Digital Medical Engineering, School of Biological Science and Medical Engineering, Southeast University, Nanjing 211102, Jiangsu, China
² Digital Science Center, University of Innsbruck, Innsbruck 6020, Tirol, Austria
³ Department of Medical Informatics, School of Biomedical Engineering and Informatics, Nanjing Medical University, Nanjing 211166, Jiangsu, China
⁴ Women and Children Department, The First Affiliated Hospital, Nanjing Medical University, Nanjing 210029, Jiangsu, China
⁵ Department of Information, The First Affiliated Hospital, Nanjing Medical University, Nanjing 210029, Jiangsu, China

\* Corresponding authors: Jie Ni (njie@seu.edu.cn); Yun Liu (liuyun@njmu.edu.cn); Adam Jatowt (adam.jatowt@uibk.ac.at).

---

## Abstract

Therapeutic antisense oligonucleotides (ASOs), siRNAs and related modalities require safety and off-target evidence that remains scattered across primary papers, regulatory documents and transcriptomic studies. We present OligoVigil, a curator-verified database of therapeutic-oligonucleotide safety and off-target evidence. The current release contains 737 human curator-verified evidence records from 660 primary sources, comprising 626 toxicity endpoints and 111 off-target observations. Each release row is an observed experimental result linked to an exact source location, evidence grade and curation-audit record. The release was built from 36,245 indexed source documents, 70,283 curation tasks and 41,114 candidate annotations through candidate generation, source-grounded proposal gating and row-by-row human adjudication. A 2,003-candidate machine pool had a measured false-accept rate of 0.73 in a 126-row audit, and 1,345 unsupported candidates were demoted rather than released. OligoVigil also provides a 344-record Grade A/B benchmark with pair-level source-by-molecule isolation, deterministic baselines, bulk downloads, REST/OpenAPI access, MCP manifests, Bioschemas JSON-LD and W3C PROV exports. A mixed 100-row second-curator study yielded Cohen kappa_binary = 0.42 under the drop-abstain convention and 0.34 under a safety-conservative collapse-abstain convention. Availability: https://oligovigil.pages.dev/; archive: 10.5281/zenodo.20633779; data under CC BY 4.0.

---

## Introduction

Oligonucleotide therapeutics have moved from exceptional cases to an established drug modality. Approved and late-stage agents now include RNase-H ASOs, splice-switching oligonucleotides, siRNA therapeutics, PMOs and chemically stabilized or conjugated designs, with GalNAc delivery making liver-directed RNAi especially tractable [1-7]. This success has shifted a major part of preclinical decision-making from target knockdown to safety and design triage.

Two evidence classes matter most for that triage. The first is chemistry-, dose- and tissue-exposure-driven toxicity, including hepatic, renal, hematologic, complement and innate-immune liabilities [8-10,15-17]. The second is off-target activity, including siRNA seed effects, hybridization or mismatch effects and transcriptome-scale perturbations that may be missed by target-efficacy summaries [10-14]. These observations exist across primary papers, supplementary files and regulatory-style reports, but they are not easy to search, cite or reuse.

The current database landscape answers adjacent questions rather than this one. theRNA provides broad coverage of functional RNA therapeutics [18]. siRNAEfficacyDB, CMsiRNAdb and siRNAmod focus on siRNA efficacy or chemical modification effects on silencing [19-21]. CRISPRoffT curates off-target evidence for CRISPR/Cas systems, a different molecular class [22]. These resources are valuable, but they do not provide a therapeutic-oligonucleotide safety resource in which each toxicity or off-target observation is tied to an exact source location, an explicit human decision and a reusable audit record.

Recent NAR Web Server and Database resources also show that modern biological databases are judged not only by record count, but by whether users can inspect the data, reproduce the analysis path and reuse the resource programmatically [23-31]. Successful resources combine a clear workflow, a content landscape, task-oriented web interfaces, downloads or APIs and transparent maintenance. For oligonucleotide safety, these expectations are especially important, because an unsupported or poorly grounded record can mislead design decisions.

We built OligoVigil to fill that gap. Its central object is a verified evidence row that links oligonucleotide identity, safety or off-target endpoint, exact source provenance, evidence grade, human audit status and benchmark reuse metadata. The remainder of this paper describes the database scope, the curation pipeline and its integrity safeguards (Figure 1), the evidence-object and access architecture (Figure 2), the release evidence landscape (Figure 3), the web portal and reusable access layers (Figure 4), the closest-work audit (Figure 5), the validation dashboard (Figure 6), and the resource's explicit limitations.


## Database scope

In scope. OligoVigil admits observed, primary preclinical evidence of two kinds. The first is the safety and toxicity of therapeutic oligonucleotides or their delivery products, covering hepatic, renal, hematologic and platelet, immune, cytokine and complement, neurological, genotoxic, body-weight, mortality and related endpoints. The second is their off-target effects, covering seed-mediated, mismatch and hybridization-dependent, and transcriptome-wide (RNA-seq or microarray) observations. Eligible agents are therapeutic oligonucleotides (ASO and gapmer, siRNA and RNAi therapeutic, PMO, LNA, aptamer, GalNAc-siRNA, therapeutic miRNA mimic / agomir) or a delivery vehicle carrying such an oligonucleotide. Aptamers are included as a borderline therapeutic-oligonucleotide class with 2 release rows; they are structurally distinct from ASO/siRNA chemistries but functionally analogous in this resource, and `modality.in_core_scope` is set to 1 to make the scope flag consistent with the prose (this was an internal-inconsistency fix at revision; the 2 release rows were already in scope).

Explicitly excluded. Several adjacent classes are deliberately out of scope: CRISPR/Cas guides, shRNA, AAV and viral gene therapy, mRNA therapeutics, endogenous lncRNA, circRNA and miRNA biology (therapeutic miRNA mimics and agomirs remain in scope), small molecules and natural products, G-quadruplex small-molecule ligands, agricultural, insect and nematode RNAi, and oligonucleotides used merely as a laboratory knock-down tool. On-target efficacy, target-knockdown potency, pharmacokinetics and biodistribution are out of scope as release evidence. These boundaries are enforced at curation time (see Methods) and again in automated quality assurance; CRISPR guides, for instance, are blocked from the molecule table.

## Materials and methods

### Data sources and licensing

Candidate evidence is derived from PubMed and PMC-indexed literature; the resource currently indexes 36,245 source documents. Released records store derived annotations and exact source locations together with stable identifiers (PMID, PMCID where available, and DOI), but they do not redistribute raw third-party article text or full-text PDFs. Each source carries a record-level reuse classification (raw-redistributable, derived-annotations-only, query or link-out only, or not-safe); restricted resources such as DrugBank and TTD are treated as link-out comparators rather than ingested. The per-class breakdown is given in Supplement S6 (all 36,245 indexed sources carry a derived-annotations-only reuse classification, with 7 open-access / official-guideline / official-notice exceptions at the license level; all 660 release-anchored sources are classified derived-annotations-only / abstract-metadata-only for redistribution). This redistribution classification governs what OligoVigil may re-publish and is independent of grounding depth: full text was read for grounding wherever a PMC record was available (547 / 737 release records are full-text-PMC-anchored; see Database content), but no third-party full text is redistributed. This conservative redistribution policy is provided as a machine-readable source-license manifest.

### Curation pipeline

Every OligoVigil record passes through a three-stage pipeline (Figure 1) whose stages are kept separate by design, so that machine output can never be presented as human curation.

Stage 1, candidate generation. A curation queue of 70,283 tasks over the indexed sources yields 41,114 derived candidate annotations, each storing matched terms, a candidate evidence domain, a source location and extraction metadata. Candidates are working items, never release evidence, and are labelled accordingly throughout the database (`curation_candidate`, status `machine_precurated_v1`, `candidate_needs_curator_review` or `curator_rejected`) and in every download.

Stage 2, machine pre-curation (v1) and error audit. An initial keyword and rule-based classifier assigned provisional accept labels within a 2,003-candidate pool. Its accuracy was evaluated by independent source-grounded re-adjudication of a 126-record stratified sample. Of 90 v1 accept calls, 66 were false accepts, 23 were confirmed accepts and 1 was uncertain. We report the conservative false-accept estimate as 66 / 90 = 0.73 (Wilson 95% CI [0.63, 0.81]); excluding the uncertain call gives 66 / 89 = 0.74. The 66 false accepts were categorised as domain confusion (33), boilerplate-no-endpoint (13), missing scope exclusion (18), acronym collision (1) and other (1). The per-row decomposition is provided in `04_delivery/v1_classifier_far_audit_n126.csv` with columns `{candidate_id, pmid, domain, source_location, v1_decision, v1_grade, re_adjudication_decision, re_adjudication_reason, sampling_stratum, error_category}`, so that `SELECT COUNT(*) WHERE v1_decision='accept' AND re_adjudication_decision='reject'` returns 66. The v1 labels are therefore retained only as machine pre-curation metadata, not as release evidence.

Stage 3, source-grounded language-model screening and human adjudication. Every v1 candidate was re-screened by a source-grounded language-model curator that reads the cached full text, or the abstract where full text is unavailable, and applies an exclusion-first, four-gate rubric: the molecule must be in scope; the result must be a primary observed finding; the evidence type must match the requested domain; and the model must supply a verbatim grounding quote that is checked in code as an exact substring of the supplied passage, so an ungrounded rationale is forced to a reject. The model output is proposal-only; it never writes a curator decision, identity or validation status. A single human curator (curator of record: Ni Jie, University of Innsbruck) adjudicated each proposal against the source, recording the final accept or reject decision, evidence grade and note row by row. Human review overrode 27 of 1,168 firm model accept/reject proposals (2.3%), recovered 33 of 835 model-abstain cases as accepts after source review, and adjusted 92 of 658 grades (14%). The original 2,003-candidate pool yielded 657 accepted records and 1,345 demoted or removed candidates; demotion deletes the row from the release tables and writes a `recurated_rejected` audit record. Subsequent curator-verified expansion rounds added 48 records (43 toxicity + 5 off-target) and 32 toxicity records, bringing the current release to 737. The per-candidate decision triple (v1 keyword call, v2 model proposal, human accept/reject/grade) is provided as `04_delivery/v2_human_override_decisions.csv` (n=2,003 rows).

Every release row carries a curation-audit record holding the curator identity (`curator_id='ni_jie'`), the decision, the grade, the verbatim grounding quote and a timestamp. Machine rows are kept distinct under `machine_precurated_v1`; the full audit table can be queried through the SQL view `release_audit_v` (see Audit reconciliation).

Second-curator pilot (KAPPA-1). An initial independent second-curator review blindly re-reviewed a stratified random sample of 100 release rows (50 toxicity + 50 off-target, sampled across Grade A / B / C in proportion) for accept / reject / abstain and, on accepts, for Grade A/B/C. Because the sample was drawn entirely from rows already accepted by the curator of record (Ni Jie), the binary-decision Cohen κ is not defined: the curator-of-record marginal has no variance. Reportable quantities from KAPPA-1 are raw decision agreement of 52 / 100 = 52% (52 accept-confirmed, 14 reject-overturn, 34 abstain on the second reading) and, on the 52-row jointly accepted subset, Cohen κ for the Grade A/B/C call = 0.21 (fair), with raw Grade agreement of 48.1%. KAPPA-1 is retained as a conditional-on-accept Grade-axis statistic; the binary accept/reject reliability analysis is provided by KAPPA-2.

Second-curator mixed accept/reject study (KAPPA-2). To estimate binary accept/reject reliability, KAPPA-2 used a mixed design of 100 rows: 50 drawn from curator-of-record accept rows and 50 from curator-of-record reject rows, stratified by domain (toxicity vs off-target) and grade (A/B/C), seed `20260608`, with zero overlap with the KAPPA-1 sample. The second curator (initials HY) had no prior exposure to the manuscript or to the KAPPA-1 sample, reviewed against the same four-gate rubric, and recorded accept / reject / abstain plus Grade A/B/C on accepts. The primary binary Cohen κ is 0.42 (moderate, Landis-Koch 0.41-0.60) under the drop-abstain convention (n=92 non-abstain rows; raw agreement 66 / 92 = 72%). A safety-conservative sensitivity analysis that collapses abstain to reject gives κ = 0.34 (fair; n=100; raw agreement 66 / 100 = 66%); the 3-class accept/reject/abstain κ is 0.37 (raw 66%) and, on the 20 jointly accepted rows, Grade A/B/C κ is 0.39 (raw 60%). The confusion matrix (rows = Ni Jie; columns = HY) is accept / reject / abstain = (20, 23, 7) on the curator-of-record accept stratum and (3, 46, 1) on the curator-of-record reject stratum (HY column marginals: 23 accept / 69 reject / 8 abstain). HY confirmed 92% (46/50) of curator-of-record rejects but accepted only 40% (20/50) of curator-of-record accepts, indicating that residual disagreement is mainly driven by stricter second readings of accepted evidence. The 42 disagreement rows are provided in `04_delivery/handoffs/KAPPA2_mixed_sample/disagreements.csv` for planned third-adjudicator review. Together, KAPPA-1 and KAPPA-2 cover 200 rows reviewed by independent second curators, with binary κ = 0.42 as the primary inter-rater statistic and Grade-axis κ = 0.21 as the conditional-on-accept statistic.

Sensitivity analysis on the abstain convention (dual-convention κ). Because eight of the 100 KAPPA-2 rows received an abstain from HY (with no abstain calls from the curator of record), Cohen κ depends on the abstain-handling convention. We therefore report two conventions: (i) binary κ after dropping abstain rows, n=92 non-abstain rows = 0.42; and (ii) binary κ after collapsing abstain to reject, n=100 = 0.34. Treating abstain as a third class gives κ = 0.37. Grade-level κ on the n=20 grade-able subset is 0.39.

Third-adjudicator status. A third-adjudicator packet has been prepared (34 disagreement rows interleaved with 20 calibration rows; full protocol in `04_delivery/handoffs/A10_third_adjudicator/`). Results from that round are not included in the current release; consensus labels will be incorporated into a later release after completion.

### Evidence grading

Released records are graded by the strength of their source anchoring. Grade A is a full-text Results, Figure, Table or Supplement location for a named therapeutic oligonucleotide with the correct evidence type. Grade B is a therapeutic oligonucleotide supported only by an abstract-level or otherwise weaker location. Grade C is in-scope but generic or unnamed, or otherwise weakly supported. Only Grade A and B records are benchmark-eligible.

### Benchmark construction

We provide reference train, validation and test splits over the Grade A/B release. Splits are grouped by source-paper × molecule pairs (`split_strategy = 'source_plus_molecule_grouped_*'`); no (source × molecule) leakage group spans more than one split. This is pair-level isolation, not molecule-level isolation: 7 toxicity molecule_ids and 4 off-target source papers (sources 1411, 1477, 1732, 10539) contribute distinct (source × molecule) pairs to more than one split, of which 2 of the 7 cross-split toxicity molecule_ids remain modality-scoped placeholders. Of the 508 Grade A/B release rows (233 A + 275 B), 344 enter the benchmark; the remaining 164 fall in singleton (source × molecule) groups that cannot be assigned to a train/validation/test trio while preserving the pair-isolation invariant, and are released as A/B evidence but not benchmark-graded. The 80 expansion records have not yet been promoted into the benchmark splits; their promotion under the same pair-isolation invariant is a planned update. We additionally provide four deterministic prior baselines (a train-majority class baseline, and modality-, evidence-grade- and target-prior classifiers) computed on the fixed splits, as diagnostic floor estimates rather than as a proposed method.

### Quality assurance

The release is gated by three automated QA suites, covering database invariants, the frontend and API contract, and a final delivery check. Among other checks, they require every release row to carry a human curator-verified accept audit, restrict benchmark splits to Grade A/B release rows, forbid abstract-level or unverified rows from being accepted, and enforce the candidate-versus-release separation. The current release passes all three.

## Database content (current release)

The release contains 737 curator-verified records: 626 toxicity endpoints and 111 off-target observations, drawn from 660 distinct primary sources, of which 547/737 (74.2%) are anchored in full text (PMC). Provenance and grading fields are complete: source title, source location, PMID and evidence grade are populated at 100%, and DOI at 733/737 = 99.5%. The release spans 1,012 distinct molecules in the molecule table. Figure 3 maps this release as an evidence landscape rather than as a simple count summary, linking modality, evidence domain, endpoint family, evidence grade, reuse state, source year and grounding depth.

Evidence grade. Combined, the release holds 233 Grade A, 275 Grade B and 229 Grade C records. The per-domain Grade A/B/C decomposition is toxicity 200/210/216 and off-target 33/65/13. Grade A/B records are eligible for benchmark use, whereas Grade C records remain release evidence but are excluded from the reference splits.

Modality. The main modality classes are siRNA (328 records), ASO (262), mixed ASO/siRNA contexts (117), PMO (16) and CpG oligodeoxynucleotide (4), with a small tail of miRNA-agomir (3), aptamer (2), DNA nanostructure (2), ASO/RNA mixed (1), DNA/RNA heteroduplex (1) and PMOplus (1) records. Expansion rounds added records reporting shared chemistry or delivery contexts, which account for the larger mixed ASO/siRNA category.

Toxicity endpoint categories. The toxicity subset is dominated by hepatic endpoints (337), followed by general safety (105), renal (42), mixed-grade toxicity (34), immunotoxicity (24), chemistry (21), delivery (20), neurological (15), hematologic or hematological (16 = 10 + 6), general toxicity (5), genotoxicity (2) and a five-record mixed tail. These counts sum to all 626 toxicity records.

Off-target evidence types. The 111 off-target records split into seed-mediated effects (44), hybridization and mismatch effects (26), transcriptome-level effects (24) and generic off-target or specificity observations (17). These categories are the mechanistic groupings most useful for design triage.

Residual placeholder molecule disclosure. Of the 737 release rows, 31 remain attached to true placeholder or mixed-modality fallback molecules after the placeholder-recovery pass, a 78% reduction from the earlier 143-row placeholder set. The recovery pass resolved 110 of those 143 rows: 70 underlying real molecule names were recovered from the source and merged onto canonical molecule_ids, and 42 records were split onto PMID-scoped placeholders that restore pair-level isolation even when the molecule name remains unrecoverable. Of the 344 benchmark rows, 14 (4.1%) remain on placeholders, down from 107/344 (31.1%). The 80 expansion records have not yet been promoted into benchmark splits; promotion under the pair-isolation invariant is planned.


### Audit reconciliation

For the current release, the `curation_audit` table holds exactly one curator-verified accept audit per release row (737 audits for 737 release entities). The SQL view `release_audit_v`:

```sql
CREATE VIEW release_audit_v AS
  SELECT * FROM curation_audit
   WHERE validation_status = 'curator_verified'
     AND curator_decision  = 'accept'
     AND curator_id NOT LIKE 'machine_%'
     AND curator_id NOT LIKE '%seed_nonhuman';
```

pre-applies the human-curator filter; the predicate `SELECT COUNT(*) FROM release_audit_v WHERE entity_table IN ('toxicity_endpoint','offtarget_evidence')` returns 737 (= 626 + 111). Downstream users should join evidence tables against `release_audit_v`, not against the raw `curation_audit` table, because the raw audit table also retains historical machine-precuration rows for provenance. Duplicate spot-check audit rows and two orphan audits pointing to demoted candidates were removed before release, leaving a one-to-one relation between release entities and curator-verified accept audits.

### Benchmark and baselines

The benchmark comprises 344 Grade A/B records: a toxicity task of 263 records (train 218 / validation 23 / test 22) and an off-target task of 81 records (train 66 / validation 5 / test 10). On the fixed test sets, all four prior baselines tie at macro-F1 = 0.26 on the toxicity test set; off-target baselines span 0.14–0.37 on the test set. We report these as diagnostic floor estimates on test sets of n = 22 (toxicity) and n = 10 (off-target); at these test-set sizes no statistical separation between baselines can be inferred (all four prior baselines tie at macro-F1 = 0.26 on the toxicity test set), and we therefore report neither pairwise CIs nor ranking. The four numerical baseline values are reproduced in Supplement S4 only; the role of this section is to establish that prior-only predictions sit substantially below ceiling. The benchmark is intended as a reproducible, leakage-aware evaluation seed, not a training corpus.

## Web portal and programmatic access

OligoVigil follows the access pattern of durable NAR-style web resources: the same evidence object is exposed through a human-facing portal, citable record pages, bulk downloads and machine-readable interfaces [23-31]. Figure 4 shows the current portal workflow. Users can search by molecule, modality, endpoint, source title, PMID, DOI or evidence text; filter by domain, grade, modality and endpoint family; open the source-localized evidence statement; inspect the audit record; export citations; and download filtered evidence or benchmark splits.

The programmatic layer is an integral access route rather than an afterthought. OligoVigil exposes a documented REST API, OpenAPI 3.1 description, MCP server manifest, `llms.txt` and `llms-full.txt`, Bioschemas `Dataset` JSON-LD and a W3C PROV-compatible profile. A read-only natural-language query endpoint returns grounded records with citations and an explicit query plan. It links users to source-supported evidence rather than generating de novo risk predictions, and returns no supported record when no curated evidence is found.


## Comparison with existing resources

OligoVigil complements, rather than replaces, existing oligonucleotide resources, because it answers a different question. theRNA catalogues broad functional RNA therapeutics [18]; siRNAEfficacyDB [19], CMsiRNAdb [20] and siRNAmod [21] catalogue siRNA efficacy, silencing or chemical-modification effects; CRISPRoffT addresses a different molecular class [22]. The distinguishing contribution of OligoVigil is a safety- and off-target-centred, curator-verified, source-anchored, graded and audited evidence layer with a leakage-aware benchmark.

Figure 5 separates the closest-work audit into two questions. First, the source-PMID comparison shows that the 660 PMIDs supporting OligoVigil release records are disjoint from the PMID-indexed portions of CRISPRoffT (74) and siRNAEfficacyDB (7), with all pairwise and triple intersections equal to zero. This is structurally plausible rather than a missing-data artefact: CRISPRoffT curates CRISPR/Cas off-targets, and siRNAEfficacyDB indexes efficacy screens rather than preclinical safety or off-target evidence. Second, the feature fingerprint shows that OligoVigil's novelty is not absolute scale or complete chemistry metadata, but exact source-location anchoring, curation-audit transparency, inter-curator reliability reporting, machine-stage false-accept auditing, reference benchmark splits and agent-readable reuse surfaces.


This comparison is intentionally conservative. OligoVigil does not claim to be a broad RNA-therapeutics catalogue, a siRNA-efficacy database, a CRISPR off-target database, or a complete sequence and modification catalogue. Its contribution is narrower: a source-grounded safety and off-target evidence layer that downstream users can inspect, cite, download and reuse.


## Discussion

OligoVigil reframes the fragmented preclinical safety and off-target literature for oligonucleotide therapeutics as a queryable, provenance-first evidence layer. The contribution is centred on verifiability rather than volume: each of the 737 release records is traceable to an exact source location and a human accept decision, and the candidate-to-release firewall makes the provenance of each record auditable. The measured failure rate of the machine pre-curation stage (0.73 false-accept rate, Wilson 95% CI [0.63, 0.81], on the 126-record audited sample) and the demotion of 1,345 unsupported candidates provide an auditable basis for the release. This distinguishes OligoVigil from efficacy-oriented databases that define much of the current landscape. A mixed accept/reject inter-rater study produced binary κ = 0.42 under the drop-abstain convention and κ = 0.34 under the collapse-abstain-to-reject convention; disagreement was asymmetric, with HY confirming 92% of curator-of-record rejects but only 40% of curator-of-record accepts. A third-adjudicator packet has been prepared for the remaining disagreement rows.

The release also supplies a leakage-aware evaluation seed for safety and off-target prediction tasks. Grouping the benchmark by source-paper × molecule pairs prevents the most common form of optimistic leakage at the pair level, and deterministic prior baselines provide a reproducible performance floor. Placeholder contamination in the benchmark is 14 / 344 = 4.1%, and the named-molecule subset on which the molecule axis is informative contains 330 rows. The prior-only baselines remain substantially below ceiling on both subsets, indicating room for learned methods while preserving the benchmark's stated size and isolation limits.

Recent curation updates resolved 110 of 143 placeholder molecules (78%), populated 11 additional off-target rows with structured gene identity, and added 48 curator-verified records (43 toxicity + 5 off-target), including 41 records covering chemistry and delivery domains for the first time. A subsequent toxicity-cache fill added a further 32 toxicity records. The KAPPA-1 pilot of 100 release-row second reads yielded 52% raw decision agreement and a fair Grade-axis κ = 0.21 on the 52 jointly accepted subset. The KAPPA-2 mixed-pool study of 100 rows yielded binary Cohen κ = 0.42 (moderate, Landis-Koch) with raw agreement 66 / 92 = 72% after dropping abstains, and the sensitivity analysis that collapses abstain to reject yielded κ = 0.34 (fair; raw agreement 66 / 100 = 66%).

These contributions should be interpreted within stated boundaries. The evidence layer is observed and source-localized, but it is not a complete census of the oligonucleotide safety literature, and the small test sets mean the baseline metrics diagnose task difficulty rather than rank methods. The single-curator design means that the release reflects one primary curator's proposal-informed adjudication plus two independent second-curator checks; the current inter-rater layer supports transparency but does not replace a full consensus curation round. Within those limits, the resource supports its intended uses, namely retrieving graded, source-anchored safety and off-target evidence and seeding reproducible evaluation. It does not support uses for which it was not designed, such as serving as a complete sequence and modification catalogue or a de novo risk predictor.

## Limitations

Several boundaries are important for interpretation.

(1) Scale. The verified release is modest in size (737 records) because it is restricted to rows that survived source-grounded human review after demotion of unsupported machine-precurated candidates. We prioritized correctness and verifiable provenance over volume; every released record traces to an exact source location and a human accept decision.

(2) Structured chemistry and sequence fields remain partially populated. Identity, provenance and grading fields are complete. Sequence fields (sense, antisense, guide, seed) and the bulk of chemistry and delivery fields remain a prioritized curation worklist. For the off-target evidence layer, `offtarget_gene_symbol` is populated for 105 / 111 rows (94.6%): 17 rows carry a specific HUGO-style gene symbol, 45 carry the curator-defensible label "unspecified", 43 carry "transcriptome-wide", and 6 remain NULL. Users running gene-conditioned analyses should treat the off-target layer as a 17-symbol indexed seed plus 88 source-anchored but unindexed observations. OligoVigil should therefore be described as a provenance-rich safety and off-target evidence database, not a complete sequence, modification or dose catalogue.

(3) Single primary curator with a dual-convention second-curator inter-rater layer. The release reflects one primary human curator's proposal-informed adjudication. Two independent second-curator rounds have been run. KAPPA-1, a release-row pilot of 100 curator-of-record accepted rows, gave 52% raw agreement and Grade-axis κ = 0.21 (fair) on the 52 jointly accepted subset; by design the binary κ from that sample is not defined. KAPPA-2, a mixed accept+reject sample of 100 rows, gives binary Cohen κ = 0.42 (moderate, Landis-Koch 0.41-0.60) under the drop-abstain convention (n=92; raw 66 / 92 = 72%), bounded below by κ = 0.34 (fair) under the safety-conservative collapse-abstain-to-reject convention (n=100; raw 66 / 100 = 66%). HY confirmed 92% (46/50) of curator-of-record rejects but accepted only 40% (20/50) of curator-of-record accepts, indicating that disagreement is dominated by stricter second readings of accepted evidence. A third-adjudicator review is planned for the 117 combined KAPPA-1 and KAPPA-2 disagreement rows.

(4) Benchmark size and isolation level. The 344-record benchmark, with test sets of 22 (toxicity) and 10 (off-target), is a reproducibility seed, not a large-scale corpus, and its baseline metrics are diagnostic floor estimates only (see Benchmark and baselines). The pair-isolation invariant prevents (source × molecule) leakage and, after the collaborator B2 recovery pass in v6, the residual placeholder contamination is 14 / 344 = 4.1% (down from 107 / 344 = 31.1% at v5, a 87% reduction). Users who require strict molecule-level isolation should now restrict to the 330-row named-molecule subset (up from 237 at v5).

(5) Structured assay metadata is uneven; placeholder molecules are largely resolved. `dose_value` is populated for 2 / 626 toxicity rows (0.3%) and `exposure_time_value` for 0 / 626 (0%). Users requiring structured dose-response should treat OligoVigil as a literature-anchored evidence index, not as a ToxRefDB-style structured database. Populating dose for the Grade A subset is planned for a future release. The placeholder issue is substantially reduced: 31 of 737 release rows remain on true placeholder or mixed-modality fallback molecules, and benchmark contamination falls from 107 / 344 (31.1%) to 14 / 344 (4.1%). The remaining 19 unrecoverable placeholders are scheduled for source re-checking.

(6) Expansion records not yet promoted into the benchmark. The 80 curator-verified expansion records carry curator-assigned Grade B (31) and Grade C (49) values but have not yet been assigned to train / validation / test splits in `benchmark_split`. The 344-record benchmark therefore remains at the earlier split composition; promoting the expansion records through the pair-isolation gate is planned. Until then, benchmark-conditioned analyses should use the current 344-row split structure.

## Data availability

The web portal, REST API, full data dictionary, complete curation audit (via `release_audit_v`), benchmark splits and deterministic baselines are openly available without login at https://oligovigil.pages.dev/; the versioned data snapshot is archived at DOI 10.5281/zenodo.20633779. All counts in this paper correspond to the release snapshot of 2026-06-08.

## Supplementary data

Supplementary Data are available at NAR Online.

## Future directions

Future releases will extend the structured sequence, chemistry and delivery fields beyond the 41 seeded records to the full benchmark-linked Grade A/B set; re-check the remaining 19 unrecoverable placeholder molecules and 12 mixed-modality fallbacks; populate `dose_value` and `exposure_time_value` for at least the Grade A toxicity subset; route the 117 combined KAPPA-1 and KAPPA-2 disagreement rows through the prepared third-adjudicator packet; promote the 80 expansion records into the benchmark splits under the pair-isolation invariant; re-curate periodically as the literature grows; and expand the smaller off-target evidence layer.

## Figures

![](C:/Users/Jie/Desktop/NAR_OligoSafetyDB/repo_ready/FINAL/v1_NAR_2026-06-07/figures/FIG1_curation_pipeline_v12.png){width=95%}

Figure 1. OligoVigil curation pipeline and candidate-to-release funnel. The pipeline runs from indexed literature (36,245 source documents) through the curation queue (70,283 tasks), derived candidates (41,114), machine audit (2,003 v1 pool; measured 0.73 false-accept rate, Wilson 95% CI [0.63, 0.81]) and source-grounded model proposals to a human review gate. Only source-supported records pass into the verified release (737 accepted records, 626 toxicity + 111 off-target); 1,345 candidates were demoted after review. The lower lane summarizes the biological evidence path from ASO/siRNA candidate evidence to source-supported safety evidence, and the inset reports the second-curator check (κ = 0.42 under the drop-abstain convention; sensitivity κ = 0.34 under collapse-abstain).

\clearpage

![](C:/Users/Jie/Desktop/NAR_OligoSafetyDB/repo_ready/FINAL/v1_NAR_2026-06-07/figures/FIG2_evidence_object_architecture_v12.png){width=95%}

Figure 2. OligoVigil verified evidence object and reuse architecture. A source sentence from PubMed/PMC is converted into a candidate row and subjected to human review before becoming a verified evidence object. The central object links oligonucleotide identity (ASO/siRNA), safety or off-target endpoint, source provenance (PMID and exact location), and human audit status, with grade and benchmark split as reusable metadata. The same verified evidence layer supports human-facing access (web portal and downloads) and agent-facing access (REST/OpenAPI, MCP, Bioschemas JSON-LD and W3C PROV).

![](C:/Users/Jie/Desktop/NAR_OligoSafetyDB/repo_ready/FINAL/v1_NAR_2026-06-07/figures/FIG3_evidence_landscape_v3.png){width=95%}

Figure 3. OligoVigil evidence landscape. (A) Alluvial evidence flow from molecule class through evidence domain, endpoint family, evidence grade and reuse state. Ribbon width is proportional to release-row count, so the panel shows how verified records move from modality to benchmark-eligible or release-only states. (B) Mechanism and endpoint connectivity network linking modality classes to toxicity and off-target evidence families. Edge width encodes the number of curator-verified records. (C) Source-year landscape by domain. Bubble area indicates the number of distinct sources in each year-domain stratum, and fill distinguishes PMC full-text grounding from abstract/metadata grounding. (D) Reusable-evidence state bars summarizing domain, grade, benchmark eligibility and grounding depth for the 737-record release.

![](C:/Users/Jie/Desktop/NAR_OligoSafetyDB/repo_ready/FINAL/v1_NAR_2026-06-07/figures/FIG4_walkthrough.png){width=95%}

Figure 4. OligoVigil web-portal walkthrough, captured from the live deployment. (A) Landing view: free-text search across molecule, target, endpoint, modification, source, PMID and DOI, with release statistics (737 verified records; 626 toxicity + 111 off-target) and primary workflow entry points. (B) Verified-release evidence browser with domain, evidence-grade, modality and category facets; every row exposes its exact source location (section and paragraph) and PMID. (C) Citable-record detail for a single release row, showing the source-anchored evidence statement, the exact source location (e.g. "Results > ...; paragraph 15"), the assigned evidence grade with its rationale, and the provenance status from the curator audit; sequence- and chemistry-level fields are explicitly marked as not curated rather than inferred. (D) Programmatic access surfaces: a universal agent.json manifest, OpenAPI 3.1 REST, an MCP server, llms.txt, Bioschemas JSON-LD, and SDK clients, so that agent and human consumers query the same source-anchored evidence without scraping the web interface.

\clearpage

![](C:/Users/Jie/Desktop/NAR_OligoSafetyDB/repo_ready/FINAL/v1_NAR_2026-06-07/figures/FIG5_peer_comparison.png){width=95%}

Figure 5. Closest-work audit against peer oligonucleotide databases. (A) Source-PMID disjointness for OligoVigil, CRISPRoffT and siRNAEfficacyDB. The three PMID-indexed sets have zero pairwise and triple overlap, supporting the claim that OligoVigil occupies a distinct literature slice rather than repackaging existing curated records. (B) Feature fingerprint across OligoVigil, theRNA, siRNAEfficacyDB, CMsiRNAdb, siRNAmod and CRISPRoffT. Filled circles indicate published or inspectable support for each resource-level capability; partial support is shown separately from absent or undocumented support. OligoVigil is strongest on provenance, audit, benchmark and programmatic reuse, while remaining weaker on complete chemistry, dose and assay metadata.

\clearpage

![](C:/Users/Jie/Desktop/NAR_OligoSafetyDB/repo_ready/FINAL/v1_NAR_2026-06-07/figures/FIG6_validation_coverage_dashboard_v12.png){width=95%}

Figure 6. Release validation and residual curation gaps. (A) Core-field completeness by domain, showing complete provenance and evidence grading alongside sparse sequence/modification and dose fields. (B) Error categories among the 66 false accepts in the 126-row machine-stage FAR audit, dominated by domain confusion and scope exclusion. (C) KAPPA-2 mixed accept/reject independent-curator confusion matrix, supporting κ = 0.42 and sensitivity κ = 0.34. (D) Benchmark and metadata readiness, including the 737-record release, 344 Grade A/B reference split, 164 A/B records not yet benchmarked, 624 toxicity rows without structured dose, and 14 placeholder benchmark rows.

## Funding

This work received no external funding. The computational results reported in this manuscript were obtained on the Austrian Scientific Computing (ASC) federated MUSICA cluster (site Linz, MUSICA-LNZ), supplemented by the LEO5 high-performance computing facility at the University of Innsbruck. We thank the operators of both sites for compute allocations that made this study possible.

## Author contributions (CRediT)

Jie Ni — Conceptualisation; Methodology; Software; Investigation; Formal analysis; Data curation; Visualisation; Writing — original draft; Project administration.
Xinting Zhang — Investigation; Data curation; Validation.
Zhuoying Xie — Investigation; Visualisation.
Shan Lu — Resources; Writing — review & editing.
Yun Liu — Conceptualisation; Supervision; Writing — review & editing; Resources.
Adam Jatowt — Supervision; Writing — review & editing; Resources.

## Conflict of interest

The authors declare that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.

## References

1. Egli, M. and Manoharan, M. Chemistry, structure and function of approved oligonucleotide therapeutics. *Nucleic Acids Research* **51**, 2529-2573 (2023). DOI:10.1093/nar/gkad067; PMID:36881759.
2. Shen, X. and Corey, D.R. Chemistry, mechanism and clinical status of antisense oligonucleotides and duplex RNAs. *Nucleic Acids Research* **46**, 1584-1600 (2018). DOI:10.1093/nar/gkx1239; PMID:29240946.
3. Khvorova, A. and Watts, J.K. The chemical evolution of oligonucleotide therapies of clinical utility. *Nature Biotechnology* **35**, 238-248 (2017). DOI:10.1038/nbt.3765; PMID:28244990.
4. Roberts, T.C. et al. Advances in oligonucleotide drug delivery. *Nature Reviews Drug Discovery* **19**, 673-694 (2020). DOI:10.1038/s41573-020-0075-7; PMID:32782413.
5. Springer, A.D. and Dowdy, S.F. GalNAc-siRNA conjugates: leading the way for delivery of RNAi therapeutics. *Nucleic Acid Therapeutics* **28**, 109-118 (2018). DOI:10.1089/nat.2018.0736; PMID:29792572.
6. Juliano, R.L. The delivery of therapeutic oligonucleotides. *Nucleic Acids Research* **44**, 6518-6548 (2016). DOI:10.1093/nar/gkw236; PMID:27084936.
7. Setten, R.L. et al. The current state and future directions of RNAi-based therapeutics. *Nature Reviews Drug Discovery* **18**, 421-446 (2019). DOI:10.1038/s41573-019-0017-4; PMID:30846871.
8. Burel, S.A. et al. Hepatotoxicity of high affinity gapmer antisense oligonucleotides is mediated by RNase H1 dependent promiscuous reduction of very long pre-mRNA transcripts. *Nucleic Acids Research* **44**, 2093-2109 (2016). DOI:10.1093/nar/gkv1210; PMID:26553810.
9. Swayze, E.E. et al. Antisense oligonucleotides containing locked nucleic acid improve potency but cause significant hepatotoxicity in animals. *Nucleic Acids Research* **35**, 687-700 (2007). DOI:10.1093/nar/gkl1071; PMID:17182632.
10. Lindow, M. et al. Assessing unintended hybridization-induced biological effects of oligonucleotides. *Nature Biotechnology* **30**, 920-923 (2012). DOI:10.1038/nbt.2376; PMID:23051805.
11. Jackson, A.L. et al. Expression profiling reveals off-target gene regulation by RNAi. *Nature Biotechnology* **21**, 635-637 (2003). DOI:10.1038/nbt831; PMID:12754523.
12. Jackson, A.L. et al. Widespread siRNA off-target transcript silencing mediated by seed region sequence complementarity. *RNA* **12**, 1179-1187 (2006). DOI:10.1261/rna.25706; PMID:16682560.
13. Birmingham, A. et al. 3' UTR seed matches, but not overall identity, are associated with RNAi off-targets. *Nature Methods* **3**, 199-204 (2006). DOI:10.1038/nmeth854; PMID:16489337.
14. Jackson, A.L. and Linsley, P.S. Recognizing and avoiding siRNA off-target effects for target identification and therapeutic application. *Nature Reviews Drug Discovery* **9**, 57-67 (2010). DOI:10.1038/nrd3010; PMID:20043028.
15. Judge, A.D. et al. Sequence-dependent stimulation of the mammalian innate immune response by synthetic siRNA. *Nature Biotechnology* **23**, 457-462 (2005). DOI:10.1038/nbt1081; PMID:15778705.
16. Hornung, V. et al. Sequence-specific potent induction of IFN-alpha by short interfering RNA in plasmacytoid dendritic cells through TLR7. *Nature Medicine* **11**, 263-270 (2005). DOI:10.1038/nm1191; PMID:15723075.
17. Kleinman, M.E. et al. Sequence- and target-independent angiogenesis suppression by siRNA via TLR3. *Nature* **452**, 591-597 (2008). DOI:10.1038/nature06765; PMID:18368052.
18. Zhou, Y. et al. theRNA: a curated knowledgebase of functional RNA therapeutics spanning diverse modalities and disease applications. *Nucleic Acids Research* **54**, D1672-D1682 (2026). DOI:10.1093/nar/gkaf1064; PMID:41171135.
19. Zhang, Y. et al. siRNAEfficacyDB: an experimentally supported small interfering RNA efficacy database. *IET Systems Biology* **18**, 199-207 (2024). DOI:10.1049/syb2.12102; PMID:39541343.
20. He, S. et al. CMsiRNAdb: a database of chemically modified siRNA silencing efficiency for nucleic acid drug design. *BMC Bioinformatics* **27**, 33 (2026). DOI:10.1186/s12859-025-06359-y; PMID:41484819.
21. Dar, S.A. et al. siRNAmod: a database of experimentally validated chemically modified siRNAs. *Scientific Reports* **6**, 20031 (2016). DOI:10.1038/srep20031; PMID:26818131.
22. Wang, G. et al. CRISPRoffT: comprehensive database of CRISPR/Cas off-targets. *Nucleic Acids Research* **53**, D914-D924 (2025). DOI:10.1093/nar/gkae1025; PMID:39526384.
23. Schultheiss, S.J. Ten simple rules for providing a scientific Web resource. *PLoS Computational Biology* **7**, e1001126 (2011). DOI:10.1371/journal.pcbi.1001126; PMID:21637800.
24. Wilkinson, M.D. et al. The FAIR Guiding Principles for scientific data management and stewardship. *Scientific Data* **3**, 160018 (2016). DOI:10.1038/sdata.2016.18; PMID:26978244.
25. The 23rd annual Nucleic Acids Research Web Server Issue 2025. *Nucleic Acids Research* **53**, W1-W3 (2025). DOI:10.1093/nar/gkaf564; PMID:40580006.
26. Rigden, D.J. and Fernandez, X.M. The 2025 Nucleic Acids Research database issue and the online molecular biology database collection. *Nucleic Acids Research* **53**, D1-D9 (2025). DOI:10.1093/nar/gkae1220; PMID:39658041.
27. Sherman, B.T. et al. DAVID: a web server for functional enrichment analysis and functional annotation of gene lists (2021 update). *Nucleic Acids Research* **50**, W216-W221 (2022). DOI:10.1093/nar/gkac194; PMID:35325185.
28. Liao, Y. et al. WebGestalt 2019: gene set analysis toolkit with revamped UIs and APIs. *Nucleic Acids Research* **47**, W199-W205 (2019). DOI:10.1093/nar/gkz401; PMID:31114916.
29. Zhou, Y. et al. Metascape provides a biologist-oriented resource for the analysis of systems-level datasets. *Nature Communications* **10**, 1523 (2019). DOI:10.1038/s41467-019-09234-6; PMID:30944313.
30. Ruan, Z. et al. Pairpot: a database with real-time lasso-based analysis tailored for paired single-cell and spatial transcriptomics. *Nucleic Acids Research* **53**, D1087-D1098 (2025). DOI:10.1093/nar/gkae986; PMID:39494542.
31. Robert, X. et al. FoldScript: a web server for the efficient analysis of AI-generated 3D protein models. *Nucleic Acids Research* **53**, W277-W282 (2025). DOI:10.1093/nar/gkaf326; PMID:40276967.
