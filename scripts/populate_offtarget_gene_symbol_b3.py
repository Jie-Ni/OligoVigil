"""B3 — Populate offtarget_gene_symbol (+ optional offtarget_transcript_id) for the
94 Grade A/B off-target_evidence rows.

Policy (see paper-skill do_not.yaml HONESTY LOCK):
  - Regex + heuristic + curated stop-word filter only. No LLM call.
  - "transcriptome-wide" is the honest answer when the source describes a global
    RNA-seq / microarray scan without naming specific off-target genes.
  - "unspecified" when the source quote is empty/'NONE' or does not name any
    off-target gene.
  - The molecule's intended target gene is NEVER labelled as an off-target.

Inputs:
  data/oligosafety.db                                — destination
  data/generated/v2_offtarget_review_final.csv      — curator grounding quotes
Outputs:
  - DB UPDATEs on offtarget_evidence
  - data/oligosafety.db.pre_b3_offtarget_gene_<UTC>.bak  (backup)
  - data/generated/b3_offtarget_gene_diff.csv            (per-row before/after)
"""
from __future__ import annotations

import csv
import datetime as _dt
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "oligosafety.db"
CSV_PATH = ROOT / "data" / "generated" / "v2_offtarget_review_final.csv"
DIFF_CSV = ROOT / "data" / "generated" / "b3_offtarget_gene_diff.csv"

# --- stop-word lists --------------------------------------------------------

# Method/instrument/buffer/section/disease acronyms that look HUGO-style but
# are never gene symbols. Liberal — false negatives ("missed real gene") are
# preferable to false positives ("called PKC an off-target when paper said
# levels were unchanged") in a curated provenance database.
METHOD_NOISE = {
    # sequencing/profiling methods
    "RNA", "DNA", "RNASEQ", "RNASEQS", "RNAS", "MRNA", "PRE", "QPCR", "RT", "PCR",
    "QRT", "RTPCR", "WB", "WESTERN", "IHC", "ELISA", "FACS", "FISH", "ICC",
    "CHIP", "CHIPSEQ", "ATAC", "ATACSEQ", "INRI", "INRISEQ", "CRISPR",
    "GUIDE", "TALEN", "TAL", "TALENS",
    "CLIP", "CLIPSEQ", "SCRNA", "TCR", "BCR", "MS", "LCMS", "ESI",
    "QTOF", "MALDI", "TLC", "HPLC", "SDS", "PAGE", "BCA", "BSA",
    "TMSD",  # Toehold-Mediated Strand Displacement (method, eid=5)
    # buffers/reagents
    "PBS", "TBS", "EDTA", "DMEM", "FBS", "DMSO", "TRIS", "HEPES", "NACL", "KCL",
    "MGCL", "MG", "NA", "K", "BME", "DTT", "RNASE", "DNASE", "PROTEASE",
    # chemistry / oligo modifications & chemistries (NOT genes)
    "OMU", "OMG", "OMA", "OMC", "FU", "FA", "FG", "FC", "OME", "OMET", "OMETHYL",
    "LNA", "PMO", "PNA", "ASO", "ASOS", "ASOR", "ASOL", "AON", "AONS", "PS",
    "SIRNA", "SIRNAS", "MIRNA", "MIRNAS", "GAPMER", "GAPMERS", "AMO", "PS-ASO",
    "GALNAC", "GNA", "SNA", "UNA", "DSI", "DSIR", "RISC", "MOE", "FNA",
    "PSDNA", "PDB", "SBP", "EXR", "REP", "TFO", "INA",
    "GNA-C", "GNA-G", "GNA-A", "GNA-U", "GNA-T",  # explicit GNA isomers
    "SI-50", "SI-47",  # siRNA identifier codes
    # assays/units
    "IC", "IC50", "EC", "EC50", "LD", "LD50", "ED", "FC", "LFC", "MFI", "MOI",
    "UC", "CT", "AUC", "MIC", "MIQE", "CPM", "RPM", "RPKM", "FPKM", "FDR",
    "TPM", "FOLD", "FOLDS", "BP", "KB", "MB", "GB", "NM", "UM", "ML", "UL", "MG",
    "MUL", "NL", "MIN", "MINS", "SEC", "H", "HR", "HRS", "WK", "MO", "YR",
    # generic
    "ROC", "PR", "TP", "FP", "TN", "FN", "AUROC", "AUPRC",
    "ANOVA", "SD", "SE", "SEM", "CI", "OR", "RR", "PI", "DEG", "DEGS",
    "NHP", "NHPS", "WT", "KO", "KI", "HET", "HOM", "TG", "WTM", "KIM",
    "MM", "GAPS", "PHE", "PRO", "PERS",
    # paper structure tokens
    "FIG", "FIGS", "FIGURE", "FIGURES", "TABLE", "TABLES", "SUPPL", "SUPPLEMENT",
    "REFS", "REF", "EQN", "EQ", "SECT", "SUBSECT", "CHAPTER", "CHAPT", "APP",
    "METHODS", "METHOD", "RESULTS", "RESULT", "DISCUSSION", "INTRODUCTION",
    "ABSTRACT", "CONCLUSION", "CONCLUSIONS", "ACKNOWLEDGMENTS",
    # english words that show up uppercase
    "ATP", "ADP", "GTP", "GDP", "AMP", "CAMP", "CGMP",
    "OK", "UG", "NG", "KDA", "MDA", "MW", "PH",
    # disease / virus / cell line acronyms (NOT host genes)
    "HIV", "HBV", "HCV", "HBVR", "SARS", "MERS", "COVID", "HSV", "HPV", "EBV",
    "TMV", "BSL", "LCA", "LCA10", "ALS", "DMD", "SMA", "DM", "DMR", "DM1",
    "DM2", "FTD", "AD", "PD", "HD", "ALS",
    "CAR", "CART", "CRC", "AML", "ALL", "CML", "CLL", "PBMC", "PBMCS",
    "PBSEDTA", "PROT", "PROTS",
    # CD/cluster of differentiation markers that are surface markers, not commonly
    # discussed as "off-target genes" — context-suppressed unless paired with
    # an explicit "off-target on CD28" cue (rare). Keep CD28/CD3 out of off-target hits.
    "CD3", "CD4", "CD8", "CD14", "CD16", "CD19", "CD20", "CD25", "CD27",
    "CD28", "CD33", "CD34", "CD38", "CD40", "CD44", "CD56", "CD62L", "CD68",
    "CD127", "CD163",
    # publishing
    "OTE", "OTES", "OFFT", "OFFTS", "OT", "OTS",
    # study identifiers / common phrasings
    "ID", "IDS", "UTR", "UTRS", "ORF", "ORFS", "CDS", "GENOME",
    # reporter / model constructs (not genes)
    "AR28Q", "AR54Q", "ARE", "ARE-",
    # nuclear / signalling acronyms with broad usage as pathways not specific off-target genes
    "NFKB", "MAPK", "ERK", "JNK", "AKT", "PI3K", "MTOR", "MTORC", "STAT",
    "JAK", "TGF",
    # AAV/lentivirus capsids
    "AAV", "AAV2", "AAV5", "AAV6", "AAV8", "AAV9", "LV", "LVS",
    # numerical Pvalues / stat phrases
    "PVALUE", "PVAL", "TUKEY", "DUNNETT", "POSTHOC", "P53", "P21", "P53R",
}

