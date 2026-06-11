from __future__ import annotations

import re
from pathlib import Path


FINAL = Path("C:/Users/Jie/Desktop/NAR_OligoSafetyDB/repo_ready/FINAL/v1_NAR_2026-06-07")
MANUSCRIPTS = [
    FINAL / "01_manuscript_blinded.md",
    FINAL / "02_manuscript_unblinded.md",
]


ABSTRACT = """## Abstract

Therapeutic antisense oligonucleotides (ASOs), siRNAs and related modalities increasingly depend on chemically modified backbones, conjugates and delivery systems, but the safety and off-target evidence needed to triage these designs remains scattered across primary papers, regulatory documents and transcriptomic studies. Existing oligonucleotide resources mainly catalogue therapeutic targets, modalities, efficacy or chemical modification; they do not provide a source-localized safety evidence layer that separates machine-proposed candidates from human-verified release records. We present **OligoVigil**, a curator-verified database of therapeutic-oligonucleotide safety and off-target evidence. The current release contains **737 human curator-verified evidence records** from **660 primary sources**, comprising **626 toxicity endpoints** and **111 off-target observations**. Each release row is an observed experimental result anchored to an exact in-source location, assigned an evidence grade, and linked to a curation-audit record. The release was produced from **36,245 indexed source documents**, **70,283 curation tasks** and **41,114 candidate annotations** through a candidate-generation stage, a source-grounded proposal gate and row-by-row human adjudication. A provisional 2,003-candidate machine pool had a measured false-accept rate of **0.73** in a 126-row audit, and **1,345 unsupported candidates** were demoted rather than released. OligoVigil also provides a **344-record Grade A/B benchmark** with pair-level (source x molecule) isolation, deterministic baselines, bulk downloads, REST/OpenAPI access, MCP and agent-readable manifests, Bioschemas JSON-LD and W3C PROV exports. A 100-row mixed accept/reject second-curator study yielded **Cohen kappa_binary = 0.42** under the drop-abstain convention and **0.34** when abstentions were collapsed to reject. The resource is deliberately scoped as a provenance-first evidence database, not as a complete sequence, chemistry or dose catalogue: off-target gene status is populated for **105/111** off-target rows, whereas sequence, modification and dose fields remain prioritized curation worklists. Availability: https://oligovigil.pages.dev/; data under CC BY 4.0.

---"""


INTRODUCTION = """## Introduction

Oligonucleotide therapeutics have moved from exceptional cases to an established drug modality. Approved and late-stage agents now include RNase-H ASOs, splice-switching oligonucleotides, siRNA therapeutics, PMOs and chemically stabilized or conjugated designs, with GalNAc delivery making liver-directed RNAi especially tractable [1-7]. This success has shifted a major part of preclinical decision-making from target knockdown to safety and design triage.

Two evidence classes matter most for that triage. The first is chemistry-, dose- and tissue-exposure-driven toxicity, including hepatic, renal, hematologic, complement and innate-immune liabilities [8-10,15-17]. The second is off-target activity, including siRNA seed effects, hybridization or mismatch effects and transcriptome-scale perturbations that may be missed by target-efficacy summaries [10-14]. These observations exist across primary papers, supplementary files and regulatory-style reports, but they are not easy to search, cite or reuse.

The current database landscape answers adjacent questions rather than this one. theRNA provides broad coverage of functional RNA therapeutics [18]. siRNAEfficacyDB, CMsiRNAdb and siRNAmod focus on siRNA efficacy or chemical modification effects on silencing [19-21]. CRISPRoffT curates off-target evidence for CRISPR/Cas systems, a different molecular class [22]. These resources are valuable, but they do not provide a therapeutic-oligonucleotide safety resource in which each toxicity or off-target observation is tied to an exact source location, an explicit human decision and a reusable audit record.

Recent NAR Web Server and Database resources also show that modern biological databases are judged not only by record count, but by whether users can inspect the data, reproduce the analysis path and reuse the resource programmatically [23-31]. Successful resources combine a clear workflow, a content landscape, task-oriented web interfaces, downloads or APIs and transparent maintenance. For oligonucleotide safety, these expectations are especially important, because an unsupported or poorly grounded record can mislead design decisions.

We built OligoVigil to fill that gap. Its central object is a verified evidence row that links oligonucleotide identity, safety or off-target endpoint, exact source provenance, evidence grade, human audit status and benchmark reuse metadata. The remainder of this paper describes the database scope, the curation pipeline and its integrity safeguards (Figure 1), the evidence-object and access architecture (Figure 2), the release evidence landscape (Figure 3), the web portal and reusable access layers (Figure 4), the closest-work audit (Figure 5), the validation dashboard (Figure 6), and the resource's explicit limitations.
"""


