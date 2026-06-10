---
name: oligovigil
description: Use OligoVigil to retrieve curator-verified therapeutic oligonucleotide safety and off-target evidence, source provenance, benchmark splits, citation text, and archive/readiness metadata. Trigger when users ask for ASO or siRNA safety evidence, off-target evidence, GalNAc or chemistry safety, benchmark reuse, or citable OligoVigil records.
---

# OligoVigil

Use OligoVigil as a source-grounded database for therapeutic oligonucleotide safety evidence. The resource separates curator-verified release evidence from machine-derived candidate gaps.

## Base URL

Prefer the public deployment URL when available. For local testing, use `http://127.0.0.1:8077`.

## Core Rules

- Use release evidence for factual claims. Candidate records are gap-finding context only.
- Never infer that an oligonucleotide is clinically safe from OligoVigil alone.
- Cite record-level provenance for safety or off-target claims: `/api/evidence_detail?domain={toxicity|offtarget}&id={id}`.
- Include source PMID/DOI, OligoVigil version, evidence grade, and source location when summarizing records.
- Do not redistribute raw article text. Use derived annotations, source metadata, and source links.
- Keep benchmark claims tied to `benchmark_reference_splits.csv`, task cards, version, leakage policy, and checksums.

## Main Endpoints

- `/api/search?q={query}`: unified search across sources, molecules, candidates, toxicity, and off-target records.
- `/api/evidence_records?domain=toxicity&q={query}`: verified release evidence.
- `/api/evidence_detail?domain=toxicity&id=1`: citable record packet with audit trail.
- `/api/safety_triage`: source-grounded triage report for sequence, target, chemistry, delivery, endpoint, and species.
- `/api/sequence_search`: sequence parsing plus evidence lookup, not de novo alignment.
- `/api/modification_profile?term=galnac`: chemistry or delivery profile.
- `/api/benchmark`: benchmark metadata, split policy, and baseline status.
- `/api/download/evidence_release.csv`: unified verified release table.
- `/api/download/benchmark_reference_splits.csv`: fixed Grade A/B benchmark splits.
- `/api/download/all_tables.zip`: full reproducible data snapshot.

## Workflows

### Safety Evidence Lookup

1. Search with `/api/search?q={molecule target endpoint chemistry}`.
2. Prefer release rows over candidate rows.
3. Open `/api/evidence_detail` for each claim-worthy record.
4. Summarize evidence grade, endpoint, source location, source PMID/DOI, and audit status.

### Design Triage

1. Call `/api/safety_triage` with sequence, target, modification, delivery, endpoint, and species when available.
2. Treat the result as an evidence packet, not a predictor.
3. Separate release-supported concerns from candidate gaps.
4. Recommend additional curation or external alignment only when the portal marks the gap.

### Benchmark Reuse

1. Download `benchmark_reference_splits.csv`, `benchmark_task_cards.csv`, and `evidence_release.csv`.
2. Keep leakage groups unchanged.
3. Report metrics from task cards and compare against the diagnostic baseline table.
4. Cite OligoVigil version, task name, split checksum, and release checksum.

## Refusal Conditions

Do not answer with an OligoVigil-backed safety conclusion if no verified release record supports it. Say that the current release has no curator-verified evidence for the claim, then mention candidate gaps only as non-citable context.
