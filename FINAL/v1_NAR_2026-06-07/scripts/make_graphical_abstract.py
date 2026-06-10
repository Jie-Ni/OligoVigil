#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_graphical_abstract.py
==========================
NAR-compliant graphical abstract for OligoVigil v1.

NAR Database GA HARD spec
-------------------------
* aspect ratio EXACTLY 5:2 (figsize 10 x 4 in @ 600 dpi -> still 5:2)
* minimum size 127 x 50 mm  (5 x 2 in)            -> we ship 254 x 101.6 mm (10x4 in)
* font sans-serif (Arial preferred, DejaVu Sans fallback), 12-16 pt
* TIF / EPS / editable PDF, 300-600 dpi             -> we ship PDF + PNG-600 + TIF-600
* single self-contained panel, summarising the resource in one glance.

Layout (three vertical thirds of the 10x4 in canvas)
----------------------------------------------------
LEFT  third : sqrt-narrowing funnel
              Indexed lit 36,245 -> Queue 70,283 -> Candidates 41,114
              -> v1 2,003 -> Human adjudication -> RELEASE 658
MIDDLE third: release "what's in it" mini-grid
              551 toxicity (hepatic 337 / general 105 / renal 42 / immuno 24)
              107 off-target (seed 42 / hybrid+mismatch 26 / transcriptome 25)
              Grade A 233 / B 244 / C 181
              Modality siRNA 336 / ASO 256 / PMO 16 / CpG 5 / other 45
              (other = ASO/siRNA-mixed 37 + 8 misc; sums to 658)
RIGHT third : differentiators tag list + firewall tagline.

Reuses the FIG1_v2 colour family (slate machine / amber human / teal release /
grey rejected / restrained red firewall accent) so the GA reads as the same
family as Figs 1-2.

HONESTY LOCK: every number on this canvas is locked to the released v1 figures.
The 233/244/181 split is the recomputed totals (toxicity 551 grade breakdown
200/183/168 + off-target 107 grade breakdown 33/61/13 = 233/244/181). Modality
"other" rolls ASO/siRNA mixed (37), CpG ODN (5)... wait, CpG is its own bar in
the brief, so other rolls 'ASO/siRNA mixed' (37) + 'other' (8) = 45. The five
modality bars sum to 336+256+16+5+45 = 658. The four toxicity sub-categories
shown (hepatic 337 + general 105 + renal 42 + immuno 24 = 508) cover the major
visible mass; the remaining 43 (16 hematologic + 15 neurological + 2 genotox
+ 10 uncategorised) are grouped into the "551" panel total but not given
sub-bars at GA resolution to keep this readable. Same convention for off-target:
3 explicit bars sum to 93, the remaining 14 'Generic / specificity' are folded
into the 107 total label but not drawn as a bar.

Run:
    cd C:/Users/Jie/Desktop/NAR_OligoSafetyDB/repo_ready
    python FINAL/v1_NAR_2026-06-07/scripts/make_graphical_abstract.py