# Curated allow-list of known human (and a few non-human) gene/protein symbols
# observed in the 94 A/B quotes during manual scan. This biases the extractor
# to be conservative — anything in this set is accepted as a real symbol.
KNOWN_GENES = {
    # therapeutic intended-targets that may appear AS off-targets too
    "TTR", "PCSK9", "ApoB", "APOB", "GAPDH", "HMGB1",
    # the explicit gene/protein hits scanned from the 94 quotes
    "AMPAR", "AGO1", "AGO2", "AGO4", "IFIT1", "OAS1", "ISG20",
    "GRAMD4", "GAS2", "POLA2", "LGALS2", "IGFBP1", "IGF1R", "MAPT",
    "NFATc1", "NFATC1", "PPP3CA", "APOLD1", "ANLN", "HHLA2", "GRHL2",
    "DPP10", "LPAL2", "PLG", "DBHS", "BACH1", "DUX4", "TMEM16A",
    "TMEM16a", "CEP290", "MALAT1", "MAPT", "BCLXL", "BCL-XL",
    "MCL1", "MCL-1", "TUBULIN", "PKC", "PKCD", "SURVIVIN", "ARL4C", "CIDEB",
    "CCND1", "TNRC6", "GW182",
    # NB: AR28Q/AR54Q removed — reporter constructs, not genes (see eid=456)
    # NB: DUX4-fl is an isoform name; covered by DUX4 in KNOWN_GENES if needed
    "AR", "AR-", "ATXN3", "HTT", "APP", "DMPK", "MAPT", "SOD1", "BTK",
    "CD46", "F12", "FXII", "FXIIA", "VIM", "FXII", "EGFP", "TNFR1",
    "IGF2BP2", "WRN", "KCNT1", "TMEM16A", "YAP1", "WWTR1", "ACTB",
    "PDIA3", "SMILR", "F7", "VIR", "WRN",
    # non-coding RNAs
    "MIR-17", "MIR17", "MIRNA17",
    # alternative isoforms (NOTE: do NOT add drug codes like ALN-HBV, ALN-HBV02,
    # ALN here — they pass the curated-list bypass and end up as fake off-targets)
}
# upper-case lookup
KNOWN_GENES_UPPER = {g.upper() for g in KNOWN_GENES}

