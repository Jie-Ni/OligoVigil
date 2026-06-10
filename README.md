# OligoVigil Presubmission Release

OligoVigil is a presubmission release candidate for a Nucleic Acids Research Database Issue resource. The local folder still uses the legacy `NAR_OligoSafetyDB` project path for continuity.

Scope:

- Core: chemically modified ASO/siRNA-class oligonucleotides.
- Core evidence: preclinical toxicity and transcriptome-level off-target evidence.
- Utility layer: evidence-graded records, provenance, downloads, evidence graph, and benchmark split metadata.
- Reuse layer: Safety Dossier Studio, citable record pages, deterministic reference splits, API snippets, agent discovery, and contribution schema.
- Out of core scope: broad therapeutic RNA catalogs, generic siRNA efficacy databases, CRISPR-guide off-target databases, clinical decision support.

Current internal release snapshot (v6.1 / v7, post-EXPAND-2 toxicity round): 737 human curator-verified release evidence records (626 toxicity + 111 off-target) with 344 Grade A/B benchmark split rows. A 100-row mixed accept+reject inter-rater study with an independent second curator (HY, no manuscript exposure) yields Cohen κ_binary = 0.34 (Landis-Koch "fair"; raw agreement 67%), with HY systematically stricter than the curator of record (92% reject-confirm, 40% accept-confirm) — the conservative direction for a safety database. These rows were independently re-curated over their source passages from an earlier pool of 2003 v1 machine pre-curated candidates (measured 0.73 false-accept rate, Wilson 95% CI [0.63, 0.81], n=126); the 1,345 candidates not supported by their source were demoted and removed from the release tables. The v5→v6 collaborator round added 48 curator-verified records (43 toxicity + 5 off-target) and the v6→v6.1 EXPAND-2 toxicity round added 32 more, while recovering real molecule identities for 110 of 143 v1-extraction-artefact placeholders, reducing benchmark placeholder contamination from 31.1% to 4.1%; the 80 cumulative EXPAND accepts are queued for promotion into the benchmark_split in a future release. The v4→v5 revision deleted 1 computational off-target row (id=156) to reach 100% observed-experimental coverage. The portal also exposes Safety Dossier generation, HELM-aware base parsing, evidence graph export, W3C PROV-compatible provenance output, NLWeb-style tool discovery, Bioschemas JSON-LD, sequence-to-evidence triage, modification/delivery profiles, NAR-style case workflows, core oligo field curation packets, independent second-review packets, and benchmark task cards. Full sequence alignment remains pending until release-grade sequence fields are curated.

Important claim boundary: OligoVigil should currently be described as a provenance-rich safety/off-target evidence database, not as a complete sequence/modification/dose catalog. The current release exposes the missing sequence, chemistry, delivery, dose, exposure, and model fields through a prioritized curation packet instead of silently inflating them.

This repository is intentionally dependency-light. The local release uses only Python standard library and SQLite so it can run anywhere. A future production deployment can move the same schema to PostgreSQL and FastAPI/Django.

## Quick Start

```powershell
cd C:\Users\Jie\Desktop\NAR_OligoSafetyDB\repo_ready
python scripts\init_db.py
python scripts\discover_pubmed_sources.py
python scripts\ingest_pubmed_sources.py --load-db
python scripts\generate_curation_queue.py
python scripts\build_curation_candidates.py
python scripts\export_curator_review_template.py
python app\server.py
```

Open:

```text
http://127.0.0.1:8077
```

Run the mechanical smoke test while the server is running:

```powershell
python scripts\smoke_test.py
python scripts\build_release_manifest.py
python scripts\final_delivery_check.py
```

## API

