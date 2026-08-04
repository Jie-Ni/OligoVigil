# OligoVigil v1.0.2 release QA

## Release counts

- Evidence records: 737
- Toxicity records: 626
- Off-target records: 111
- Release-linked primary studies: 660
- Release-linked molecules: 524
- Release audit rows: 737
- Benchmark split rows: 344

## Identifier checks

- PMCID values use canonical `PMC` identifiers.
- PMID, DOI, PMCID, and source URLs remain linked to release records.
- Evidence, source, molecule, and audit tables use the same release scope.

## Bundle checks

- `all_tables.zip` is deterministic.
- Bundle bytes: 326,772
- Bundle SHA-256: `839c02e7f3914b67fb628e70e5bcd6bdc13d872c7428c9f8196db95ae2d22b66`
- The bundle contains release evidence, release-linked sources and molecules, release audit rows, benchmark files, the data dictionary, and license metadata.

## Versioned access

- Archived snapshot: v1.0.1, DOI `10.5281/zenodo.20633779`
- Current web release: v1.0.2, <https://oligovigil.pages.dev/>