DATABASE_CONTENT = """## Database content (current release)

The release contains **737 curator-verified records**: **626 toxicity endpoints** and **111 off-target observations**, drawn from **660 distinct primary sources**, of which **547/737 (74.2%)** are anchored in full text (PMC). Provenance and grading fields are complete: source title, source location, PMID and evidence grade are populated at 100%, and DOI at **733/737 = 99.5%**. The release spans **1,012 distinct molecules** in the molecule table. Figure 3 maps this release as an evidence landscape rather than as a simple count summary, linking modality, evidence domain, endpoint family, evidence grade, reuse state, source year and grounding depth.

**Evidence grade.** Combined, the release holds **233 Grade A, 275 Grade B and 229 Grade C** records. The per-domain Grade A/B/C decomposition is **toxicity 200/210/216** and **off-target 33/65/13**. Grade A/B records are eligible for benchmark use, whereas Grade C records remain release evidence but are excluded from the reference splits.

**Modality.** The main modality classes are siRNA (**328 records**), ASO (**262**), mixed ASO/siRNA contexts (**117**), PMO (**16**) and CpG oligodeoxynucleotide (**4**), with a small tail of miRNA-agomir (**3**), aptamer (**2**), DNA nanostructure (**2**), ASO/RNA mixed (**1**), DNA/RNA heteroduplex (**1**) and PMOplus (**1**) records. The mixed ASO/siRNA bucket grew from 37 to 117 as the EXPAND rounds added records reporting shared chemistry or delivery contexts.

**Toxicity endpoint categories.** v7 toxicity rows are dominated by hepatic endpoints (**337**), followed by general safety (**105**), renal (**42**), mixed-grade toxicity (**34**), immunotoxicity (**24**), chemistry (**21**), delivery (**20**), neurological (**15**), hematologic or hematological (**16 = 10 + 6**), general toxicity (**5**), genotoxicity (**2**) and a five-record mixed tail. These counts sum to all **626** toxicity records.

**Off-target evidence types.** The **111** off-target records split into seed-mediated effects (**44**), hybridization and mismatch effects (**26**), transcriptome-level effects (**24**) and generic off-target or specificity observations (**17**). These categories are the mechanistic groupings most useful for design triage.

**Placeholder molecule disclosure (elevated from Limitations).** Of the 737 release rows, **31 of the v6 release rows (4.4% on the v6 705-row denominator)** remain attached to true placeholder molecules after the collaborator B2 recovery pass, a 78% reduction from the v5 figure of 143 (21.8%). The B2 round resolved **110 of the 143 v5 placeholder rows**: 70 underlying real molecule names were recovered from the source and merged onto canonical molecule_ids, and a further 42 records were split onto PMID-scoped placeholders that restore pair-level isolation even when the molecule name remains unrecoverable. Of the **344 benchmark rows**, **14 (4.1%)** remain on placeholders, down from **107/344 (31.1%)** at v5. The 80 EXPAND-1 and EXPAND-2 additions have not yet been promoted into benchmark splits; promotion under the pair-isolation invariant is a near-term roadmap item.
"""


WEB_PORTAL = """## Web portal and programmatic access

OligoVigil follows the access pattern of durable NAR-style web resources: the same evidence object is exposed through a human-facing portal, citable record pages, bulk downloads and machine-readable interfaces [23-31]. Figure 4 shows the current portal workflow. Users can search by molecule, modality, endpoint, source title, PMID, DOI or evidence text; filter by domain, grade, modality and endpoint family; open the source-localized evidence statement; inspect the audit record; export citations; and download filtered evidence or benchmark splits.

The programmatic layer is deliberately first-class rather than an afterthought. OligoVigil exposes a documented REST API, OpenAPI 3.1 description, MCP server manifest, `llms.txt` and `llms-full.txt`, Bioschemas `Dataset` JSON-LD and a W3C PROV-compatible profile. A read-only natural-language query endpoint returns grounded records with citations and an explicit query plan. It links users to source-supported evidence rather than generating de novo risk predictions, and it refuses to fabricate evidence when no supported record is found.
"""