# Off-target-context cues — if a candidate token appears within ~40 chars of any
# of these, we prefer it over the molecule's intended target.
OFFTARGET_CUES = [
    "off-target", "off target", "offtarget", "downregulat", "down-regulat",
    "down regulat", "decrease", "reduced", "knockdown", "knock-down",
    "silencing", "inhibit", "perturb", "altered", "increased expression",
    "elevated expression", "induced", "up-regulat", "upregulat",
    "not detected", "not significantly", "unchanged", "off-targets",
]

# Transcriptome-wide cues — if the quote mentions one of these AND no specific
# off-target gene symbol survives stop-word filtering, label as 'transcriptome-wide'
TRANSCRIPTOME_CUES = [
    "rna-seq", "rnaseq", "rna sequencing", "rna-sequencing",
    "transcriptome-wide", "transcriptome wide", "whole-transcriptome",
    "whole transcriptome", "global transcriptome", "transcriptome profiling",
    "microarray", "genome-wide rna", "rnaseqs", "rna-seq dataset",
    "transcriptome analysis", "transcriptome changes",
    "transcriptome-wide off-target", "transcriptome-wide changes",
]

# HUGO-like regex: 2-12 chars, starts with capital letter, may contain digits
# and at most one hyphen.
GENE_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,6}(?:-[A-Z0-9]{1,4})?)\b")

# Accession regex (NM_, NR_, XM_, ENST, ENSG, NP_)
ACCESSION_RE = re.compile(r"\b((?:NM|NR|XM|XR|NP)_\d+(?:\.\d+)?|ENS[TGP]\d+(?:\.\d+)?)\b")

# Drug / oligo / construct identifier patterns (NOT gene symbols).
# Used to reject tokens like ASO-4733, ALN-HBV02, RGLS4326, QR-110, PH-762,
# SLN360, BHF7, KT777, FM10, MC3, T39, S1A3, S10B, DV29P, si098-DV29P,
# bsYW-61, si-50, ASO-001933, ASO-2025, WRN-108, etc.
DRUG_CODE_PATTERNS = [
    # leading letters followed by 2+ digits, optional trailing letters
    re.compile(r"^[A-Z]{1,4}-?\d{2,}[A-Z]?$"),
    # leading letters then hyphen then alnum block of length 4-12 (drug codes
    # like ALN-HBV02, PH-762, QR-110, ASO-4733, GR18-3, WRN-108, ASO-2025,
    # ALN-HBV, GSK2910546A)
    re.compile(r"^[A-Z]{2,6}-?[A-Z0-9]{2,10}$"),
    # Figure / table panel labels: S10B, S10E, S1A3, Figure 6I etc.
    re.compile(r"^S\d{1,3}[A-Z]?\d*$"),
    # DV-style siRNA codes: DV29P, DV26P
    re.compile(r"^DV\d{1,3}[A-Z]$"),
    # vendor lot / oligo identifiers like ADO2, FM10, T39, BHF7, KT777, P9, S9
    re.compile(r"^[A-Z]{1,4}\d{1,3}$"),
    # AR28Q / AR54Q / P9S9 / P9S10 / P9S910 reporter constructs
    re.compile(r"^[A-Z]{1,3}\d+[A-Z]\d*$"),
    re.compile(r"^P\d+S\d+\d*$"),
    # Animal numbering: B4, C4, D4 (rejected by length)
]


def looks_like_drug_code(tok: str) -> bool:
    u = tok.upper().replace(" ", "")
    return any(p.match(u) for p in DRUG_CODE_PATTERNS)


# Suppress molecule's intended-target gene from being labelled as off-target.
# Two sources:
#   (a) molecule.target_gene_symbol (trusted; split on common delimiters)
#   (b) tokens in molecule.canonical_name THAT ARE ALSO IN KNOWN_GENES_UPPER —
#       this is intentionally narrow: we only suppress when the canonical name
#       names a curated gene symbol (e.g. "Di-siRNA-HTT panel" → HTT). We
#       intentionally do NOT mine arbitrary uppercase tokens (e.g. "TNRC6;
#       GW182; AGO2" must not suppress AGO2 — see eid=42).
#
# IMPORTANT: For (b), we further require that the symbol appears EITHER as a
# "siRNA-targeting-X" / "X-targeting" / "anti-X" / "X siRNA" / "X ASO" pattern
# in the canonical name, OR is the sole alpha word in the name. This blocks
# multi-gene panel names from being treated as a single intended target.
INTENDED_TARGET_RE = re.compile(
    r"\b(?:anti-|si-?|sh-?|miR-?|ASO[- ]|AON[- ]|PMO[- ]|PNA[- ]|MOE[- ]|gapmer[- ]?)?"
    r"([A-Z][A-Z0-9]{1,11})(?:-(?:targeting|directed|specific|si|sh))?\b",
    re.IGNORECASE,
)


