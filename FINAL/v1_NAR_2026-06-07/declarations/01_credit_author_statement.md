---
title: "CRediT Author Contribution Statement"
subtitle: "OligoVigil submission to Nucleic Acids Research, Database Issue"
date: "2026-06-07"
---

# CRediT Author Contribution Statement

This statement follows the Contributor Roles Taxonomy (CRediT) as adopted by Nucleic Acids Research and Oxford University Press. The 14 standard CRediT roles are: Conceptualisation, Data Curation, Formal Analysis, Funding Acquisition, Investigation, Methodology, Project Administration, Resources, Software, Supervision, Validation, Visualisation, Writing — Original Draft, and Writing — Review & Editing.

Role assignments below follow the convention used in the team's Octo-Agent / ESWA 2026-06-07 submission (same author group; PI-confirmed mapping).

**Jie Ni** — Conceptualisation; Methodology; Software; Investigation; Formal analysis; Data curation; Visualisation; Writing — original draft; Project administration.

**Xinting Zhang** — Investigation; Data curation; Validation.

**Zhuoying Xie** — Investigation; Visualisation.

**Shan Lu** — Resources; Writing — review & editing.

**Yun Liu** — Conceptualisation; Supervision; Writing — review & editing; Resources; Funding acquisition.

**Adam Jatowt** — Supervision; Writing — review & editing; Resources.

## Notes specific to OligoVigil

- **Data Curation (Jie Ni).** Sole human curator of record (`curator_id = 'ni_jie'` in `curation_audit`). Adjudicated every one of the 1,168 firm LLM proposals plus 835 LLM-abstain cases on the 2,003 candidate pool; signed off on the 658-row human-verified release and on every override decision (20 over-accepts caught, 7 over-rejects caught, 33 abstains recovered, 92 grades adjusted).
- **Validation (Jie Ni, with Xinting Zhang).** Designed and executed the v1 forward-validation experiment (false-accept rate 0.73, 66/90, 95% CI ±0.09, n = 126); designed the 1,345-source demotion audit; confirmed the 657/658 observed-experimental coverage figure. **Inter-curator agreement (Cohen's κ) is not claimed** because adjudication was performed by a single human curator; this is disclosed as a limitation in §Limitations(3) of the manuscript.
- **Methodology (Jie Ni).** Designed the three-stage candidate-then-LLM-then-human architecture with the candidate-vs-release firewall (the LLM never writes a curator decision); defined the toxicity (n = 263 = 218/23/22) and off-target (n = 81 = 66/5/10) benchmark splits; defined the 477 Grade A/B versus 133 not-benchmarked separation; designed the cross-split contamination audit that surfaced the 9 toxicity `molecule_id`s and 4 off-target source papers requiring the pair-level isolation invariant.
- **Software (Jie Ni).** Implemented the curation pipeline, the 70,283-task work queue, the v2 LLM-curator under exclusion-first + verbatim-grounding-quote constraints, the QA suites (`smoke_test.py`, `frontend_contract_check.py`, `final_delivery_check.py`), the public web portal (no-login REST API + OpenAPI + MCP + Bioschemas + W3C PROV), and the release scripts that produced `evidence_release.csv`, `benchmark_reference_splits.csv`, `curation_audit.csv`, and `v2_human_override_decisions.csv`.
- **Writing — Original Draft (Jie Ni).** Drafted the entire manuscript including the honesty-locked numbers (release 658, benchmark 344, target-gene-only 12.9%, sequence/chemistry 0%, FAR 0.73).
- **Writing — Review & Editing (all).** A post-curation copy-editing pass on the manuscript text used a large-language-model in an editorial role under a hard "numbers-and-honesty-caveats are locked" constraint (Yuan1z0825/nature-skills polishing skill, see `06_genai_disclosure.md`). All authors are responsible for the final wording.
- **Funding acquisition (Yun Liu).** See `04_funding.md`.
- **Supervision (Yun Liu, Adam Jatowt).** Provided scientific oversight; reviewed all major design decisions including the candidate/release firewall and the honesty-led framing of the curation-integrity remediation.
- **Resources (Shan Lu, Yun Liu, Adam Jatowt).** Provided institutional research-computing resources used to run the v2 LLM curator and the QA suites (institutional facilities at Southeast University, Nanjing Medical University and the University of Innsbruck; see `04_funding.md` for the full acknowledgement).

## Author identities (locked, ORCID-validated)

| Author | Affiliations | ORCID | Email |
| --- | --- | --- | --- |
| **Jie Ni** (corresp.) | SEU (1), UIBK DSC (2), NJMU (3) | `0009-0003-9767-5441` | njie@seu.edu.cn |
| Xinting Zhang | SEU (1) | `0009-0005-0158-3679` | xtzhang@seu.edu.cn |
| Zhuoying Xie | SEU (1) | `0000-0003-3534-1924` | zyxie@seu.edu.cn |
| Shan Lu | First Affil. Hosp. NJMU, Women & Children Dept (4) | `0009-0004-3088-5070` | lushan_sd@njmu.edu.cn |
| **Yun Liu** (corresp.) | SEU (1), First Affil. Hosp. NJMU, Information Dept (5) | `0000-0002-4311-3772` | liuyun@njmu.edu.cn |
| **Adam Jatowt** (corresp.) | UIBK DSC (2) | `0000-0001-7235-0665` | adam.jatowt@uibk.ac.at |

(1) State Key Laboratory of Digital Medical Engineering, School of Biological Science and Medical Engineering, Southeast University, Nanjing 211102, China.
(2) Digital Science Center, University of Innsbruck, Innsbruck 6020, Austria.
(3) Department of Medical Informatics, School of Biomedical Engineering and Informatics, Nanjing Medical University, Nanjing 211166, China.
(4) Women and Children Department, The First Affiliated Hospital, Nanjing Medical University, Nanjing 210029, China.
(5) Department of Information, The First Affiliated Hospital, Nanjing Medical University, Nanjing 210029, China.

---

*All six ORCID iDs have been checksum-validated (ISO 7064 MOD 11-2). For NAR ScholarOne submission, each co-author should link the matching ORCID iD to their Editorial Manager account when invited.*