COMPARISON = """## Comparison with existing resources

OligoVigil complements, rather than replaces, existing oligonucleotide resources, because it answers a different question. theRNA catalogues broad functional RNA therapeutics [18]; siRNAEfficacyDB [19], CMsiRNAdb [20] and siRNAmod [21] catalogue siRNA efficacy, silencing or chemical-modification effects; CRISPRoffT addresses a different molecular class [22]. The distinguishing contribution of OligoVigil is a **safety- and off-target-centred, curator-verified, source-anchored, graded and audited evidence layer** with a leakage-aware benchmark.

Figure 5 separates the closest-work audit into two questions. First, the source-PMID comparison shows that the **660** PMIDs supporting OligoVigil release records are disjoint from the PMID-indexed portions of CRISPRoffT (**74**) and siRNAEfficacyDB (**7**), with all pairwise and triple intersections equal to zero. This is structurally plausible rather than a missing-data artefact: CRISPRoffT curates CRISPR/Cas off-targets, and siRNAEfficacyDB indexes efficacy screens rather than preclinical safety or off-target evidence. Second, the feature fingerprint shows that OligoVigil's novelty is not absolute scale or complete chemistry metadata, but exact source-location anchoring, curation-audit transparency, inter-curator reliability reporting, machine-stage false-accept auditing, reference benchmark splits and agent-readable reuse surfaces.

![](C:/Users/Jie/Desktop/NAR_OligoSafetyDB/repo_ready/FINAL/v1_NAR_2026-06-07/figures/FIG5_peer_comparison.png){width=95%}

**Figure 5. Closest-work audit against peer oligonucleotide databases.** (A) Source-PMID disjointness for OligoVigil, CRISPRoffT and siRNAEfficacyDB. The three PMID-indexed sets have zero pairwise and triple overlap, supporting the claim that OligoVigil occupies a distinct literature slice rather than repackaging existing curated records. (B) Feature fingerprint across OligoVigil, theRNA, siRNAEfficacyDB, CMsiRNAdb, siRNAmod and CRISPRoffT. Filled circles indicate published or inspectable support for each resource-level capability; partial support is shown separately from absent or undocumented support. OligoVigil is strongest on provenance, audit, benchmark and programmatic reuse, while remaining weaker on complete chemistry, dose and assay metadata.

This comparison is intentionally conservative. OligoVigil does not claim to be a broad RNA-therapeutics catalogue, a siRNA-efficacy database, a CRISPR off-target database, or a complete sequence and modification catalogue. Its contribution is narrower: a source-grounded safety and off-target evidence layer that downstream users can inspect, cite, download and reuse.
"""


FIGURE_3_BLOCK = """![](C:/Users/Jie/Desktop/NAR_OligoSafetyDB/repo_ready/FINAL/v1_NAR_2026-06-07/figures/FIG3_evidence_landscape_v3.png){width=95%}

**Figure 3. OligoVigil evidence landscape.** (A) Alluvial evidence flow from molecule class through evidence domain, endpoint family, evidence grade and reuse state. Ribbon width is proportional to release-row count, so the panel shows how verified records move from modality to benchmark-eligible or release-only states. (B) Mechanism and endpoint connectivity network linking modality classes to toxicity and off-target evidence families. Edge width encodes the number of curator-verified records. (C) Source-year landscape by domain. Bubble area indicates the number of distinct sources in each year-domain stratum, and fill distinguishes PMC full-text grounding from abstract/metadata grounding. (D) Concentric reusable-evidence state summarizing domain, grade, benchmark eligibility and grounding depth for the 737-record release.
"""


