# OligoVigil Visual QA v35

Version: `20260603_formal_submission_ui_v35`

Context: five user-agent review pass before NAR-style submission hardening. Personas covered oligonucleotide drug discovery, toxicology review, RNAi/off-target use, ML benchmark reuse, and NAR editor/resource evaluation.

## v40 Agent Access Addendum

Date: `2026-06-04`

Scope: added an Agent Access route for coding-agent and vibe-coding reuse without exposing a visible SDK/code wall.

Checks:

- Desktop `1440x920`: 6 summary cards, 11 real artifacts, 5 guardrail cards, 4 workflow cards, 0 visible `pre`/code blocks, 0 page-level overflow.
- Mobile `375x840`: page-level horizontal overflow absent, topbar 127px, 0 visible `pre`/code blocks, scrollable nav overflow only.
- Console errors: 0.
- Agent pack excludes `__pycache__` and `.pyc` files.

Artifact:

- `C:/Users/Jie/Desktop/codex/oligovigil_v40_agent_access_desktop.png`

## v41 Universal Agent Connect Addendum

Date: `2026-06-04`

Scope: expanded the agent route from Codex-friendly access to tool-agnostic vibe-coding access.

Checks:

- Agent page exposes universal manifest, OpenAPI, MCP config, llms.txt, full guide, access metadata, well-known manifest, action manifest, and agent pack actions.
- Desktop `1440x920`: 8 summary cards, 5 tool profile cards, 5 universal entrypoint cards, 16 artifact cards, 5 guardrails, 5 workflows, 0 visible `pre`/code blocks, 0 page-level overflow.
- Mobile `375x840`: page-level horizontal overflow absent; only the expected horizontally scrollable nav links extend inside the nav scroller; 0 visible `pre`/code blocks.
- Console errors: 0.
- `/agent.json`, `/.well-known/oligovigil-agent.json`, `/.well-known/ai-plugin.json`, `/mcp.json`, and `/api/agent_connect` return no-login JSON payloads.
- Visible UI remains button/card based; SDK, MCP, and client source code stay inside downloadable artifacts.

Artifact:

- `C:/Users/Jie/Desktop/codex/oligovigil_v41_universal_agent_connect_desktop.png`

## Changes From v34

- Promoted `Sources`, `Downloads`, and `API` into the primary navigation; moved Ask/Sequence/Examples into workflow entry points.
- Rebuilt Downloads from a flat link wall into a grouped manifest with rows, bytes, SHA256, schema, recommended use, and reuse policy.
- Added molecule/cohort search results and record-level `Open` actions to toxicity/off-target search tables.
- Added source provenance packet links from citable record pages and moved verified source evidence above queue/candidate context.
- Reworded sequence UI as evidence lookup only, with explicit no-alignment/no-seed-scan/no-risk-ranking guardrails.
- Preserved underscores in API paths, filenames, benchmark task names, and citation strings.
- Replaced Windows Segoe-first rendering with self-hosted IBM Plex Sans and IBM Plex Mono, reduced excessive label/badge weights, and increased table text to 13px for denser but cleaner reading.

## Browser QA

Automated checks:

- `frontend_contract_check=pass`
- `smoke_test=pass`
- `final_delivery_check=pass`
- `node --check app/static/app.js`
- `python -m py_compile app/server.py scripts/frontend_contract_check.py scripts/smoke_test.py scripts/final_delivery_check.py scripts/build_benchmark_task_cards.py`

Viewport checks:

| Viewport | Page | Result |
|---|---|---|
| 1440x920 | Overview | no page-level horizontal overflow; topbar 87px; generated hero image loaded |
| 1440x920 | Search | `GalNAc hepatotoxicity` returns molecules, toxicity records, off-target records, and record buttons |
| 1440x920 | Downloads | 4 manifest sections; no page-level horizontal overflow |
| 1440x920 | Sources | verified sources appear before source detail context |
| 1440x920 | Sequence | sequence limitation notice visible; release/candidate evidence tables contained |
| 375x840 | Overview | no page-level horizontal overflow; topbar 116px; primary buttons 44px high |
| 375x840 | Downloads | page-level overflow absent; wide manifest tables scroll inside `.table-wrap` only |
| 375x840 | Sequence | invalid sequence clears previous results and displays evidence-lookup warning |

Artifacts:

- `C:/Users/Jie/Desktop/codex/OligoVigil_v35_five_agent_qa/desktop_overview.png`
- `C:/Users/Jie/Desktop/codex/OligoVigil_v35_five_agent_qa/desktop_search.png`
- `C:/Users/Jie/Desktop/codex/OligoVigil_v35_five_agent_qa/desktop_downloads.png`
- `C:/Users/Jie/Desktop/codex/OligoVigil_v35_five_agent_qa/desktop_sources.png`
- `C:/Users/Jie/Desktop/codex/OligoVigil_v35_five_agent_qa/desktop_sequence.png`
- `C:/Users/Jie/Desktop/codex/OligoVigil_v35_five_agent_qa/visual_metrics_v35.json`

## Remaining Submission Blockers

- Public HTTPS deployment is still required before NAR presubmission.
- DOI/archive should remain pending until the public release is frozen.
- Exact sequence-alignment claims remain blocked until curator-verified sequence/modification strings are added.
