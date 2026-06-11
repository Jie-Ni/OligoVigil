\[TBD: date\]

To the Editor-in-Chief  
*Nucleic Acids Research*, Database Issue

Dear Editor,

We submit **"OligoVigil: a curator-verified, source-anchored database of safety and off-target evidence for therapeutic oligonucleotides"** for consideration as a new database entry in the *NAR* Database Issue (target length 4-5 typeset pages).

The existing oligonucleotide-database landscape catalogues **on-target efficacy** (theRNA; siRNAEfficacyDB; CMsiRNAdb; siRNAmod) or a different molecular class entirely (CRISPRoffT). It does not provide a curator-verified, source-anchored evidence layer for the two liabilities that now drive preclinical attrition of ASOs and siRNAs: chemistry- and accumulation-driven safety toxicity, and sequence-independent off-target effects (seed-mediated and hybridization-dependent). OligoVigil fills exactly that gap. The single best argument for the resource is its **honest curation accounting**: every one of the **737** release records (626 toxicity + 111 off-target after the v6.1 within-team collaborator round) carries a verbatim source-grounded human accept decision, the upstream machine pre-curation stage was independently audited at a measured **0.73 false-accept rate (Wilson 95% CI [0.63, 0.81])** on a 126-record stratified sample, and 1,345 unsupported machine-proposed candidates were demoted rather than released. A firewall in the data model prevents any machine output from being presented as human curation. The resource doubles as a benchmark-ready **344-row evaluation seed** (toxicity 263 / off-target 81) with deterministic prior baselines and pair-level (source × molecule) split isolation; following the v6 collaborator round, placeholder benchmark contamination is reduced from 31.1% (107 / 344) to **4.1% (14 / 344)** and full integration of the 80 new EXPAND-1 + EXPAND-2 records into the benchmark splits is a future-release roadmap item. The portal ships **no-login** with documented REST, OpenAPI, MCP, Bioschemas JSON-LD and W3C PROV interfaces, and a SQL view `release_audit_v` so downstream users join cleanly against the human-verified subset of the audit table.

Following the v5 referee revision, a within-team collaborator round reduced placeholder benchmark contamination from 31.1% to 4.1%, added 48 curator-verified records, and conducted a pilot second-curator review of 100 release rows (52% raw agreement; full κ characterisation in Stage 3 of the Methods). The v6.1 round added a further 32 toxicity records (total 737 = 626 tox + 111 off-target) and a second 100-row inter-rater study from an independent curator; we report Cohen kappa binary under both the textbook drop-abstain convention (n=92) and the safety-conservative collapse-abstain convention (n=100), giving 0.42 (moderate, Landis-Koch) and 0.34 (fair) respectively, with the second curator systematically stricter; a third-blinded-adjudicator packet (A10) has been prepared and is expected to push the post-adjudication kappa(curator-of-record vs consensus) into substantial Landis-Koch territory.

The database is **freely accessible without login** at **https://oligovigil.pages.dev/**; we commit to maintenance for **at least five years** under HTTPS, with the versioned release snapshot archived at Zenodo DOI **10.5281/zenodo.20633779**. The submission complies with *NAR*'s pre-print policy, is not under concurrent consideration elsewhere, and the authors declare that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper. The work received no external funding; computation was carried out on institutional research-computing facilities at Southeast University, Nanjing Medical University and the University of Innsbruck. Limitations (single curator, pair-level not molecule-level isolation, currently provenance-rich rather than sequence/chemistry-complete) are disclosed explicitly in the manuscript rather than smoothed over.

Institutional e-mail addresses for all six authors are provided on the title page and in the submission system. A 13-feature comparison against five existing oligonucleotide databases is provided as Supplementary Table S8. As reviewers, with no prior collaboration, we suggest the six candidates listed in `suggested_reviewers_final_6.md`.

We believe OligoVigil is a precise fit for the Database Issue: it is a new community resource, openly accessible, programmatically reusable, and built to a standard of curation transparency we hope will be useful as a template for safety-oriented evidence databases. All six authors have approved this submission.

Sincerely,

Jie Ni, on behalf of the authors
State Key Laboratory of Digital Medical Engineering, Southeast University
Digital Science Center, University of Innsbruck
Department of Medical Informatics, Nanjing Medical University
E-mail: njie@seu.edu.cn
