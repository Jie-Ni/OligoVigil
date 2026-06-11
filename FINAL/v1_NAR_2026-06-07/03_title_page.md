# Title page

## Title

**OligoVigil: a curator-verified, source-anchored database of safety and off-target evidence for therapeutic oligonucleotides**

## Running title (≤50 chars)

OligoVigil: curated ASO/siRNA safety evidence *(48 characters)*

## Authors

Jie Ni¹,²,³,\*, Xinting Zhang¹, Zhuoying Xie¹, Shan Lu⁴, Yun Liu¹,⁵,\*, and Adam Jatowt²,\*

¹ State Key Laboratory of Digital Medical Engineering, School of Biological Science and Medical Engineering, Southeast University, Nanjing 211102, Jiangsu, China
² Digital Science Center, University of Innsbruck, Innsbruck 6020, Tirol, Austria
³ Department of Medical Informatics, School of Biomedical Engineering and Informatics, Nanjing Medical University, Nanjing 211166, Jiangsu, China
⁴ Women and Children Department, The First Affiliated Hospital, Nanjing Medical University, Nanjing 210029, Jiangsu, China
⁵ Department of Information, The First Affiliated Hospital, Nanjing Medical University, Nanjing 210029, Jiangsu, China

\* Corresponding authors.

## ORCID identifiers

| Author | ORCID |
| --- | --- |
| Jie Ni (corresponding) | `0009-0003-9767-5441` — <https://orcid.org/0009-0003-9767-5441> |
| Xinting Zhang | `0009-0005-0158-3679` — <https://orcid.org/0009-0005-0158-3679> |
| Zhuoying Xie | `0000-0003-3534-1924` — <https://orcid.org/0000-0003-3534-1924> |
| Shan Lu | `0009-0004-3088-5070` — <https://orcid.org/0009-0004-3088-5070> |
| Yun Liu (corresponding) | `0000-0002-4311-3772` — <https://orcid.org/0000-0002-4311-3772> |
| Adam Jatowt (corresponding) | `0000-0001-7235-0665` — <https://orcid.org/0000-0001-7235-0665> |

All six ORCID iDs have been checksum-validated (ISO 7064 MOD 11-2). For NAR submission via ScholarOne, each co-author should link the matching ORCID iD to their EM account when invited.

## Corresponding author contact

| Corresponding author | E-mail |
| --- | --- |
| **Jie Ni** (lead corresponding) | njie@seu.edu.cn |
| Yun Liu | liuyun@njmu.edu.cn |
| Adam Jatowt | adam.jatowt@uibk.ac.at |

## Co-author e-mail addresses

| Author | E-mail |
| --- | --- |
| Xinting Zhang | xtzhang@seu.edu.cn |
| Zhuoying Xie | zyxie@seu.edu.cn |
| Shan Lu | lushan_sd@njmu.edu.cn |

## Funding

This work received no external funding. The computational results reported in this manuscript were obtained on the Austrian Scientific Computing (ASC) federated MUSICA cluster (site Linz, MUSICA-LNZ), supplemented by the LEO5 high-performance computing facility at the University of Innsbruck. We thank the operators of both sites for compute allocations that made this study possible.

## Acknowledgements

We thank the operators of the Austrian Scientific Computing (ASC) federated MUSICA cluster and the LEO5 high-performance computing facility at the University of Innsbruck for compute allocations that made this study possible.

## Declarations summary

- **Conflict of interest:** The authors declare that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.
- **Data availability:** Release data (737 curator-verified records: 626 toxicity + 111 off-target; audit trail, benchmark splits, deterministic baselines), schema, API and code are openly available without login at `https://oligovigil.pages.dev/`; the versioned release snapshot is archived at Zenodo DOI `10.5281/zenodo.20633779`. Full statement: `declarations/03_data_availability.md`.
- **Inter-rater agreement:** A second independent curator reviewed a 100-row mixed accept+reject stratified sample (KAPPA-2); binary Cohen κ = **0.34** (fair, per Landis-Koch); the second curator is systematically stricter than the curator of record (a safety-conservative direction). The pilot 100-row KAPPA-1 release-only round (κ not computable; Grade-axis κ = 0.21) is superseded. Full inter-rater treatment in §Methods Stage 3.
- **Code availability:** Curation scripts, QA suites, baseline reproducibility code and the portal source are released under the MIT License (code) and CC BY 4.0 (derived annotations); see `LICENSE` and `LICENSE-DATA` in the repository.
- **Ethics:** No human subjects, animal experiments or identifiable personal data were involved; the resource is derived from published preclinical literature.
- **AI-assisted curation disclosure:** A documented AI-assisted human curation workflow was used (Stage-2 source-grounded LLM proposals with verbatim grounding gate, followed by single-human adjudication); the firewall between machine proposals and human decisions is enforced in the data model and audited per record. See `declarations/06_genai_disclosure.md`.
- **Author contributions (CRediT):** see `declarations/01_credit_author_statement.md`. Summary: **Jie Ni** — Conceptualisation; Methodology; Software; Investigation; Formal analysis; Data curation; Visualisation; Writing — original draft; Project administration. **Xinting Zhang** — Investigation; Data curation; Validation. **Zhuoying Xie** — Investigation; Visualisation. **Shan Lu** — Resources; Writing — review & editing. **Yun Liu** — Conceptualisation; Supervision; Writing — review & editing; Resources. **Adam Jatowt** — Supervision; Writing — review & editing; Resources.

## Word counts and item counts (computed from 02_manuscript_unblinded.md, 2026-06-10)

- Abstract: **192 words**
- Main text (Introduction through Future directions, excluding figure captions, declarations and references): **2,987 words**
- Number of figures: **6** (Figure 1: curation pipeline; Figure 2: evidence-object architecture; Figure 3: evidence landscape; Figure 4: web portal walkthrough; Figure 5: peer comparison; Figure 6: validation dashboard)
- Number of tables: **0**
- Number of references: **31** verified references; no citation placeholders in the main manuscript

## Submission

Date: \[TBD: YYYY-MM-DD on submission\]
Manuscript type: Database Article (NAR Database Issue 2027 cycle)
