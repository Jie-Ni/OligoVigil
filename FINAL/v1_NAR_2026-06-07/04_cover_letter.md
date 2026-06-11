11 June 2026

To the Editor-in-Chief  
*Nucleic Acids Research*, Database Issue

Dear Editor,

We submit "OligoVigil: a curator-verified, source-anchored database of safety and off-target evidence for therapeutic oligonucleotides" for consideration as a new database entry in the *NAR* Database Issue.

The existing oligonucleotide-database landscape mainly catalogues on-target efficacy (theRNA; siRNAEfficacyDB; CMsiRNAdb; siRNAmod) or a different molecular class entirely (CRISPRoffT). It does not provide a curator-verified, source-anchored evidence layer for the two liabilities that now drive preclinical attrition of ASOs and siRNAs: chemistry- and accumulation-driven safety toxicity, and sequence-independent off-target effects. OligoVigil addresses this gap. The current release contains 737 curator-verified records (626 toxicity + 111 off-target), each with a verbatim source-grounded human accept decision. The upstream machine pre-curation stage was independently audited at a measured 0.73 false-accept rate (Wilson 95% CI [0.63, 0.81]) on a 126-record stratified sample, and 1,345 unsupported machine-proposed candidates were demoted rather than released. A firewall in the data model prevents machine output from being presented as human curation. The resource also provides a 344-row Grade A/B evaluation seed with deterministic prior baselines and pair-level source-by-molecule split isolation; residual placeholder contamination in this benchmark is 4.1% (14 / 344). The portal is freely accessible without login and exposes documented REST, OpenAPI, MCP, Bioschemas JSON-LD and W3C PROV interfaces, plus a SQL view `release_audit_v` for joining against the human-verified audit subset.

The release includes an inter-rater layer. An initial 100-row second-curator review of release rows yielded 52% raw decision agreement and Grade-axis Cohen kappa = 0.21 on the 52 jointly accepted rows. A subsequent 100-row mixed accept/reject review by an independent second curator yielded binary Cohen kappa = 0.42 under the drop-abstain convention (n=92) and kappa = 0.34 under the safety-conservative collapse-abstain-to-reject convention (n=100). The second curator was systematically stricter on accepted rows, and a third-adjudicator packet has been prepared for the remaining disagreement rows.

The database is freely accessible without login at https://oligovigil.pages.dev/; we commit to maintenance for at least five years under HTTPS, with the versioned release snapshot archived at Zenodo DOI 10.5281/zenodo.20633779. The submission complies with *NAR*'s pre-print policy, is not under concurrent consideration elsewhere, and the authors declare that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper. The work received no external funding; computation was carried out on the Austrian Scientific Computing (ASC) federated MUSICA cluster and the LEO5 high-performance computing facility at the University of Innsbruck. The manuscript explicitly states the current limitations, including single-curator primary adjudication, pair-level rather than molecule-level benchmark isolation, and incomplete sequence, chemistry and dose metadata.

Institutional e-mail addresses for all six authors are provided on the title page and in the submission system. A 13-feature comparison against five existing oligonucleotide databases is provided as Supplementary Table S8. As reviewers, with no prior collaboration, we suggest the six candidates listed in `suggested_reviewers_final_6.md`.

We believe OligoVigil is a strong fit for the Database Issue: it is a new community resource, openly accessible, programmatically reusable, and built around transparent curation and source-level provenance. All six authors have approved this submission.

Sincerely,

Jie Ni, on behalf of the authors
State Key Laboratory of Digital Medical Engineering, Southeast University
Digital Science Center, University of Innsbruck
Department of Medical Informatics, Nanjing Medical University
E-mail: njie@seu.edu.cn