REFERENCES = """## References

1. Egli, M. and Manoharan, M. Chemistry, structure and function of approved oligonucleotide therapeutics. *Nucleic Acids Research* **51**, 2529-2573 (2023). DOI:10.1093/nar/gkad067; PMID:36881759.
2. Shen, X. and Corey, D.R. Chemistry, mechanism and clinical status of antisense oligonucleotides and duplex RNAs. *Nucleic Acids Research* **46**, 1584-1600 (2018). DOI:10.1093/nar/gkx1239; PMID:29240946.
3. Khvorova, A. and Watts, J.K. The chemical evolution of oligonucleotide therapies of clinical utility. *Nature Biotechnology* **35**, 238-248 (2017). DOI:10.1038/nbt.3765; PMID:28244990.
4. Roberts, T.C. et al. Advances in oligonucleotide drug delivery. *Nature Reviews Drug Discovery* **19**, 673-694 (2020). DOI:10.1038/s41573-020-0075-7; PMID:32782413.
5. Springer, A.D. and Dowdy, S.F. GalNAc-siRNA conjugates: leading the way for delivery of RNAi therapeutics. *Nucleic Acid Therapeutics* **28**, 109-118 (2018). DOI:10.1089/nat.2018.0736; PMID:29792572.
6. Juliano, R.L. The delivery of therapeutic oligonucleotides. *Nucleic Acids Research* **44**, 6518-6548 (2016). DOI:10.1093/nar/gkw236; PMID:27084936.
7. Setten, R.L. et al. The current state and future directions of RNAi-based therapeutics. *Nature Reviews Drug Discovery* **18**, 421-446 (2019). DOI:10.1038/s41573-019-0017-4; PMID:30846871.
8. Burel, S.A. et al. Hepatotoxicity of high affinity gapmer antisense oligonucleotides is mediated by RNase H1 dependent promiscuous reduction of very long pre-mRNA transcripts. *Nucleic Acids Research* **44**, 2093-2109 (2016). DOI:10.1093/nar/gkv1210; PMID:26553810.
9. Swayze, E.E. et al. Antisense oligonucleotides containing locked nucleic acid improve potency but cause significant hepatotoxicity in animals. *Nucleic Acids Research* **35**, 687-700 (2007). DOI:10.1093/nar/gkl1071; PMID:17182632.
10. Lindow, M. et al. Assessing unintended hybridization-induced biological effects of oligonucleotides. *Nature Biotechnology* **30**, 920-923 (2012). DOI:10.1038/nbt.2376; PMID:23051805.
11. Jackson, A.L. et al. Expression profiling reveals off-target gene regulation by RNAi. *Nature Biotechnology* **21**, 635-637 (2003). DOI:10.1038/nbt831; PMID:12754523.
12. Jackson, A.L. et al. Widespread siRNA off-target transcript silencing mediated by seed region sequence complementarity. *RNA* **12**, 1179-1187 (2006). DOI:10.1261/rna.25706; PMID:16682560.
13. Birmingham, A. et al. 3' UTR seed matches, but not overall identity, are associated with RNAi off-targets. *Nature Methods* **3**, 199-204 (2006). DOI:10.1038/nmeth854; PMID:16489337.
14. Jackson, A.L. and Linsley, P.S. Recognizing and avoiding siRNA off-target effects for target identification and therapeutic application. *Nature Reviews Drug Discovery* **9**, 57-67 (2010). DOI:10.1038/nrd3010; PMID:20043028.
15. Judge, A.D. et al. Sequence-dependent stimulation of the mammalian innate immune response by synthetic siRNA. *Nature Biotechnology* **23**, 457-462 (2005). DOI:10.1038/nbt1081; PMID:15778705.
16. Hornung, V. et al. Sequence-specific potent induction of IFN-alpha by short interfering RNA in plasmacytoid dendritic cells through TLR7. *Nature Medicine* **11**, 263-270 (2005). DOI:10.1038/nm1191; PMID:15723075.
17. Kleinman, M.E. et al. Sequence- and target-independent angiogenesis suppression by siRNA via TLR3. *Nature* **452**, 591-597 (2008). DOI:10.1038/nature06765; PMID:18368052.
18. Zhou, Y. et al. theRNA: a curated knowledgebase of functional RNA therapeutics spanning diverse modalities and disease applications. *Nucleic Acids Research* **54**, D1672-D1682 (2026). DOI:10.1093/nar/gkaf1064; PMID:41171135.
19. Zhang, Y. et al. siRNAEfficacyDB: an experimentally supported small interfering RNA efficacy database. *IET Systems Biology* **18**, 199-207 (2024). DOI:10.1049/syb2.12102; PMID:39541343.
20. He, S. et al. CMsiRNAdb: a database of chemically modified siRNA silencing efficiency for nucleic acid drug design. *BMC Bioinformatics* **27**, 33 (2026). DOI:10.1186/s12859-025-06359-y; PMID:41484819.
21. Dar, S.A. et al. siRNAmod: a database of experimentally validated chemically modified siRNAs. *Scientific Reports* **6**, 20031 (2016). DOI:10.1038/srep20031; PMID:26818131.
22. Wang, G. et al. CRISPRoffT: comprehensive database of CRISPR/Cas off-targets. *Nucleic Acids Research* **53**, D914-D924 (2025). DOI:10.1093/nar/gkae1025; PMID:39526384.
23. Schultheiss, S.J. Ten simple rules for providing a scientific Web resource. *PLoS Computational Biology* **7**, e1001126 (2011). DOI:10.1371/journal.pcbi.1001126; PMID:21637800.
24. Wilkinson, M.D. et al. The FAIR Guiding Principles for scientific data management and stewardship. *Scientific Data* **3**, 160018 (2016). DOI:10.1038/sdata.2016.18; PMID:26978244.
25. The 23rd annual Nucleic Acids Research Web Server Issue 2025. *Nucleic Acids Research* **53**, W1-W3 (2025). DOI:10.1093/nar/gkaf564; PMID:40580006.
26. Rigden, D.J. and Fernandez, X.M. The 2025 Nucleic Acids Research database issue and the online molecular biology database collection. *Nucleic Acids Research* **53**, D1-D9 (2025). DOI:10.1093/nar/gkae1220; PMID:39658041.
27. Sherman, B.T. et al. DAVID: a web server for functional enrichment analysis and functional annotation of gene lists (2021 update). *Nucleic Acids Research* **50**, W216-W221 (2022). DOI:10.1093/nar/gkac194; PMID:35325185.
28. Liao, Y. et al. WebGestalt 2019: gene set analysis toolkit with revamped UIs and APIs. *Nucleic Acids Research* **47**, W199-W205 (2019). DOI:10.1093/nar/gkz401; PMID:31114916.
29. Zhou, Y. et al. Metascape provides a biologist-oriented resource for the analysis of systems-level datasets. *Nature Communications* **10**, 1523 (2019). DOI:10.1038/s41467-019-09234-6; PMID:30944313.
30. Ruan, Z. et al. Pairpot: a database with real-time lasso-based analysis tailored for paired single-cell and spatial transcriptomics. *Nucleic Acids Research* **53**, D1087-D1098 (2025). DOI:10.1093/nar/gkae986; PMID:39494542.
31. Robert, X. et al. FoldScript: a web server for the efficient analysis of AI-generated 3D protein models. *Nucleic Acids Research* **53**, W277-W282 (2025). DOI:10.1093/nar/gkaf326; PMID:40276967.
"""