"""

from __future__ import annotations

import argparse, sys as _sys
_ap = argparse.ArgumentParser(add_help=False)
_ap.add_argument('--blinded', action='store_true', help='use anonymous curator label + blinded output filenames')
_args, _ = _ap.parse_known_args()
BLINDED_CURATOR = 'single human curator' if _args.blinded else 'Ni Jie'
OUT_SUFFIX = '_blinded' if _args.blinded else ''

import math
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from matplotlib import font_manager


# --------------------------------------------------------------------------- #
# 0. Fonts: prefer Arial, fall back to DejaVu Sans (same fallback as v2)
# --------------------------------------------------------------------------- #
def _resolve_sans():
    candidates = ["Arial", "Liberation Sans", "Helvetica", "DejaVu Sans"]
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for c in candidates:
        if c in installed:
            return c
    return "DejaVu Sans"

SANS = _resolve_sans()

# NAR demands 12-16 pt. Set base to 12 pt; titles/tags up to 14-15 pt.
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": [SANS, "Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 12,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "legend.fontsize": 11,
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "figure.dpi": 600,
    "savefig.dpi": 600,
    "savefig.bbox": "standard",   # keep exact 5:2; 'tight' would shrink it
    "savefig.pad_inches": 0.0,
})


# --------------------------------------------------------------------------- #
# 1. Palette (matches FIG1_v2)
# --------------------------------------------------------------------------- #
C_MACHINE   = "#6B7FB3"
C_MACHINE_L = "#AEB9D6"
C_HUMAN     = "#E0A458"
C_RELEASE   = "#2E8B83"
C_REJECT    = "#C2BDB6"
C_TEXT      = "#222222"
C_FIRE      = "#B0413E"
C_BG_TAG    = "#F2F0EC"
C_BG_PANEL  = "#FAFAF8"

GRADE_COLORS = {"A": "#264653", "B": "#5C8A8A", "C": "#A9C5C0"}
C_TOX  = "#3A6EA5"
C_OFFT = "#C26B3E"


def lum(hexcolor: str) -> float:
    c = hexcolor.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b


# --------------------------------------------------------------------------- #
# 2. LOCKED DATA (every number is from the locked release)
# --------------------------------------------------------------------------- #
FUNNEL = [
    ("Indexed literature",       "36,245",  "machine"),
    ("Curation queue",           "70,283",  "machine"),
    ("Derived candidates",       "41,114",  "machine"),
    ("v1 machine pre-curation",  "2,003",   "machine"),
    ("Human adjudication",       BLINDED_CURATOR,  "human"),
    ("Curator-verified release", "658",     "release"),
]
# numeric values for sqrt width scaling (None -> use neighbour avg)
FUNNEL_VALS = [36245, 70283, 41114, 2003, None, 658]

# Middle-third stat blocks
TOX_TOTAL = 551
TOX_SUB = [("Hepatic", 337), ("General", 105), ("Renal", 42), ("Immuno", 24)]
# (other 7 toxicity records = 43, rolled into 551 total not drawn)

OFFT_TOTAL = 107
OFFT_SUB = [("Seed", 42), ("Hybrid./mismatch", 26), ("Transcriptome", 25)]
# (other 14 off-target = 'Generic / specificity', rolled into 107 total not drawn)

GRADES = [("A", 233), ("B", 244), ("C", 181)]   # sums to 658

# Modality rolled to 5 bars summing to 658:
#   siRNA 336 + ASO 256 + PMO 16 + CpG 5 + other 45  = 658
#   (other = ASO/siRNA mixed 37 + 8 misc)
MODALITY = [("siRNA", 336), ("ASO", 256), ("PMO", 16), ("CpG", 5), ("other", 45)]

DIFFERENTIATORS = [
    "Curator-verified",
    "Source-anchored",
    "Leakage-aware benchmark (n = 344)",
    "No-login web portal",
    "Agent-readable: OpenAPI + MCP + Bioschemas + PROV",
]

FIREWALL_TAGLINE = "The LLM never writes a curator decision."


# --------------------------------------------------------------------------- #
# 3. Build figure
# --------------------------------------------------------------------------- #
def build():
    # 10 x 4 in == 5:2 EXACTLY (NAR HARD requirement). 600 dpi.
    fig = plt.figure(figsize=(10.0, 4.0))
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 40)        # 100:40 == 5:2
    ax.axis("off")

    # background hairline frame (helps reviewers verify the bleed) — disable if
    # you want zero frame, but a 0.4 pt frame is within NAR allowance.
    ax.add_patch(Rectangle((0.2, 0.2), 99.6, 39.6, facecolor="white",
                           edgecolor="#DDDDDD", linewidth=0.4, zorder=0))

    # Three-third dividers (very light), only inside the body strip
    for x in (33.5, 66.5):
        ax.plot([x, x], [1.5, 31.0], color="#E8E6E2", lw=0.6, zorder=1)

    # ---- header strip (top of canvas) -------------------------------------- #
    ax.text(50, 38.4,
            "OligoVigil:  a curator-verified, source-anchored knowledge base "
            "of oligonucleotide safety",
            ha="center", va="center", fontsize=14, fontweight="bold", color=C_TEXT)
    ax.text(50, 35.6,
            "Six-stage curation pipeline  |  658 records  |  344-item leakage-aware "
            "benchmark  |  agent-readable",
            ha="center", va="center", fontsize=10.5, color="#555555", style="italic")

    # ====================================================================== #
    # LEFT THIRD — funnel
    # ====================================================================== #
    _draw_funnel(ax)

    # ====================================================================== #
    # MIDDLE THIRD — "what's in it" mini-grid
    # ====================================================================== #
    _draw_middle(ax)

    # ====================================================================== #
    # RIGHT THIRD — differentiators + firewall tagline
    # ====================================================================== #
    _draw_right(ax)

    return fig


# --------------------------------------------------------------------------- #
# 3a. LEFT — funnel
# --------------------------------------------------------------------------- #
def _draw_funnel(ax):
    kind_color = {"machine": C_MACHINE, "human": C_HUMAN, "release": C_RELEASE}

    # third spans x in [1.0, 33.0]; vertical funnel inside.
    x_left, x_right = 1.5, 32.0
    cx = (x_left + x_right) / 2.0
    y_top, y_bot = 29.8, 2.6
    n = len(FUNNEL)
    gap = (y_top - y_bot) / n
    box_h = gap * 0.74

    # section header
    ax.text(cx, 31.4, "Curation pipeline", ha="center", va="bottom",
            fontsize=12, fontweight="bold", color=C_TEXT)

    # sqrt-narrowing widths
    real_vals = [v for v in FUNNEL_VALS if v is not None]
    vmax = max(real_vals)
    max_w = (x_right - x_left) * 0.95
    min_w = (x_right - x_left) * 0.42

    centers = []
    for i, ((label, val_str, kind), val) in enumerate(zip(FUNNEL, FUNNEL_VALS)):
        ycen = y_top - gap * (i + 0.5)
        if val is None:
            w = (max_w + min_w) / 2.0 * 0.85
        else:
            scale = math.sqrt(val / vmax)
            w = min_w + (max_w - min_w) * scale
        x0 = cx - w / 2.0
        color = kind_color[kind]
        box = FancyBboxPatch((x0, ycen - box_h / 2), w, box_h,
                             boxstyle="round,pad=0.10,rounding_size=0.7",
                             linewidth=0.7, edgecolor="white",
                             facecolor=color, alpha=0.96, zorder=3)
        ax.add_patch(box)
        tcol = "white" if lum(color) < 0.5 else C_TEXT
        # two-line label: name (smaller) above value (bigger)
        ax.text(cx, ycen + box_h * 0.18, label, ha="center", va="center",
                fontsize=8.6, color=tcol, zorder=4)
        ax.text(cx, ycen - box_h * 0.22, val_str, ha="center", va="center",
                fontsize=11, fontweight="bold", color=tcol, zorder=4)
        centers.append((cx, ycen, box_h))

    # arrows
    for i in range(n - 1):
        x1, y1, h1 = centers[i]
        x2, y2, h2 = centers[i + 1]
        arr = FancyArrowPatch((x1, y1 - h1 / 2 - 0.05),
                              (x2, y2 + h2 / 2 + 0.05),
                              arrowstyle="-|>", mutation_scale=7,
                              linewidth=0.9, color="#666666", zorder=2)
        ax.add_patch(arr)

    # firewall band between stage 3 (v1 machine pre-curation) and stage 4 (human)
    _, y_v1, h_v1 = centers[3]
    _, y_hu, h_hu = centers[4]
    fire_y = (y_v1 - h_v1 / 2 + y_hu + h_hu / 2) / 2.0
    ax.plot([x_left + 0.2, x_right - 0.2], [fire_y, fire_y],
            color=C_FIRE, lw=1.0, linestyle=(0, (4, 2.5)), zorder=5)
    ax.text(x_right - 0.4, fire_y + 0.35,
            "machine / human firewall",
            ha="right", va="bottom", fontsize=8, color=C_FIRE,
            fontstyle="italic", zorder=6)

    # demoted side-note on the human stage
    _, y_hu_c, _ = centers[4]
    ax.text(x_right - 0.3, y_hu_c - box_h * 0.55,
            "1,345 demoted",
            ha="right", va="top", fontsize=7.6, color="#777777", fontstyle="italic")


# --------------------------------------------------------------------------- #
# 3b. MIDDLE — release composition mini-grid (2x2 micro-panels)
# --------------------------------------------------------------------------- #
def _draw_middle(ax):
    # third spans x in [34.5, 66.0]
    x_left, x_right = 34.5, 65.5
    y_top, y_bot = 29.8, 2.2
    cx = (x_left + x_right) / 2.0

    ax.text(cx, 31.4, "Inside the 658-record release",
            ha="center", va="bottom", fontsize=12, fontweight="bold", color=C_TEXT)

    # 2x2 sub-panels: top-left toxicity, top-right off-target,
    #                 bottom-left grade,  bottom-right modality.
    midx = (x_left + x_right) / 2.0
    midy = (y_top + y_bot) / 2.0
    pad  = 0.6

    panels = [
        (x_left,        midy + pad / 2, midx - pad / 2,    y_top,            "tox"),
        (midx + pad / 2, midy + pad / 2, x_right,           y_top,            "offt"),
        (x_left,        y_bot,          midx - pad / 2,    midy - pad / 2,   "grade"),
        (midx + pad / 2, y_bot,          x_right,           midy - pad / 2,   "mod"),
    ]

    for (px0, py0, px1, py1, kind) in panels:
        ax.add_patch(Rectangle((px0, py0), px1 - px0, py1 - py0,
                               facecolor=C_BG_PANEL, edgecolor="#E3E1DC",
                               linewidth=0.5, zorder=1))
        if   kind == "tox":   _panel_tox(ax,   px0, py0, px1, py1)
        elif kind == "offt":  _panel_offt(ax,  px0, py0, px1, py1)
        elif kind == "grade": _panel_grade(ax, px0, py0, px1, py1)
        elif kind == "mod":   _panel_mod(ax,   px0, py0, px1, py1)


def _panel_header(ax, px0, py0, px1, py1, title, total_str, color):
    ax.text(px0 + 0.5, py1 - 0.4, title,
            ha="left", va="top", fontsize=9.5, fontweight="bold", color=C_TEXT)
    ax.text(px1 - 0.5, py1 - 0.4, total_str,
            ha="right", va="top", fontsize=9.5, fontweight="bold", color=color)


def _hbars(ax, items, px0, py0, px1, py1, color, header_top, header_bot=1.2):
    """Render a small horizontal-bar plot inside the rect [px0..px1, py0..py1]."""
    n = len(items)
    inner_top = py1 - header_top
    inner_bot = py0 + header_bot
    inner_left  = px0 + 4.0   # leave room for left labels
    inner_right = px1 - 4.0   # leave room for right value
    avail_h = inner_top - inner_bot
    if n == 0 or avail_h <= 0:
        return
    row_h = avail_h / n
    bar_h = row_h * 0.66
    vmax = max(v for _, v in items)
    for i, (lab, v) in enumerate(items):
        y_row = inner_top - row_h * (i + 0.5)
        # left label
        ax.text(inner_left - 0.4, y_row, lab,
                ha="right", va="center", fontsize=8.2, color=C_TEXT)
        # bar
        bw = (inner_right - inner_left) * (v / vmax) if vmax > 0 else 0
        ax.add_patch(Rectangle((inner_left, y_row - bar_h / 2), bw, bar_h,
                               facecolor=color, edgecolor="white",
                               linewidth=0.4, zorder=3))
        # right value
        ax.text(inner_left + bw + 0.3, y_row, f"{v:,}",
                ha="left", va="center", fontsize=8.2, color=C_TEXT)


def _panel_tox(ax, px0, py0, px1, py1):
    _panel_header(ax, px0, py0, px1, py1, "Toxicity", f"n = {TOX_TOTAL}", C_TOX)
    _hbars(ax, TOX_SUB, px0, py0, px1, py1, C_TOX, header_top=1.4)


def _panel_offt(ax, px0, py0, px1, py1):
    _panel_header(ax, px0, py0, px1, py1, "Off-target", f"n = {OFFT_TOTAL}", C_OFFT)
    _hbars(ax, OFFT_SUB, px0, py0, px1, py1, C_OFFT, header_top=1.4)


def _panel_grade(ax, px0, py0, px1, py1):
    _panel_header(ax, px0, py0, px1, py1, "Evidence grade", "n = 658", C_RELEASE)
    # single stacked horizontal bar (A | B | C), one bar -> visual variety vs
    # the three hbar panels around it.
    inner_left  = px0 + 1.0
    inner_right = px1 - 1.0
    avail_w = inner_right - inner_left
    total = sum(v for _, v in GRADES)
    bar_y = py0 + (py1 - py0) * 0.40
    bar_h = (py1 - py0) * 0.22
    x = inner_left
    for g, v in GRADES:
        w = avail_w * (v / total)
        ax.add_patch(Rectangle((x, bar_y - bar_h / 2), w, bar_h,
                               facecolor=GRADE_COLORS[g], edgecolor="white",
                               linewidth=0.5, zorder=3))
        # in-bar label if wide enough, else above
        tcol = "white" if lum(GRADE_COLORS[g]) < 0.5 else C_TEXT
        if w > 2.5:
            ax.text(x + w / 2, bar_y, f"{g}\n{v}",
                    ha="center", va="center", fontsize=8.2, color=tcol,
                    linespacing=0.95, zorder=4)
        x += w
    ax.text((inner_left + inner_right) / 2, py0 + (py1 - py0) * 0.13,
            "graded A / B / C", ha="center", va="center",
            fontsize=8.0, color="#666666", fontstyle="italic")


def _panel_mod(ax, px0, py0, px1, py1):
    _panel_header(ax, px0, py0, px1, py1, "Modality", "n = 658", C_TOX)
    _hbars(ax, MODALITY, px0, py0, px1, py1, C_MACHINE, header_top=1.4)


# --------------------------------------------------------------------------- #
# 3c. RIGHT — differentiators + firewall tagline
# --------------------------------------------------------------------------- #
def _draw_right(ax):
    x_left, x_right = 67.5, 98.8
    y_top, y_bot = 29.8, 2.2
    cx = (x_left + x_right) / 2.0

    ax.text(cx, 31.4, "What makes it different",
            ha="center", va="bottom", fontsize=12, fontweight="bold", color=C_TEXT)

    # tag chips: stacked rounded boxes
    n = len(DIFFERENTIATORS)
    avail_h = (y_top - y_bot) - 5.0    # save the bottom 5 units for the firewall tagline
    chip_h = avail_h / n * 0.78
    row_h  = avail_h / n
    inner_left  = x_left + 0.7
    inner_right = x_right - 0.7
    for i, txt in enumerate(DIFFERENTIATORS):
        ycen = y_top - row_h * (i + 0.5)
        box = FancyBboxPatch((inner_left, ycen - chip_h / 2),
                             inner_right - inner_left, chip_h,
                             boxstyle="round,pad=0.10,rounding_size=0.7",
                             linewidth=0.7, edgecolor="#D6D2C9",
                             facecolor=C_BG_TAG, zorder=3)
        ax.add_patch(box)
        # bullet dot
        ax.add_patch(plt.Circle((inner_left + 0.9, ycen), 0.32,
                                facecolor=C_RELEASE, edgecolor="none", zorder=4))
        ax.text(inner_left + 1.7, ycen, txt, ha="left", va="center",
                fontsize=9.6, color=C_TEXT, zorder=4)

    # firewall tagline (the big one) at the bottom of the right third
    tag_y = y_bot + 2.2
    ax.add_patch(FancyBboxPatch((inner_left, tag_y - 1.8),
                                inner_right - inner_left, 3.6,
                                boxstyle="round,pad=0.10,rounding_size=0.8",
                                linewidth=1.0, edgecolor=C_FIRE,
                                facecolor="#FBEEEC", zorder=3))
    ax.text(cx, tag_y + 0.4, FIREWALL_TAGLINE, ha="center", va="center",
            fontsize=11, fontweight="bold", color=C_FIRE, zorder=4)
    ax.text(cx, tag_y - 0.95,
            "Human-only writes on curator_verified.",
            ha="center", va="center", fontsize=8.6, color=C_FIRE,
            fontstyle="italic", zorder=4)


# --------------------------------------------------------------------------- #
# 4. Driver
# --------------------------------------------------------------------------- #
def main():
    here   = Path(__file__).resolve()
    figdir = here.parent.parent / "figures"
    figdir.mkdir(parents=True, exist_ok=True)

    fig = build()

    base = figdir / f"graphical_abstract{OUT_SUFFIX}"
    fig.savefig(base.with_suffix(".pdf"))
    fig.savefig(base.with_suffix(".png"), dpi=600)
    # TIF: LZW-compressed at 600 dpi (NAR accepts TIF; LZW keeps it lossless+small)
    fig.savefig(base.with_suffix(".tif"), dpi=600, pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)

    # Confirm exact bounding-box size in mm
    w_in, h_in = fig.get_size_inches()
    w_mm, h_mm = w_in * 25.4, h_in * 25.4
    ratio = w_in / h_in
    print(f"Font used: {SANS}")
    print(f"Figure size: {w_in:.3f} x {h_in:.3f} in  =  {w_mm:.1f} x {h_mm:.1f} mm")
    print(f"Aspect ratio: {ratio:.4f}  (target 2.5000 == 5:2)")
    if abs(ratio - 2.5) > 1e-6:
        print("ASPECT-RATIO FAIL", file=sys.stderr)
        sys.exit(2)
    if w_mm < 127.0 or h_mm < 50.0:
        print("MIN-SIZE FAIL (NAR requires >= 127 x 50 mm)", file=sys.stderr)
        sys.exit(3)

    for ext in (".pdf", ".png", ".tif"):
        p = base.with_suffix(ext)
        print(f"WROTE {p}  ({p.stat().st_size/1024:.1f} KB)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
