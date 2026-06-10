# OligoVigil Prompt Pack

Use these prompts with coding agents or research agents. Replace the base URL with the public OligoVigil deployment after release.

## Safety Evidence Question

You are using OligoVigil as a source-grounded evidence database. Search verified release evidence for: `{question}`. Use candidate records only as non-citable gap context. For each claim, return evidence domain, evidence grade, molecule/cohort, endpoint or off-target type, source location, PMID/DOI, and the `/api/evidence_detail` URL. Do not infer clinical safety if no verified release record supports the claim.

## Oligo Design Triage

Given sequence `{sequence}`, target `{target}`, modification `{modification}`, delivery `{delivery}`, endpoint focus `{endpoint}`, and species `{species}`, call `/api/safety_triage`. Summarize release-supported concerns, candidate gaps, missing external checks, and record-level citations. State clearly that OligoVigil does not perform de novo sequence alignment or clinical safety prediction.

## Benchmark Reuse

Use `/api/benchmark`, `benchmark_reference_splits.csv`, `benchmark_task_cards.csv`, and `benchmark_baseline_results.csv`. Build a reproducible benchmark report that includes task name, split strategy, leakage policy, target field, metrics, OligoVigil version, split checksum, and baseline comparison. Do not change the reference split groups.

## Curation Gap Review

Use `/api/curation_candidates` and `/api/source_detail` to identify candidate evidence that may deserve human review. Do not promote candidates automatically. Return source PMID/DOI, exact source location, candidate signal, suggested grade, and what a curator must verify.