BIBTEX = r"""@article{EgliManoharan2023ApprovedOligos,
  author = {Egli, Martin and Manoharan, Muthiah},
  title = {Chemistry, structure and function of approved oligonucleotide therapeutics},
  journal = {Nucleic Acids Research},
  year = {2023},
  volume = {51},
  pages = {2529--2573},
  doi = {10.1093/nar/gkad067},
  pmid = {36881759}
}

@article{ShenCorey2018OligoStatus,
  author = {Shen, Xiulong and Corey, David R.},
  title = {Chemistry, mechanism and clinical status of antisense oligonucleotides and duplex {RNAs}},
  journal = {Nucleic Acids Research},
  year = {2018},
  volume = {46},
  pages = {1584--1600},
  doi = {10.1093/nar/gkx1239},
  pmid = {29240946}
}

@article{KhvorovaWatts2017ChemicalEvolution,
  author = {Khvorova, Anastasia and Watts, Jonathan K.},
  title = {The chemical evolution of oligonucleotide therapies of clinical utility},
  journal = {Nature Biotechnology},
  year = {2017},
  volume = {35},
  pages = {238--248},
  doi = {10.1038/nbt.3765},
  pmid = {28244990}
}

@article{Roberts2020OligoDelivery,
  author = {Roberts, Thomas C. and others},
  title = {Advances in oligonucleotide drug delivery},
  journal = {Nature Reviews Drug Discovery},
  year = {2020},
  volume = {19},
  pages = {673--694},
  doi = {10.1038/s41573-020-0075-7},
  pmid = {32782413}
}

@article{SpringerDowdy2018GalNAcSiRNA,
  author = {Springer, Ashley D. and Dowdy, Steven F.},
  title = {{GalNAc-siRNA} Conjugates: Leading the Way for Delivery of {RNAi} Therapeutics},
  journal = {Nucleic Acid Therapeutics},
  year = {2018},
  volume = {28},
  pages = {109--118},
  doi = {10.1089/nat.2018.0736},
  pmid = {29792572}
}

@article{Juliano2016Delivery,
  author = {Juliano, Rudy L.},
  title = {The delivery of therapeutic oligonucleotides},
  journal = {Nucleic Acids Research},
  year = {2016},
  volume = {44},
  pages = {6518--6548},
  doi = {10.1093/nar/gkw236},
  pmid = {27084936}
}

@article{Setten2019RNAiTherapeutics,
  author = {Setten, Rachel L. and others},
  title = {The current state and future directions of {RNAi}-based therapeutics},
  journal = {Nature Reviews Drug Discovery},
  year = {2019},
  volume = {18},
  pages = {421--446},
  doi = {10.1038/s41573-019-0017-4},
  pmid = {30846871}
}

@article{Burel2016GapmerHepatotoxicity,
  author = {Burel, Sebastien A. and others},
  title = {Hepatotoxicity of high affinity gapmer antisense oligonucleotides is mediated by {RNase H1} dependent promiscuous reduction of very long pre-mRNA transcripts},
  journal = {Nucleic Acids Research},
  year = {2016},
  volume = {44},
  pages = {2093--2109},
  doi = {10.1093/nar/gkv1210},
  pmid = {26553810}
}

@article{Swayze2007LNAHepatotoxicity,
  author = {Swayze, Eric E. and others},
  title = {Antisense oligonucleotides containing locked nucleic acid improve potency but cause significant hepatotoxicity in animals},
  journal = {Nucleic Acids Research},
  year = {2007},
  volume = {35},
  pages = {687--700},
  doi = {10.1093/nar/gkl1071},
  pmid = {17182632}
}

@article{Lindow2012UnintendedHybridization,
  author = {Lindow, Morten and others},
  title = {Assessing unintended hybridization-induced biological effects of oligonucleotides},
  journal = {Nature Biotechnology},
  year = {2012},
  volume = {30},
  pages = {920--923},
  doi = {10.1038/nbt.2376},
  pmid = {23051805}
}

@article{Jackson2003RNAiOffTargetProfiling,
  author = {Jackson, Aimee L. and others},
  title = {Expression profiling reveals off-target gene regulation by {RNAi}},
  journal = {Nature Biotechnology},
  year = {2003},
  volume = {21},
  pages = {635--637},
  doi = {10.1038/nbt831},
  pmid = {12754523}
}

@article{Jackson2006SeedOffTarget,
  author = {Jackson, Aimee L. and others},
  title = {Widespread {siRNA} off-target transcript silencing mediated by seed region sequence complementarity},
  journal = {RNA},
  year = {2006},
  volume = {12},
  pages = {1179--1187},
  doi = {10.1261/rna.25706},
  pmid = {16682560}
}

@article{Birmingham2006SeedMatches,
  author = {Birmingham, Amanda and others},
  title = {3' {UTR} seed matches, but not overall identity, are associated with {RNAi} off-targets},
  journal = {Nature Methods},
  year = {2006},
  volume = {3},
  pages = {199--204},
  doi = {10.1038/nmeth854},
  pmid = {16489337}
}

@article{JacksonLinsley2010AvoidingOffTargets,
  author = {Jackson, Aimee L. and Linsley, Peter S.},
  title = {Recognizing and avoiding {siRNA} off-target effects for target identification and therapeutic application},
  journal = {Nature Reviews Drug Discovery},
  year = {2010},
  volume = {9},
  pages = {57--67},
  doi = {10.1038/nrd3010},
  pmid = {20043028}
}

@article{Judge2005SiRNAInnate,
  author = {Judge, Adam D. and others},
  title = {Sequence-dependent stimulation of the mammalian innate immune response by synthetic {siRNA}},
  journal = {Nature Biotechnology},
  year = {2005},
  volume = {23},
  pages = {457--462},
  doi = {10.1038/nbt1081},
  pmid = {15778705}
}

@article{Hornung2005TLR7SiRNA,
  author = {Hornung, Veit and others},
  title = {Sequence-specific potent induction of {IFN-alpha} by short interfering {RNA} in plasmacytoid dendritic cells through {TLR7}},
  journal = {Nature Medicine},
  year = {2005},
  volume = {11},
  pages = {263--270},
  doi = {10.1038/nm1191},
  pmid = {15723075}
}

@article{Kleinman2008TLR3SiRNA,
  author = {Kleinman, Mark E. and others},
  title = {Sequence- and target-independent angiogenesis suppression by {siRNA} via {TLR3}},
  journal = {Nature},
  year = {2008},
  volume = {452},
  pages = {591--597},
  doi = {10.1038/nature06765},
  pmid = {18368052}
}

@article{Zhou2026TheRNA,
  author = {Zhou, Yang and others},
  title = {{theRNA}: a curated knowledgebase of functional {RNA} therapeutics spanning diverse modalities and disease applications},
  journal = {Nucleic Acids Research},
  year = {2026},
  volume = {54},
  pages = {D1672--D1682},
  doi = {10.1093/nar/gkaf1064},
  pmid = {41171135}
}

@article{Zhang2024SiRNAEfficacyDB,
  author = {Zhang, Y. and others},
  title = {{siRNAEfficacyDB}: An experimentally supported small interfering {RNA} efficacy database},
  journal = {IET Systems Biology},
  year = {2024},
  volume = {18},
  pages = {199--207},
  doi = {10.1049/syb2.12102},
  pmid = {39541343}
}

@article{He2026CMsiRNAdb,
  author = {He, S. and others},
  title = {{CMsiRNAdb}: a database of chemically modified {SiRNA} silencing efficiency for nucleic acid drug design},
  journal = {BMC Bioinformatics},
  year = {2026},
  volume = {27},
  pages = {33},
  doi = {10.1186/s12859-025-06359-y},
  pmid = {41484819}
}

@article{Dar2016SiRNAmod,
  author = {Dar, Showkat Ahmad and others},
  title = {{siRNAmod}: A database of experimentally validated chemically modified {siRNAs}},
  journal = {Scientific Reports},
  year = {2016},
  volume = {6},
  pages = {20031},
  doi = {10.1038/srep20031},
  pmid = {26818131}
}

@article{Wang2025CRISPRoffT,
  author = {Wang, G. and others},
  title = {{CRISPRoffT}: comprehensive database of {CRISPR/Cas} off-targets},
  journal = {Nucleic Acids Research},
  year = {2025},
  volume = {53},
  pages = {D914--D924},
  doi = {10.1093/nar/gkae1025},
  pmid = {39526384}
}

@article{Schultheiss2011WebResourceRules,
  author = {Schultheiss, Sebastian J.},
  title = {Ten simple rules for providing a scientific Web resource},
  journal = {PLoS Computational Biology},
  year = {2011},
  volume = {7},
  pages = {e1001126},
  doi = {10.1371/journal.pcbi.1001126},
  pmid = {21637800}
}

@article{Wilkinson2016FAIR,
  author = {Wilkinson, Mark D. and others},
  title = {The {FAIR} Guiding Principles for scientific data management and stewardship},
  journal = {Scientific Data},
  year = {2016},
  volume = {3},
  pages = {160018},
  doi = {10.1038/sdata.2016.18},
  pmid = {26978244}
}

@article{NARWebServerIssue2025,
  title = {The 23rd annual {Nucleic Acids Research} Web Server Issue 2025},
  journal = {Nucleic Acids Research},
  year = {2025},
  volume = {53},
  pages = {W1--W3},
  doi = {10.1093/nar/gkaf564},
  pmid = {40580006}
}

@article{RigdenFernandez2025DatabaseIssue,
  author = {Rigden, Daniel J. and Fernandez, Xos{\\'{e}} M.},
  title = {The 2025 {Nucleic Acids Research} database issue and the online molecular biology database collection},
  journal = {Nucleic Acids Research},
  year = {2025},
  volume = {53},
  pages = {D1--D9},
  doi = {10.1093/nar/gkae1220},
  pmid = {39658041}
}

@article{Sherman2022DAVID,
  author = {Sherman, Brad T. and others},
  title = {{DAVID}: a web server for functional enrichment analysis and functional annotation of gene lists (2021 update)},
  journal = {Nucleic Acids Research},
  year = {2022},
  volume = {50},
  pages = {W216--W221},
  doi = {10.1093/nar/gkac194},
  pmid = {35325185}
}

@article{Liao2019WebGestalt,
  author = {Liao, Yuxing and others},
  title = {{WebGestalt} 2019: gene set analysis toolkit with revamped {UIs} and {APIs}},
  journal = {Nucleic Acids Research},
  year = {2019},
  volume = {47},
  pages = {W199--W205},
  doi = {10.1093/nar/gkz401},
  pmid = {31114916}
}

@article{Zhou2019Metascape,
  author = {Zhou, Yingyao and others},
  title = {Metascape provides a biologist-oriented resource for the analysis of systems-level datasets},
  journal = {Nature Communications},
  year = {2019},
  volume = {10},
  pages = {1523},
  doi = {10.1038/s41467-019-09234-6},
  pmid = {30944313}
}

@article{Ruan2025Pairpot,
  author = {Ruan, Z. and others},
  title = {Pairpot: a database with real-time lasso-based analysis tailored for paired single-cell and spatial transcriptomics},
  journal = {Nucleic Acids Research},
  year = {2025},
  volume = {53},
  pages = {D1087--D1098},
  doi = {10.1093/nar/gkae986},
  pmid = {39494542}
}

@article{Robert2025FoldScript,
  author = {Robert, X. and others},
  title = {{FoldScript}: a web server for the efficient analysis of {AI}-generated 3D protein models},
  journal = {Nucleic Acids Research},
  year = {2025},
  volume = {53},
  pages = {W277--W282},
  doi = {10.1093/nar/gkaf326},
  pmid = {40276967}
}
"""


