# OligoVigil

OligoVigil is a curator-verified, source-anchored resource for safety and off-target evidence on therapeutic oligonucleotides.

- Web release: [v1.0.2](https://oligovigil.pages.dev/)
- Archived data snapshot: [v1.0.1](https://doi.org/10.5281/zenodo.20633779)
- Data license: CC BY 4.0
- Code license: MIT

## Release scope

The public release contains 737 human curator-verified observations: 626 toxicity records and 111 off-target records from 660 primary studies. It also provides 737 release audit rows and 344 fixed Grade A/B benchmark split rows.

The machine stage produced a 2,003-record candidate pool. Independent source-grounded re-adjudication of a stratified sample of 126 records found 66 false accepts among 90 machine-accepted records, corresponding to a false-accept rate of 0.73 (Wilson 95% CI 0.63–0.81). Human adjudication produced the released observations; 1,345 records remained outside the release.

## Run locally

OligoVigil uses the Python standard library and SQLite.

```powershell
python app\server.py --host 127.0.0.1 --port 8077
```

Open `http://127.0.0.1:8077/`.

## Public release files

- `evidence_release.csv`: unified toxicity and off-target evidence
- `source_document.csv`: 660 release-linked primary-study records
- `molecule.csv`: 524 release-linked molecule/cohort records
- `curation_audit.csv`: 737 release audit records
- `benchmark_reference_splits.csv`: 344 fixed Grade A/B split assignments
- `benchmark_task_cards.csv`: benchmark definitions and reporting fields
- `benchmark_baseline_results.csv`: deterministic reference baselines
- `data_dictionary_v1.csv`: field definitions for the public tables
- `source_license_manifest_v1.csv`: release-linked provenance and reuse metadata
- `all_tables.zip`: deterministic release bundle

The machine-readable download manifest at `/api/download_manifest` provides row counts, byte counts, and SHA-256 checksums.

## Core endpoints

- `GET /api/metadata`
- `GET /api/stats`
- `GET /api/evidence_records`
- `GET /api/sources`
- `GET /api/curation_protocol`
- `GET /api/independent_validation`
- `GET /api/data_availability`
- `GET /api/download_manifest`
- `GET /api/benchmark`

## Static export

Build the Cloudflare Pages artifact from a running local server:

```powershell
python scripts\export_cloudflare_pages_static.py `
  --base-url http://127.0.0.1:8077 `
  --public-base-url https://oligovigil.pages.dev `
  --output public_final_build
```

The export contains the release portal, release-scoped API snapshots, CSV files, manifests, and deterministic ZIP bundle.
