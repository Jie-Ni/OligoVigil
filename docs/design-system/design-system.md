# OligoVigil Design System

Version: `20260604_resource_depth_v42`

OligoVigil is a scientific database workbench, not a landing page. The visual layer should make evidence search, provenance inspection, benchmark reuse, and downloads feel reliable within the first few seconds.

## Direction

The system uses a restrained scientific editorial interface: light neutral surfaces, compact panels, stable tables, one teal action accent, one plum provenance accent, and minimal shadows. AI-generated images are allowed only as orientation assets; they must not compete with evidence, search, or release status.

## Tokens

Use the values in [manifest.json](manifest.json) as the source of truth.

- Page surface: `#f5f7f8`
- Panel surface: `#ffffff`
- Text: `#17202a`, `#536270`, `#748290`
- Border: `#d8e0e4`, subtle `#e8edf0`
- Accent: teal `#0f766e`, hover `#0b5f59`
- Provenance accent: plum `#7c3a4d`
- Warning: amber `#9a5b12`

Typography uses self-hosted IBM Plex Sans for UI text and IBM Plex Mono for code, checksums, and citations. System fonts remain fallbacks only.

- Page title: 29px, weight 700
- Section title: 21px, weight 600
- Card title: 15px, weight 700
- Body: 14px, line-height 1.55
- Label/caption: 12px, weight 500
- Table body: 13px, line-height 1.5
- Data numerals: 24px, tabular, weight 700

Spacing follows an 8px rhythm. Component padding should be 12px or 16px; section gaps should be 24px. Do not introduce arbitrary spacing unless it is solving a measured layout defect.

## Layout

The product shell has a compact sticky header and horizontal nav tabs. The header must stay below one compact product row on desktop and below a short brand row plus nav scroller on mobile/tablet.

The overview page prioritizes:

1. Search
2. Release status and access/readiness signals
3. Verified counts
4. Main workflows
5. Supporting imagery, only at secondary visual weight

Internal pages use a consistent pattern:

- `section-head` for title and actions
- filter toolbar or compact controls
- table/list result region
- optional secondary panels below or beside the main workflow

Tables should stay tables. Do not convert dense evidence records into decorative cards.

## Components

Buttons:
Primary buttons are filled teal and should represent the main action in a local workflow. Secondary actions are white bordered links. Avoid multiple large primary blocks in one viewport.

Cards and panels:
Cards are for repeated items, metrics, or framed tools. They use 8px radius, subtle border, and at most a barely visible panel shadow. Avoid card-inside-card composition.

Badges:
Badges are small metadata or semantic state markers. They should not be used as decorative punctuation.

Images:
Use the hero provenance image on the overview page and the provenance network image on the workflow page. Keep them secondary to data and controls.

Homepage icons:
Use icons inside task entries where they improve recognition. Do not place a separate signal-icon grid in the first viewport unless it solves a concrete navigation problem.

Tables:
Tables use sticky headers, compact rows, left-aligned text, and contained horizontal scroll. Header typography should be 12px, semibold, and muted.

Downloads:
Release files are presented through a grouped manifest rather than a flat link wall. Each public file must show rows, size, SHA256, schema, recommended use, and reuse policy.

Agent Connect:
Agent-oriented reuse is presented as universal manifests, connection profiles, installable artifacts, guardrails, and workflows, not as a visible code wall. Show agent.json, OpenAPI, MCP config, llms.txt, optional Skill, SDK clients, prompts, templates, checksums, and download actions through compact cards and details.

## v42 Resource Depth Addendum

The homepage should behave like a database workbench entry point: search, release counts, evidence/off-target/benchmark workflows, then supporting imagery. Evidence detail pages must read as citable evidence cards with record key, evidence statement, grade rationale, provenance status, sequence/chemistry completeness, and reuse limitations. Off-target evidence is a first-class mechanism view within Evidence. Sequence pages must lead with curation coverage and remain clearly framed as evidence lookup, not sequence-specific prediction.

Search and provenance:
Search results must include molecule/cohort hits and direct `Open` actions for verified toxicity/off-target records. Record pages must link back to source provenance packets.

Sequence:
The sequence workbench is an evidence lookup surface only. It must not imply genome/transcriptome alignment, 3'UTR seed scanning, sequence-specific off-target prediction, or candidate risk ranking until curator-verified sequence fields are populated.

## Accessibility And QA

Every control needs visible focus. Touch targets on mobile should be at least 40px high, preferably 44px. The page must have no page-level horizontal overflow at 375px, 768px, and 1440px. Metadata and badges must remain readable at mobile width.

## Anti-Patterns

Do not ship:

- Tall mobile nav that consumes half the viewport
- Card walls that make every section look equally important
- Decorative gradients, glass panels, glow shadows, or generic SaaS hero composition
- Large repeated icon tiles where search, tables, or filters would be clearer
- Random font sizes outside the type scale
- Yellow pill tags repeated across every card
- More than two strong primary action areas visible at once