def replace_block(text: str, start_pat: str, end_pat: str, replacement: str) -> str:
    pattern = re.compile(f"{start_pat}.*?{end_pat}", re.S | re.M)
    if not pattern.search(text):
        raise RuntimeError(f"Block not found: {start_pat} ... {end_pat}")
    return pattern.sub(replacement + "\n\n" + end_pat.lstrip("^"), text, count=1)


def revise_manuscript(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    text = replace_block(text, r"## Abstract\s*", r"^## Introduction", ABSTRACT)
    text = replace_block(text, r"## Introduction\s*", r"^## Database scope", INTRODUCTION)
    text = replace_block(text, r"## Database content \(current release\)\s*", r"^### Audit reconciliation", DATABASE_CONTENT)
    text = replace_block(text, r"## Web portal and programmatic access\s*", r"^## Comparison with existing resources", WEB_PORTAL)
    text = replace_block(text, r"## Comparison with existing resources\s*", r"^## Discussion", COMPARISON)

    old_fig3 = re.compile(
        r"!\[\]\(C:/Users/Jie/Desktop/NAR_OligoSafetyDB/repo_ready/04_delivery/FIG2_content_summary_v2\.png\)\{width=95%\}\n\n"
        r"\*\*Figure 3\..*?All four panels are computed directly from the current 737-record release\.",
        re.S,
    )
    if not old_fig3.search(text):
        raise RuntimeError(f"Old Figure 3 block not found in {path.name}")
    text = old_fig3.sub(FIGURE_3_BLOCK.rstrip(), text, count=1)

    text = re.sub(
        r"sequence and chemistry fields are no longer 0% .*? structured `dose_value` is 2 / 626 = 0\.3%\)",
        "sequence, chemistry and dose fields remain sparse and are exposed as prioritized curation worklists; structured `dose_value` is 2/626 = 0.3%)",
        text,
        flags=re.S,
    )

    text = re.sub(r"## References\s*.*\Z", REFERENCES.rstrip(), text, count=1, flags=re.S | re.M)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    for manuscript in MANUSCRIPTS:
        revise_manuscript(manuscript)
    (FINAL / "references.bib").write_text(BIBTEX.rstrip() + "\n", encoding="utf-8")
    print("Revised manuscripts and references.bib")


if __name__ == "__main__":
    main()