- `GET /api/health`
- `GET /api/stats`
- `GET /api/metadata`
- `GET /api/summary`
- `GET /api/facets`
- `GET /api/quality`
- `GET /api/coverage`
- `GET /api/examples`
- `GET /api/ask?q=Show%20GalNAc%20liver%20toxicity%20Grade%20A%2FB%20evidence`
- `GET /api/help`
- `GET /api/curation_protocol`
- `GET /api/data_availability`
- `GET /api/release_status`
- `GET /api/submission_pack`
- `GET /api/field_completeness`
- `GET /api/core_oligo_fields`
- `GET /api/independent_validation`
- `GET /api/novelty_position`
- `GET /api/archive_readiness`
- `GET /api/adoption_packet`
- `GET /api/download_manifest`
- `GET /api/downloads`
- `GET /api/citation`
- `GET /api/offtarget_taxonomy`
- `GET /api/safety_triage?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&delivery=GalNAc&endpoint=hepatic&species=human`
- `GET /api/safety_dossier?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&delivery=GalNAc&endpoint=hepatic&species=human`
- `GET /api/evidence_graph?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&delivery=GalNAc&endpoint=hepatic&species=human`
- `GET /api/prov_graph?sequence=AUGCUACUGACUGA&target=PCSK9&modification=GalNAc&delivery=GalNAc&endpoint=hepatic&species=human`
- `GET /bioschemas.json`
- `GET /nlweb.json`
- `GET /.well-known/nlweb.json`
- `GET /api/use_cases`
- `GET /api/case_workflows`
- `GET /api/sequence_coverage`
- `GET /api/sequence_search?sequence=AUGCUACUGACUGA&modification=GalNAc&target=PCSK9`
- `GET /api/modification_profile?term=galnac`
- `GET /api/client_examples`
- `GET /api/submission_schema`
- `GET /api/openapi.json`
- `GET /api/search?q=toxicity`
- `GET /api/source_detail?q=hepatotoxicity`
- `GET /api/readiness`
- `GET /api/closest_work`
- `GET /api/data_dictionary`
- `GET /api/sources`
- `GET /api/molecules`
- `GET /api/evidence`
- `GET /api/evidence_records`
- `GET /api/evidence_detail?domain=toxicity&id=1`
- `GET /api/benchmark`
- `GET /api/benchmark_baseline_results`
- `GET /api/benchmark_tasks`
- `GET /api/agent_access`
- `GET /api/agent_connect`
- `GET /agent.json`
- `GET /.well-known/oligovigil-agent.json`
- `GET /.well-known/ai-plugin.json`
- `GET /mcp.json`
- `GET /llms.txt`
- `GET /llms-full.txt`
- `GET /api/audit`
- `GET /api/curation_queue`
- `GET /api/curation_candidates`
- `GET /api/download/source_document.csv`
- `GET /api/download/molecule.csv`
- `GET /api/download/toxicity_endpoint.csv`
- `GET /api/download/offtarget_evidence.csv`
- `GET /api/download/curation_audit.csv`
- `GET /api/download/benchmark_split.csv`
- `GET /api/download/curation_queue.csv`
- `GET /api/download/curation_candidate.csv`
- `GET /api/download/curation_candidates_filtered.csv`
- `GET /api/download/evidence_release.csv`
- `GET /api/download/benchmark_reference_splits.csv`
- `GET /api/download/benchmark_task_cards.csv`
- `GET /api/download/sequence_modification_curation_template.csv`
- `GET /api/download/core_oligo_field_curation_packet.csv`
- `GET /api/download/independent_curation_validation_template.csv`
- `GET /api/download/all_tables.zip`
- `GET /api/manifest/source_candidates_v1.csv`
- `GET /api/manifest/source_candidates_v2.csv`
- `GET /api/manifest/source_candidates_v3.csv`
- `GET /api/manifest/source_candidates_v4.csv`
- `GET /api/manifest/source_candidates_v5.csv`
- `GET /api/manifest/source_candidates_v6.csv`
- `GET /api/manifest/license_manifest_v1.csv`
- `GET /api/manifest/source_license_manifest_v1.csv`
- `GET /api/manifest/closest_work_matrix_v1.csv`
- `GET /api/manifest/data_dictionary_v1.csv`
- `GET /api/manifest/source_document_pubmed_v1.csv`
- `GET /api/manifest/curation_queue_v1.csv`
- `GET /api/manifest/curation_candidate_v1.csv`
- `GET /api/manifest/curator_review_template_v1.csv`
- `GET /api/manifest/sequence_modification_curation_template_v1.csv`
- `GET /api/manifest/core_oligo_field_curation_packet_v1.csv`
- `GET /api/manifest/independent_curation_validation_template_v1.csv`
- `GET /api/manifest/benchmark_task_cards_v1.csv`
- `GET /api/manifest/pubmed_discovery_candidates_v1.csv`
- `GET /api/manifest/pubmed_discovery_candidates_v2.csv`
- `GET /api/manifest/pubmed_discovery_candidates_v3.csv`
- `GET /api/manifest/pubmed_discovery_candidates_v4.csv`