_NAME_PREFIX_RE = re.compile(
    r"^(si|sh|anti-?|miR-?|ASO[- ]?|AON[- ]?|PMO[- ]?|PNA[- ]?|MOE[- ]?|gapmer[- ]?)",
    re.IGNORECASE,
)


def _strip_oligo_prefix(tok: str) -> str:
    """Strip leading "si"/"sh"/"anti-"/"ASO-" etc., yield possible bare gene name."""
    s = tok
    for _ in range(2):  # apply at most twice to handle "siIGF1R-1" → "IGF1R-1" → "IGF1R"
        m = _NAME_PREFIX_RE.match(s)
        if m:
            s = s[m.end():]
    # strip trailing -<digit>/<letter><digit> identifier
    s = re.sub(r"[-_][0-9]+[A-Z]?$", "", s)
    return s


def mine_intended_targets_from_name(name: str | None,
                                    explicit_target: str | None) -> set[str]:
    """Compute the suppression set of "intended-target" gene symbols.

    Sources (both narrow on purpose):
      (a) molecule.target_gene_symbol  — always trusted, split on ;/,, space
      (b) molecule.canonical_name      — ONLY if the name is a SINGLE molecule
          (no ';' or '/' delimiters); we strip oligo prefixes (si/sh/anti-/ASO-)
          and accept tokens that match KNOWN_GENES_UPPER

    The narrow rule (b) avoids dragging AGO2 out of "TNRC6; GW182; AGO2" while
    still suppressing IGF1R out of "siIGF1R-1".
    """
    out: set[str] = set()
    if explicit_target:
        for piece in re.split(r"[;/, ]+", explicit_target):
            piece = piece.strip().upper()
            if piece and piece not in METHOD_NOISE:
                out.add(piece)
                # Common F12 ↔ FXII alias (Factor XII)
                if piece == "F12":
                    out.add("FXII")
                if piece == "FXII":
                    out.add("F12")
                if piece == "F7":
                    out.add("FVII")
                if piece == "FVII":
                    out.add("F7")
    if name:
        # Split on ; / , and mine each piece independently. CRITICAL guard:
        # a piece only contributes when it has one of these intended-target
        # signals:
        #   (i)  begins with oligo prefix (si/sh/anti-/ASO-/AON-/PMO-/PNA-)
        #   (ii) contains "-targeting" / "-directed" / "-specific" suffix
        #   (iii) is the ONLY piece AND matches a KNOWN_GENES symbol exactly
        # This stops "TNRC6; GW182; AGO2" from suppressing AGO2 (none of those
        # have prefix/suffix), while still catching "ARL4C-targeting" and the
        # single-token name "TMEM16a".
        pieces = [p.strip() for p in re.split(r"[;/]", name) if p.strip()]
        # Pre-pass: handle the "single-piece bare-symbol" case.
        if len(pieces) == 1:
            sole = pieces[0]
            for tok in GENE_RE.findall(sole):
                u = tok.upper()
                if u in METHOD_NOISE:
                    continue
                if u in KNOWN_GENES_UPPER:
                    out.add(u)
        for piece in pieces:
            has_oligo_prefix = bool(_NAME_PREFIX_RE.match(piece))
            has_target_suffix = bool(
                re.search(r"[-_](?:targeting|directed|specific|aon|aso|pmo|pna)\b",
                          piece, re.IGNORECASE)
            )
            if not (has_oligo_prefix or has_target_suffix):
                continue
            # mine HUGO tokens inside the piece (e.g. "ASO-targeting-MAPT")
            for tok in GENE_RE.findall(piece):
                u = tok.upper()
                if u in METHOD_NOISE:
                    continue
                stripped = _strip_oligo_prefix(tok).upper()
                for cand in (u, stripped):
                    if cand and cand in KNOWN_GENES_UPPER and cand not in METHOD_NOISE:
                        out.add(cand)
            # also try whole-piece stripping (e.g. "siIGF1R-1" → "IGF1R")
            whole = _strip_oligo_prefix(piece).upper()
            for sub in re.findall(r"[A-Z][A-Z0-9]{2,11}", whole):
                if sub in KNOWN_GENES_UPPER and sub not in METHOD_NOISE:
                    out.add(sub)
            # Residue from explicit prefix strip ("siF12" → "F12")
            residue = _NAME_PREFIX_RE.sub("", piece, count=1)
            residue = re.sub(r"[-_].*$", "", residue).upper()
            if residue and residue in KNOWN_GENES_UPPER:
                out.add(residue)
            if residue == "F12":
                out.update({"F12", "FXII"})
            if residue == "FXII":
                out.update({"F12", "FXII"})
    return out


