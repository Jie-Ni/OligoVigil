# OligoVigil Visual QA v34

Date: 2026-06-03
Version: `20260603_public_release_ui_v34`
Status: `visual_release_candidate_local_pass`

## Design Review Verdict

The portal now presents as a restrained scientific database workbench rather than an ad hoc dashboard. The first viewport prioritizes search, release status, verified counts, workflow entry points, and citable downloads. Decorative signal tiles were removed from the first viewport; generated imagery remains secondary to evidence workflows.

## Key Fixes

- Compressed the product header from a two-row brand/nav block into a compact sticky shell.
- Hid native horizontal nav scrollbars while retaining mobile swipe navigation.
- Reduced the overview image height and removed the separate signal-icon grid from the first viewport.
- Tightened statistic cards and workflow entries to reduce first-screen density.
- Converted Example Results from tall stacked cards into a scan-friendly workflow list on desktop.
- Kept mobile and tablet headers sticky and deep-link safe.
- Preserved the generated hero provenance image and provenance workflow image as secondary evidence visuals.

## Browser Metrics

| Viewport | Page | Header | Overflow | Hero | Provenance | Notes |
|---|---:|---:|---|---|---|---|
| 1440x920 | overview | 87px | no | loaded | loaded | signal grid hidden |
| 768x900 | overview | 121px | no | loaded | loaded | tablet nav contained |
| 375x840 | overview | 117px | no | loaded | loaded | sticky mobile header |
| 1440x920 | examples | 87px | no | loaded | loaded | desktop list layout |
| 375x840 | examples | 117px | no | loaded | loaded | mobile single-column layout |

## Screenshots

- `docs/design-system/screenshots/v34/desktop_overview_final.png`
- `docs/design-system/screenshots/v34/tablet_overview_final.png`
- `docs/design-system/screenshots/v34/mobile_overview_final.png`
- `docs/design-system/screenshots/v34/desktop_examples_final.png`
- `docs/design-system/screenshots/v34/mobile_examples_final.png`
- `docs/design-system/screenshots/v34/visual_metrics_v34.json`

## Technical QA

- `node --check app/static/app.js`: pass
- `python -m py_compile app/server.py scripts/frontend_contract_check.py scripts/smoke_test.py scripts/final_delivery_check.py scripts/build_benchmark_task_cards.py scripts/build_release_manifest.py scripts/build_delivery_package.py`: pass
- `python scripts/frontend_contract_check.py`: pass
- `python scripts/smoke_test.py`: pass
- `python scripts/final_delivery_check.py`: pass

## Remaining Deployment Gate

The local portal has passed technical and visual review; public operation still requires deployment to a stable HTTPS URL with no login requirement.