## Web Portal Architecture

The portal is organized as a workbench instead of a single long landing page. The homepage prioritizes search, task entry points, verified release counts, benchmark access, and downloads. Detailed data views are separated into:

- Search: global source, candidate, toxicity, and off-target lookup.
- Ask: grounded read-only natural-language query assistant over verified release evidence with exposed query plan, citations, and candidate-exclusion guardrails.
- Sequence: sequence parsing, seed-window display, sequence/modification curation coverage, template download, and linked off-target/modification evidence lookup without claiming full alignment before sequence fields are curated.
- Examples: one-click example-result workflows for GalNAc liver safety, siRNA seed off-target evidence, ASO/gapmer hepatotoxicity, renal/platelet scanning, and benchmark reuse.
- Modification: delivery/chemistry safety profiles for terms such as GalNAc, LNP, phosphorothioate, LNA, PMO, ASO, and siRNA.
- Use Cases: task-oriented entry points plus NAR-style case workflows for GalNAc-siRNA liver safety, ASO/gapmer hepatotoxicity, renal/thrombocytopenia scan, and siRNA seed/off-target evidence.
- Record: single verified evidence record with source metadata, audit trail, and citation/BibTeX text.
- Benchmark: deterministic Grade A/B reference splits, DOI-pending release contract, task cards, and baseline metric guidance.
- Release: current release gates, batch status, access policy, public-URL blocker, field completeness, and the prioritized core oligo field upgrade queue.
- Trust: curation protocol, reviewer audit path, release/candidate boundary, provenance coverage, independent second-review status, and license/redistribution policy.
- Help: chaptered user guide covering inputs, evidence grades, benchmark reuse, downloads, troubleshooting, and citation.
- Cite: global citation text, BibTeX, record-citation guidance, and benchmark-citation policy.
- API: copy-ready Python, R, and shell client snippets.
- Submit: curator-reviewed contribution/correction schema and review-template links.
- Quality: release readiness and gate checks.
- Coverage: source-year, journal, domain, modality, and release-gap summaries.
- Curation: triage candidates and queue tasks.
- Evidence: verified evidence explorer and audit records.
- Sources: source-level provenance packet lookup plus source and molecule tables.
- Closest-work audit: novelty boundary against theRNA, siRNAEfficacyDB, CMsiRNAdb, siRNAmod, CRISPR off-target resources, DrugBank, and TTD.
- Downloads: CSV, ZIP, manifest, and API documentation links.

This keeps the first viewport readable while preserving direct hash links for reviewers and users, for example `/#ask`, `/#examples`, `/#record`, `/#benchmark`, `/#trust`, `/#release`, `/#help`, `/#cite`, and `/#downloads`.

## Docker

```powershell
cd C:\Users\Jie\Desktop\NAR_OligoSafetyDB\repo_ready
docker compose up --build
```

## Data Policy

OligoVigil release tables contain machine pre-curated (v1) derived annotations, source metadata, source locations, audit decisions, and source links. Third-party raw article text, PDFs, and full source documents are not redistributed unless source terms explicitly allow it.

`curation_candidate` records are derived triage annotations only. They store matched terms, source locations, extraction metadata, and pending curator decisions, not raw abstract text and not release-grade evidence claims.

`core_oligo_field_curation_packet_v1.csv` is a worklist for source-verified sequence, modification, delivery, dose, exposure, and model curation. It must not be cited as completed structured coverage until rows are manually verified and promoted.

`independent_curation_validation_template_v1.csv` is a 500-row second-review template with release accept rows and rejected candidate controls. Inter-curator agreement, Cohen kappa, and error-rate estimates are not manuscript claims until reviewer-2 decisions are completed and adjudicated.