def now_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_csv_quotes() -> dict[int, dict]:
    rows: dict[int, dict] = {}
    with CSV_PATH.open("r", encoding="utf-8") as fp:
        for row in csv.DictReader(fp):
            if row.get("entity_table") != "offtarget_evidence":
                continue
            try:
                eid = int(row["entity_id"])
            except (KeyError, TypeError, ValueError):
                continue
            rows[eid] = row
    return rows


# On-target phrasing — when these surround a gene name, that gene is the
# intended on-target, not an off-target. Patterns must be anchored so they
# only fire when they end IMMEDIATELY BEFORE / start IMMEDIATELY AFTER the
# gene name (no characters between). All patterns are designed to be
# applied with the relevant context substring (40 chars) and require that
# the match abuts the gene boundary.
#
# Anchoring: BEFORE patterns end with $ when matched against ctx_left (so the
# phrase must be the LAST thing before the gene); AFTER patterns start with ^
# when matched against ctx_right (so the phrase must be the FIRST thing after).
#
# Critically: "off-target" must NEVER trigger on-target suppression. The
# leading-word check for "off-" / "non-" handles this explicitly.

ONTARGET_PHRASES_BEFORE = [
    # phrase must be immediately before the gene (end of left-context)
    r"\btargeting\s+$",              # "ASO targeting MAPT"
    r"\btargets\s+$",                # "ASO targets MAPT"
    r"\bdirected\s+against\s+$",
    r"\bdirected\s+(?:at|to|toward(?:s)?)\s+$",
    r"\bspecific\s+(?:to|for)\s+$",
    r"\bcomplementar(?:y|ity)\s+to\s+$",
    r"\b(?:anti-?|si-?|sh-?|miR-?)$",     # "anti-MAPT", "siMAPT"
    r"\bsilencing\s+of\s+$",
    r"\bknockdown\s+of\s+$",
    r"\binhibitor\s+of\s+$",
    r"\bsuppress(?:ed|ing)?\s+(?:the\s+)?(?:on-target\s+)?$",  # "suppressed both the AR54Q"
    r"\bagainst\s+(?:the\s+(?:on-?target\s+)?)?$",  # "against the on-target miR-17"
    r"\bunclouded\s+by\s+$",         # "unclouded by DUX4 target genes"
    r"\b(?:efficacy|activity|potency)\s+(?:against|toward|on)\s+$",
    r"\b(?:on-?target|intended\s+target)\s+(?:of|gene\s+is|is)?\s*$",
    r"\b(?:effect\s+on|effects\s+on)\s+$",
]
ONTARGET_PHRASES_AFTER = [
    # phrase must be immediately after the gene (start of right-context)
    r"^\s*(?:-|\s)*target\s+gene(?:s)?\b",      # "DUX4 target genes"
    r"^\s*(?:silencing|knockdown|treatment)\b", # "HTT silencing", "HTT treatment"
    r"^\s*(?:-targeting|-directed|-specific)\b",
    r"^\s*siRNA\b",                              # "MAPT siRNA"
    r"^\s*ASO\b",
    r"^\s*AON\b",
    r"^\s*PMO\b",
    r"^\s*PNA\b",
    r"^\s*gapmer\b",
    r"^\s*on-?target\b",
    r"^\s+(?:is\s+the\s+)?(?:only\s+)?differentially\s+regulated\s+gene\b",
    r"^\s*\d+[-–]\d+\s+(?:mRNA|exon|transcript)\b",   # "CEP290 26-27 mRNA" / "X 26-27 exon"
    r"^\s+(?:is|are)\s+the\s+only\s+differential",          # "MAPT is the only…"
]


def _is_offtarget_context(ctx_left: str) -> bool:
    """Check if the gene is in an explicitly OFF-target context: 'off-target X'.

    This MUST short-circuit on-target detection — "off-target AMPAR" names
    AMPAR as the off-target, not the on-target.
    """
    # final words of ctx_left (the bit right before the gene)
    tail = ctx_left.rstrip()
    return (
        bool(re.search(r"\boff-?targets?\s*$", tail))
        or bool(re.search(r"\bnon-?targets?\s*$", tail))
        or bool(re.search(r"\bunintended\s*$", tail))
        or bool(re.search(r"\bpotential\s+off-?targets?\s*$", tail))
    )


