# OligoVigil Component Map

Version: `20260604_resource_depth_v42`

## Source Files

- HTML shell: `app/static/index.html`
- Styles: `app/static/styles.css`
- Client rendering: `app/static/app.js`
- Logo/favicon: `app/static/logo.svg`, `app/static/favicon.svg`
- Generated images: `app/static/assets/generated/`

## Shell

`topbar`, `brand-lockup`, `primary-nav`

Rules:

- Header is compact and sticky on desktop.
- Navigation is a tab row, not a wrapped button wall.
- On small screens, nav scrolls inside its own container instead of increasing page width.

## Overview

`overview-layout`, `overview-main`, `gate-panel`, `hero-search-bar`, `visual-band`, `stats-grid`, `task-grid`, `novelty-strip`, `signal-strip`

Rules:

- Search is the main action.
- Resource status is the right-side trust panel.
- Release/reuse panel exposes verified evidence, benchmark rows, DOI/archive status, public URL status, and primary reuse actions.
- Hero image supports provenance orientation and should be visually quiet.
- Task buttons are secondary workflow entries, not primary CTA blocks.
- Signal tiles remain available in markup but are not shown on the first viewport; task icons are the preferred homepage icon pattern.

## Data Surfaces

`table-wrap`, `table`, `split`, `search-results`, `quality-grid`, `benchmark-grid`, `summary-grid`

Rules:

- Data tables keep real table structure.
- Table overflow must remain inside `table-wrap`.
- Repeated metric cards use consistent padding and data typography.
- Search includes sources, molecules/cohorts, candidates, toxicity records, and off-target records.
- Verified record rows expose an `Open` action that navigates to the citable record page.

## Downloads

`download-summary`, `download-manifest-grid`, `download-section`

Rules:

- Downloads are grouped by Core release, Benchmark, Curation and audit, and Manifests.
- Each row shows file, purpose, recommended use, rows, size, SHA256, and schema.
- Long checksums and filenames wrap inside table cells; page-level horizontal overflow is not allowed.

## Agent Connect

`agent-summary-grid`, `agent-tool-grid`, `agent-connector-grid`, `agent-artifact-grid`, `agent-rule-list`, `agent-workflow-list`

Rules:

- Agent-facing reuse is shown through buttons, compact cards, connection profiles, guardrails, and checksum details.
- Do not place SDK or MCP source code directly in the visible page.
- Artifacts must map to real files in `agent_ready/`, `/agent.json`, `/api/openapi.json`, `/mcp.json`, and `/api/download/oligovigil_agent_pack.zip`.
- Guardrails must keep release evidence, candidate gaps, no-prediction policy, and benchmark split policy explicit.

## Provenance

`record-detail-card`, `source-detail-card`, `source-detail-*`

Rules:

- Record detail links to source, source provenance packet, JSON, and release CSV.
- Source detail shows verified release evidence before queue/candidate context.
- Reuse policy is human-readable; raw article text redistribution limits should not be exposed only as internal enum names.

## Workflow Cards

`example-result-card`, `tool-card`, `quality-card`, `profile-card`, `record-detail-card`, `source-detail-card`

Rules:

- 8px radius, 1px border, 12px or 16px padding.
- No large shadows.
- Metadata tags are small and subdued.
- Example result cards use a list-like desktop layout with stable title, question, metadata, metrics, and actions regions.
- Use concise titles and real endpoint actions.

## Controls

`button`, `button-link`, `inline-actions`, `sequence-controls`, `queue-controls`, `toolbar`

Rules:

- Primary filled button only for the main action in the local control group.
- Secondary links are bordered and white.
- Inputs and selects share height, border, radius, focus ring, and typography.

## Known Gaps

- No server-side rendered loading placeholders; initial async regions can remain blank for a short period.
- No formal visual regression test suite yet; current QA relies on browser screenshot inspection and contract/smoke checks.
- A public HTTPS deployment is still required before NAR presubmission.