Promotion into `toxicity_endpoint` or `offtarget_evidence` is gated by `scripts/promote_curator_review.py`. The script only accepts rows marked `curator_decision=accept`, `validation_status=curator_verified`, and evidence grades `A/B/C`. Curator identity may be redacted in the database, but accepted rows must retain a verified source location and an audit note.

No abstract-level batch-promotion script is shipped. The promotion gate requires `validation_status=curator_verified`.

**Curation provenance (important).** The v1 release tables were produced by an automated keyword/regex classifier (`scripts/curate_release_scale_batch*.py`), not by human review; an independent re-adjudication of a stratified sample estimated ~74% false-accept. Those 2003 machine candidates were then re-screened by a source-grounded LLM curator (`scripts/curate_v2_llm.py`, exclusion-first with a verbatim grounding-quote gate) and independently re-curated over the source passages by the human curator of record, **Ni Jie (University of Innsbruck, Digital Science Center)**, who recorded the final accept/reject decision row by row (`scripts/apply_recuration_verdicts.py`; `curator_id='ni_jie'`). Result: **737 human curator-verified release rows** (626 toxicity + 111 off-target after the v5→v6 collaborator round added 48 curator-verified records, the v6→v6.1 EXPAND-2 toxicity round added 32 more, and the v4→v5 R4 deletion of 1 computational off-target row); 1,345 candidates not supported by their source were demoted and removed from the release tables. Machine-only audit rows are labelled `validation_status='machine_precurated_v1'` (`curator_id='machine_v1_keyword_classifier'` or null) and are **not** release evidence; only the human curator rows carry `validation_status='curator_verified'`. This was AI-assisted human curation — the curator adjudicated the LLM proposals against the sources rather than reviewing blind (on the 2003 rows the human overrode 27 of the LLM's firm accept/reject decisions, recovered 33 LLM-abstained rows as accepts, and adjusted 92 evidence grades), so it is disclosed as such. It is a **single-curator** review by one person (`ni_jie`); a 100-row mixed accept+reject inter-rater study with an independent second curator (HY, no manuscript exposure) yields **Cohen κ_binary = 0.34** (Landis-Koch "fair"; raw agreement 67%). HY is systematically stricter than `ni_jie` (92% reject-confirm, 40% accept-confirm) — the conservative direction for a safety database; 42 disagreement rows are queued for third-adjudicator routing (`04_delivery/handoffs/KAPPA2_mixed_sample/disagreements.csv`). The earlier release-only KAPPA-1 (n=100, c1=all accept) gives a conditional-on-accept Grade-axis κ = 0.21 and 52% raw decision agreement; KAPPA-2 supersedes KAPPA-1 for the load-bearing binary κ.

## Data Availability Draft

The current Docker release exposes a no-login web portal and REST API with CSV/ZIP downloads. The primary citable release files are `evidence_release.csv`, `source_document.csv`, `molecule.csv`, `curation_audit.csv`, `benchmark_reference_splits.csv`, `benchmark_task_cards.csv`, `benchmark_baseline_results.csv`, `license_manifest_v1.csv`, `source_license_manifest_v1.csv`, and `data_dictionary_v1.csv`. File sizes, row counts, checksums, and file-specific reuse notes are exposed through `/api/downloads` and `/api/data_availability`.

Before NAR submission, replace the pending placeholders with a stable public HTTPS URL, archive DOI, code repository DOI or release tag, final freeze date, maintainer contact, and correction route. The local release deliberately does not claim public adoption, citation impact, or long-term URL availability before deployment.

## Delivery Package

After final QA passes:

```powershell
python scripts\build_release_manifest.py
python scripts\build_delivery_package.py
```

This creates a timestamped OligoVigil package and zip under `C:\Users\Jie\Desktop\NAR_OligoSafetyDB_delivery`.

Every release record must include:

- source URL and PMID/PMCID/DOI where applicable;
- source location when available;
- extraction method;
- validation status;
- curator decision;
- evidence grade.

## Presubmission Gate

Before any NAR presubmission query:

- public HTTPS URL works without login or registration;
- downloads work without email collection;
- source and reuse terms are documented;
- no fake institution, fake staffing, fake uptime, fake URL, or unverified credentials;
- CRISPR guide records are excluded from the core database.