def collect_ontarget_genes_in_quote(quote: str) -> set[str]:
    """Detect gene names in 'on-target' grammatical contexts within the quote
    and return their uppercase forms for downstream suppression."""
    out: set[str] = set()
    if not quote:
        return out
    q = quote
    q_lower = q.lower()
    for sym in KNOWN_GENES_UPPER:
        if len(sym) < 3:
            continue
        pattern = re.compile(r"\b" + re.escape(sym) + r"\b", re.IGNORECASE)
        for m in pattern.finditer(q):
            idx = m.start()
            end = m.end()
            ctx_left = q_lower[max(0, idx - 60):idx]
            ctx_right = q_lower[end:min(len(q), end + 60)]
            # Hard veto: if explicitly framed as off-target, never suppress.
            if _is_offtarget_context(ctx_left):
                continue
            if any(re.search(p, ctx_left, re.IGNORECASE) for p in ONTARGET_PHRASES_BEFORE):
                out.add(sym)
                break
            if any(re.search(p, ctx_right, re.IGNORECASE) for p in ONTARGET_PHRASES_AFTER):
                out.add(sym)
                break
    return out


def extract_gene_symbols(quote: str,
                          intended_targets_upper: set[str]) -> list[str]:
    """Return ordered, de-duped list of likely off-target gene symbols.

    Filter order (each candidate must pass ALL):
      1. NOT in METHOD_NOISE
      2. NOT the molecule's intended target (set passed in)
      3. NOT detected as on-target context within the quote
      4. IF in KNOWN_GENES allow-list → ACCEPT (overrides drug-code/length)
      5. ELSE: NOT a drug/oligo/figure-panel code (looks_like_drug_code)
              AND length>=4 AND NOT in ENGLISH_NOISE
    """
    if not quote:
        return []
    ontarget_in_quote = collect_ontarget_genes_in_quote(quote)
    suppress = intended_targets_upper | ontarget_in_quote

    candidates: list[str] = []
    seen: set[str] = set()
    # First, case-insensitive pass for KNOWN_GENES (catches mixed-case like
    # "NFATc1" which the all-caps GENE_RE misses).
    for sym in KNOWN_GENES_UPPER:
        if len(sym) < 3:
            continue
        if sym in suppress:
            continue
        if re.search(r"\b" + re.escape(sym) + r"\b", quote, re.IGNORECASE):
            if sym not in seen:
                candidates.append(sym)
                seen.add(sym)
    # Second, all-caps pass for unknown HUGO-like tokens
    for m in GENE_RE.finditer(quote):
        tok = m.group(1)
        u = tok.upper()
        if u in METHOD_NOISE:
            continue
        if u in suppress:
            continue
        if u in KNOWN_GENES_UPPER:
            # already added by case-insensitive pass
            continue
        if looks_like_drug_code(tok):
            continue
        if len(u) >= 4 and u not in ENGLISH_NOISE:
            if u not in seen:
                candidates.append(tok)
                seen.add(u)
    return candidates


# Common all-caps English words / scientific jargon that show up uppercase
# in figure captions and methods. Rejected if not in KNOWN_GENES.
ENGLISH_NOISE = {
    "RESULTS", "METHODS", "DISCUSSION", "INTRODUCTION", "ABSTRACT",
    "CONCLUSION", "CONCLUSIONS", "BACKGROUND",
    "OBSERVED", "REPORTED", "DEMONSTRATED", "REVEALED", "CONFIRMED",
    "DEMONSTRATE", "SHOW", "SHOWED", "FOUND", "SUGGEST", "SUGGESTS",
    "PERFORMED", "PERFORM", "OBSERVED", "TREATED", "EVALUATED",
    "INDICATED", "INDICATE", "INDICATES", "ANALYZED", "ANALYSED",
    "MEASURED", "QUANTIFIED", "DETECTED", "DETERMINED", "ASSESSED",
    "TESTED", "EXAMINED", "INVESTIGATED", "INVESTIGATE",
    "STUDY", "STUDIES", "PAPER", "REPORT", "ARTICLE",
    "GENE", "GENES", "TRANSCRIPT", "TRANSCRIPTS", "MRNA", "RNAS",
    "PROTEIN", "PROTEINS", "PEPTIDE", "PEPTIDES",
    "CELL", "CELLS", "TISSUE", "TISSUES", "TUMOR", "TUMORS",
    "EXPRESSION", "REGULATION", "PATHWAY", "PATHWAYS", "SIGNALING",
    "FIGURE", "TABLE", "PANEL", "PANELS", "DATA",
}


def is_transcriptome_wide(quote: str) -> bool:
    q = quote.lower()
    return any(cue in q for cue in TRANSCRIPTOME_CUES)


