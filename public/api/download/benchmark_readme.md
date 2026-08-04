# OligoVigil benchmark reference splits

Web maintenance release: v1.0.2  
Manuscript-cited archive: v1.0.1, DOI 10.5281/zenodo.20633779  
Website: https://oligovigil.pages.dev/

## Release

The reference benchmark is built from the 737 curator-verified OligoVigil observations: 626 toxicity records and 111 off-target records from 660 primary studies. The fixed Grade A/B reference splits contain 344 rows.

## Tasks

| task_name | target | train | validation | test | Grade A | Grade B |
|---|---|---:|---:|---:|---:|---:|
| toxicity_safety_v0_1 | toxicity endpoint category | 218 | 23 | 22 | 180 | 83 |
| offtarget_safety_v0_1 | off-target evidence type | 66 | 5 | 10 | 32 | 49 |

## Eligibility and split policy

Reference rows have a curator-verified accept audit, evidence grade A or B, an explicit toxicity or off-target domain, and source plus molecule/cohort fields sufficient to form a leakage group.

Rows sharing a source-paper and molecule/cohort leakage group remain in one split within each task. The 344-row reference split has zero cross-split leakage-group violations.

## Files

| file | bytes | SHA-256 |
|---|---:|---|
| benchmark_reference_splits.csv | 145,896 | 4679ebdc25fff41e80cd54882e4d6baf782a1b7c49be18c69dff43cb2617f3ed |
| benchmark_task_cards.csv | 1,517 | 83c12152448c2edb92148f0601d1c86e573018b698bbe43bceba415aa72b20c8 |
| benchmark_baseline_results.csv | 5,108 | b6066d0b1b5cebb92e97bfdd32fc7c1b171ba08c023a2428bdbec14e7542bf9d |
| evidence_release.csv | 542,459 | ca8099474448db9f626849e7a20f400f518cbc697614a78395ec31be3a3ccbcc |

## Reporting

Report the OligoVigil version, task name, split-file checksum, evaluation split, metric definition, and source-paper plus molecule/cohort grouping policy with benchmark results. Cite the manuscript-cited v1.0.1 archive using DOI 10.5281/zenodo.20633779.
