---
title: "CRediT Author Contribution Statement"
subtitle: "OligoVigil submission to Nucleic Acids Research, Database Issue"
date: "2026-06-11"
---

# CRediT Author Contribution Statement

This statement follows the Contributor Roles Taxonomy (CRediT) as adopted by Nucleic Acids Research and Oxford University Press. The 14 standard CRediT roles are: Conceptualisation, Data Curation, Formal Analysis, Funding Acquisition, Investigation, Methodology, Project Administration, Resources, Software, Supervision, Validation, Visualisation, Writing — Original Draft, and Writing — Review & Editing.

Role assignments below follow the CRediT taxonomy and have been prepared for author confirmation before submission.

**Jie Ni** — Conceptualisation; Methodology; Software; Investigation; Formal analysis; Data curation; Visualisation; Writing — original draft; Project administration.

**Xinting Zhang** — Investigation; Data curation; Validation.

**Zhuoying Xie** — Investigation; Visualisation.

**Shan Lu** — Resources; Writing — review & editing.

**Yun Liu** — Conceptualisation; Supervision; Writing — review & editing; Resources.

**Adam Jatowt** — Supervision; Writing — review & editing; Resources.

## Notes specific to OligoVigil

- **Data Curation (Jie Ni).** Sole human curator of record (`curator_id = 'ni_jie'` in `curation_audit`). Adjudicated the 2,003-candidate proposal pool and signed off on curator-verified release decisions and grade assignments.
- **Validation (Jie Ni, with Xinting Zhang).** Designed and executed the machine-stage false-accept audit (66/90 false accepts among v1 accept calls; Wilson 95% CI [0.63, 0.81]), the candidate-demotion audit, the release-row audit reconciliation and the second-curator reliability analyses reported in the manuscript.
- **Methodology (Jie Ni).** Designed the three-stage candidate-then-model-then-human architecture with the candidate-vs-release firewall; defined the toxicity and off-target benchmark splits; and specified the pair-level source-by-molecule isolation invariant.
- **Software (Jie Ni).** Implemented the curation pipeline, the 70,283-task work queue, the v2 LLM-curator under exclusion-first + verbatim-grounding-quote constraints, the QA suites (`smoke_test.py`, `frontend_contract_check.py`, `final_delivery_check.py`), the public web portal (no-login REST API + OpenAPI + MCP + Bioschemas + W3C PROV), and the release scripts that produced `evidence_release.csv`, `benchmark_reference_splits.csv`, `curation_audit.csv`, and `v2_human_override_decisions.csv`.
- **Writing - Original Draft (Jie Ni).** Drafted the manuscript and assembled the numerical claim audit supporting the reported release, benchmark and validation counts.
- **Writing - Review & Editing (all).** Reviewed and revised the manuscript. All authors are responsible for the final wording.
- **Supervision (Yun Liu, Adam Jatowt).** Provided scientific oversight and reviewed major design decisions including the candidate/release firewall and curation-integrity framework.
- **Resources (Shan Lu, Yun Liu, Adam Jatowt).** Provided institutional, domain and research-computing resources used to run the curation workflows and QA suites; the computational work used the Austrian Scientific Computing (ASC) federated MUSICA cluster and the LEO5 high-performance computing facility at the University of Innsbruck (see `04_funding.md` for the full acknowledgement).

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

*All six ORCID iDs have been checksum-validated (ISO 7064 MOD 11-2).*