def extract_accessions(quote: str) -> list[str]:
    if not quote:
        return []
    return list(dict.fromkeys(m.group(1) for m in ACCESSION_RE.finditer(quote)))


def decide(quote: str,
            intended_targets_upper: set[str]) -> tuple[str, str | None, str]:
    """Return (offtarget_gene_symbol, offtarget_transcript_id_or_None, decision_rule).

    Rules (in order):
      R1 quote empty/NONE                                  -> ('unspecified', None, 'no_quote')
      R2 explicit gene candidate(s)                        -> (joined symbols, ?, 'explicit')
      R3 transcriptome-wide cue + 0 specific symbols       -> ('transcriptome-wide', ?, 'tx_wide')
      R4 otherwise                                         -> ('unspecified', ?, 'no_match')

    offtarget_transcript_id is filled separately if NM_/ENST accession present.
    """
    q = (quote or "").strip()
    if not q or q.upper() == "NONE":
        return "unspecified", None, "no_quote"

    symbols = extract_gene_symbols(q, intended_targets_upper)
    accessions = extract_accessions(q)
    transcript_id = ";".join(accessions) if accessions else None

    if symbols:
        # Order: prefer symbols that appear within 60 chars of an off-target cue
        ordered = order_by_offtarget_proximity(q, symbols)
        # Cap at 5 symbols to keep cell readable
        return ";".join(ordered[:5]), transcript_id, "explicit"

    if is_transcriptome_wide(q):
        return "transcriptome-wide", transcript_id, "tx_wide"

    return "unspecified", transcript_id, "no_match"


def order_by_offtarget_proximity(quote: str, symbols: list[str]) -> list[str]:
    q_lower = quote.lower()
    cue_positions: list[int] = []
    for cue in OFFTARGET_CUES:
        start = 0
        while True:
            idx = q_lower.find(cue, start)
            if idx == -1:
                break
            cue_positions.append(idx)
            start = idx + len(cue)
    if not cue_positions:
        return symbols

    def min_dist(sym: str) -> int:
        idx = quote.find(sym)
        if idx == -1:
            return 10**9
        return min(abs(idx - cp) for cp in cue_positions)

    return sorted(symbols, key=min_dist)


