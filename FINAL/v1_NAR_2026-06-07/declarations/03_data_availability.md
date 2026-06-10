---
title: "Data and Code Availability Statement"
subtitle: "OligoVigil submission to Nucleic Acids Research"
date: "2026-06-10"
---

# Data and Code Availability Statement

## Web portal

The OligoVigil web portal will be freely accessible without login or registration at:

**`[TBD: public HTTPS URL]`**

The portal supports browsing, free-text search, filtered evidence tables, per-record provenance display, curation-audit inspection, benchmark downloads and programmatic access through REST/OpenAPI, MCP, Bioschemas JSON-LD and W3C PROV-compatible exports.

## Versioned release archive

A frozen, citable snapshot of the release corresponding to this manuscript will be deposited at:

**`[TBD: Zenodo or Figshare DOI]`**

The archive will contain the exact files backing the manuscript counts: 737 human curator-verified release records, 626 toxicity endpoints, 111 off-target observations, 660 primary release sources, the source-license manifest, curation-audit exports, benchmark reference splits, deterministic baseline outputs, schema documentation and checksums.

## Source code

The curation scripts, release QA scripts, web portal, API implementation, baseline code and figure-generation scripts will be available at:

**`https://github.com/Jie-Ni/OligoVigil`**

## Licensing

- **Code:** MIT License.
- **Curated derived annotations and release tables:** Creative Commons Attribution 4.0 International (CC BY 4.0).
- **Third-party source text and PDFs:** not redistributed. OligoVigil redistributes derived annotations, identifiers, source locations and limited evidence snippets for provenance; users must access the underlying articles through the cited publisher, PubMed, PMC or institutional route.

## Itemised release downloads

All release files will be available as individual downloads and as `all_tables.zip`.

| File | Rows | Description |
|---|---:|---|
| `evidence_release.csv` | 737 | Human curator-verified release records: 626 toxicity endpoints and 111 off-target observations. |
| `benchmark_reference_splits.csv` | 344 | Grade A/B reference benchmark split with pair-level source-by-molecule isolation. |
| `curation_audit.csv` | 70,283 queue tasks | Full candidate and audit trail; the SQL view `release_audit_v` isolates release-linked human-verified rows. |
| `source_license_manifest_v1.csv` | 36,245 sources | Per-source identifiers, licence/reuse classification and redistribution scope. |
| `v1_classifier_far_audit_n126.csv` | 126 | Machine-stage false-accept-rate audit supporting the reported 0.73 FAR estimate. |
| `v2_human_override_decisions.csv` | 2,003 | Per-candidate proposal, grounding and human decision summary for the Stage-2/Stage-3 curation gate. |
| `schema.sql` / `schema_dictionary.csv` | n/a | Relational schema and field-level data dictionary. |
| `all_tables.zip` | n/a | Bundle of the tables above with README and SHA256 checksums. |

## Long-term maintenance

The authors commit to maintaining the OligoVigil web portal and downloadable release files at the canonical public URL for at least five years from publication. Versioned archival snapshots will remain available through the DOI independently of portal uptime. If the portal is migrated, redirects from the original URL and update notices on the DOI landing page and public repository will be maintained.

## Reproducibility

All numerical claims in the manuscript are tied to the 2026-06-08 release snapshot after the EXPAND-2 and KAPPA-2 updates. The shipped release files reproduce the headline counts: 737 release records, 626 toxicity records, 111 off-target records, 344 benchmark rows, 36,245 indexed source documents, 70,283 curation tasks, 41,114 candidate annotations, 1,345 demoted candidates, 105/111 populated off-target-gene-status rows and a 0.73 machine-stage false-accept-rate estimate from the 126-row audit.

---

*[TBD before submission: insert final public URL and archive DOI.]*
