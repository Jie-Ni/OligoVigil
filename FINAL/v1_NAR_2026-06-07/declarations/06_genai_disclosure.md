---
title: "Generative AI Use Disclosure"
subtitle: "OligoVigil submission to Nucleic Acids Research, Database Issue"
date: "2026-06-11"
---

# Generative AI Use Disclosure

## Use in the database curation workflow

A large language model was used as a proposal-only pre-screen during source-grounded re-curation. The model never wrote a curator decision, curator identity, or validation status. Each release row was individually adjudicated against its cited source passage by the human curator of record before acceptance.

The model was constrained by an exclusion-first rubric requiring: (i) an in-scope therapeutic oligonucleotide or delivery context; (ii) a primary observed result; (iii) agreement between the requested evidence domain and the reported evidence type; and (iv) a verbatim grounding quote from the supplied passage. Grounding quotes were checked programmatically before human review, and ungrounded proposals were forced to reject.

The curation audit records the model-proposal labels and the final human decisions per candidate in `04_delivery/v2_human_override_decisions.csv` (n = 2,003). Cross-tabulating the model proposal against the human decision reproduces the reported override statistics: 20 model accepts rejected by the human curator, 7 model rejects accepted by the human curator, 33 model abstains recovered as human accepts, and 92 grade adjustments.

## Use in manuscript preparation

Language-editing tools were used to support grammar, concision and stylistic revision of the manuscript. They were not used to generate evidence records, substitute for curator decisions, invent references, alter numerical results, or create scientific claims. All numerical claims were checked against the release database and audit files before submission. All authors reviewed the final manuscript and are responsible for its content.

## Non-use

No synthetic data, generated evidence records, generated citations, generated images, fine-tuned model, embedding-based retrieval system, or de novo risk-prediction model was used to produce the release database, benchmark, figures or scientific results.