def main() -> int:
    if not DB_PATH.exists():
        print(f"FATAL: {DB_PATH} missing", file=sys.stderr)
        return 2
    if not CSV_PATH.exists():
        print(f"FATAL: {CSV_PATH} missing", file=sys.stderr)
        return 2

    backup = DB_PATH.with_suffix(f".db.pre_b3_offtarget_gene_{now_utc()}.bak")
    shutil.copy2(DB_PATH, backup)
    print(f"backup: {backup}")

    csv_rows = load_csv_quotes()

    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        ab = cur.execute(
            """SELECT oe.id, oe.molecule_id, oe.offtarget_gene_symbol,
                      oe.offtarget_transcript_id, oe.source_document_id,
                      oe.source_location, oe.evidence_grade,
                      m.canonical_name, m.target_gene_symbol
               FROM offtarget_evidence oe
               LEFT JOIN molecule m ON m.id = oe.molecule_id
               WHERE oe.evidence_grade IN ('A','B')
               ORDER BY oe.id"""
        ).fetchall()

        diffs: list[dict] = []
        gene_updates = 0
        tx_updates = 0
        rule_counts = {"explicit": 0, "tx_wide": 0, "no_quote": 0, "no_match": 0}
        distinct_genes: set[str] = set()
        tx_wide_count = 0
        unspecified_count = 0

        for (eid, mid, old_gene, old_tx, sdoc, sloc, grade,
             mol_name, intended_target) in ab:
            csv_row = csv_rows.get(eid)
            quote = (csv_row or {}).get("v2_grounding_quote", "") or ""
            # The intended-target suppression set combines:
            #  (a) molecule.target_gene_symbol (when populated)
            #  (b) any uppercase token in molecule.canonical_name that survives
            #      noise + drug-code filters (these are very likely intended
            #      targets, e.g. "ARL4C; ARL4C-targeting; CP8" -> {ARL4C, CP8})
            intended_targets_upper = mine_intended_targets_from_name(
                mol_name, intended_target
            )
            new_gene, new_tx, rule = decide(quote, intended_targets_upper)
            rule_counts[rule] += 1

            if new_gene == "transcriptome-wide":
                tx_wide_count += 1
            elif new_gene == "unspecified":
                unspecified_count += 1
            else:
                for sym in new_gene.split(";"):
                    distinct_genes.add(sym.strip())

            # only UPDATE if a real change is made
            do_update = False
            if (old_gene or "") != new_gene:
                cur.execute(
                    "UPDATE offtarget_evidence SET offtarget_gene_symbol = ? WHERE id = ?",
                    (new_gene, eid),
                )
                gene_updates += cur.rowcount
                do_update = True
            if new_tx and (old_tx or "") != new_tx:
                cur.execute(
                    "UPDATE offtarget_evidence SET offtarget_transcript_id = ? WHERE id = ?",
                    (new_tx, eid),
                )
                tx_updates += cur.rowcount
                do_update = True

            diffs.append({
                "id": eid,
                "molecule_id": mid,
                "molecule_canonical_name": mol_name or "",
                "intended_target_gene": intended_target or "",
                "evidence_grade": grade,
                "source_document_id": sdoc,
                "source_location": sloc or "",
                "old_offtarget_gene_symbol": old_gene or "",
                "new_offtarget_gene_symbol": new_gene,
                "old_offtarget_transcript_id": old_tx or "",
                "new_offtarget_transcript_id": new_tx or "",
                "decision_rule": rule,
                "grounding_quote": quote,
            })
            print(f"  eid={eid:>4} grade={grade} rule={rule:<8} "
                  f"old={old_gene!r} -> new={new_gene!r}"
                  + (f"  | tx_id: {old_tx!r} -> {new_tx!r}" if new_tx else ""))

        con.commit()

        # integrity check
        rc = cur.execute("PRAGMA integrity_check").fetchall()
        print(f"\nintegrity_check: {rc}")

        # write diff CSV
        DIFF_CSV.parent.mkdir(parents=True, exist_ok=True)
        with DIFF_CSV.open("w", encoding="utf-8", newline="") as fp:
            w = csv.DictWriter(fp, fieldnames=list(diffs[0].keys()))
            w.writeheader()
            w.writerows(diffs)
        print(f"diff csv: {DIFF_CSV}")

        # post-update metrics
        n_total = cur.execute("SELECT COUNT(*) FROM offtarget_evidence").fetchone()[0]
        n_ab = cur.execute(
            "SELECT COUNT(*) FROM offtarget_evidence WHERE evidence_grade IN ('A','B')"
        ).fetchone()[0]
        n_gene_total = cur.execute(
            "SELECT COUNT(*) FROM offtarget_evidence "
            "WHERE offtarget_gene_symbol IS NOT NULL AND offtarget_gene_symbol != ''"
        ).fetchone()[0]
        n_gene_ab = cur.execute(
            "SELECT COUNT(*) FROM offtarget_evidence "
            "WHERE evidence_grade IN ('A','B') AND offtarget_gene_symbol IS NOT NULL "
            "  AND offtarget_gene_symbol != ''"
        ).fetchone()[0]
        n_tw_db = cur.execute(
            "SELECT COUNT(*) FROM offtarget_evidence "
            "WHERE offtarget_gene_symbol = 'transcriptome-wide'"
        ).fetchone()[0]
        n_unsp_db = cur.execute(
            "SELECT COUNT(*) FROM offtarget_evidence "
            "WHERE offtarget_gene_symbol = 'unspecified'"
        ).fetchone()[0]
        n_tx_db = cur.execute(
            "SELECT COUNT(*) FROM offtarget_evidence "
            "WHERE offtarget_transcript_id IS NOT NULL AND offtarget_transcript_id != ''"
        ).fetchone()[0]
        distinct_genes_db = cur.execute(
            """SELECT COUNT(DISTINCT s)
               FROM (
                 SELECT TRIM(value) AS s
                 FROM offtarget_evidence,
                      json_each('["' || REPLACE(offtarget_gene_symbol, ';', '","') || '"]')
                 WHERE offtarget_gene_symbol IS NOT NULL
                   AND offtarget_gene_symbol NOT IN ('unspecified', 'transcriptome-wide', '')
               )"""
        ).fetchone()[0]

        print("\n=== POST-WRITE METRICS ===")
        print(f"backup_path: {backup}")
        print(f"rowcount_gene_updates : {gene_updates}")
        print(f"rowcount_tx_updates   : {tx_updates}")
        print(f"rule_counts           : {json.dumps(rule_counts)}")
        print()
        print(f"offtarget_evidence rows total                       : {n_total}")
        print(f"offtarget_evidence rows A/B                         : {n_ab}")
        print(f"offtarget_gene_symbol populated (total)             : {n_gene_total}/{n_total}")
        print(f"offtarget_gene_symbol populated (A/B subset)        : {n_gene_ab}/{n_ab}")
        print(f"transcriptome-wide labelled (total)                 : {n_tw_db}")
        print(f"unspecified (total)                                 : {n_unsp_db}")
        print(f"offtarget_transcript_id populated (total)           : {n_tx_db}")
        print(f"distinct specific gene symbols (non-placeholder)    : {distinct_genes_db}")

    finally:
        con.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
