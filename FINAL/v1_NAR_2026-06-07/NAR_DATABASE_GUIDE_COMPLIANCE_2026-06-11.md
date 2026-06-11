# NAR Database Issue guide-compliance pass

Guide source: https://academic.oup.com/nar/pages/Ms_Prep_Database  
Checked date: 2026-06-11

## Result

The upload-facing OligoVigil submission package has been revised against the NAR Database Issue manuscript-preparation page. No blocking local-format issue remains in the manuscript files, declarations, graphical abstract, suggested-reviewer file or upload checklist.

## Checked items

| NAR Database Issue requirement | OligoVigil status |
|---|---|
| New submissions require a functional database URL for suitability review. | Pass: `https://oligovigil.pages.dev/` returned HTTP 200 on 2026-06-11. |
| Database must be freely available on the web, without login, registration or password. | Pass: stated in abstract-adjacent access text, data availability and checklist. |
| Title should start with database name. | Pass: title starts with `OligoVigil`. |
| Abstract and article must include a valid database URL. | Pass: URL appears in abstract and data availability. |
| Manuscript should be a brief factual database description focused on content and access. | Pass: manuscript frames results as database content, curation, access, validation and limitations. |
| Homepage should not be used as a main-text figure; representative query output is allowed. | Pass after revision: Figure 4 is described as representative query and record-output views. |
| Six suggested referees with names, institutes and email addresses. | Pass: `suggested_reviewers_final_6.md`. |
| Graphical abstract is mandatory. | Pass: `figures/graphical_abstract.tif` and `.pdf` are present. |
| Graphical abstract technical requirements: landscape, 5:2, TIF/EPS/editable PDF, 300-600 dpi, sans-serif 12-16 pt. | Pass for available files: 6000 x 2400 pixels, 5:2, 600 dpi, TIF/PDF outputs. |
| Website should preferably use HTTPS. | Pass: `https://oligovigil.pages.dev/`. |
| Database should be accessible and legible on phone and tablet screens, and this compatibility should be mentioned. | Pass after revision: manuscript and data availability now state responsive desktop/tablet/phone access. |
| Database expected to be maintained under the same URL for at least 5 years. | Pass after revision: data availability and checklist state 5-year URL and download maintenance. |
| Availability of underlying data, including download formats and terms, must be addressed. | Pass after revision: CSV, SQL/schema, JSON/API, ZIP/checksums, CC BY 4.0 and MIT terms stated. |
| References must be sequentially numbered; no submitted/in preparation/unpublished/personal-communication citations. | Pass by local text audit. |

## Local checks performed

- Public URL check: `https://oligovigil.pages.dev/` returned HTTP 200.
- Graphical abstract check: `graphical_abstract.png`, `graphical_abstract.tif`, `graphical_abstract_blinded.png` and `graphical_abstract_blinded.tif` are 6000 x 2400 at 600 dpi.
- Upload-facing markdown ASCII check: passed.
- Placeholder, stale-state and encoding-risk scans passed for the upload-facing manuscript, declaration and supplement files.
