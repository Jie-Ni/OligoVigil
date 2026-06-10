#!/usr/bin/env python3
"""
Render NAR Fig 5 peer comparison: 2-panel matplotlib figure.

Panel A: Area-proportional Venn3 of literature evidence (PMIDs) across
         OligoVigil, CRISPRoffT, and siRNAEfficacyDB. All pairwise and
         triple intersections are empty (real finding, not missing data).

Panel B: Feature support heatmap across six oligonucleotide-safety DBs.
         Cell values: 1.0 = yes, 0.5 = partial, 0.0 = absent/unknown.

Outputs: FIG5_peer_comparison.pdf, .png, .svg @ 600 dpi.

Re-render 2026-06-08: ensure Panel B label is visible (was previously
overlapping with the heatmap title). Solution: drop the heatmap title and
push the "B" label outside the heatmap axes on the left.
"""

import os

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from matplotlib_venn import venn3, venn3_circles

# ---------- Configuration ----------
FIG_DIR = "C:/Users/Jie/Desktop/NAR_OligoSafetyDB/repo_ready/FINAL/v1_NAR_2026-06-07/figures"
PEER_DIR = os.path.join(FIG_DIR, "peer_data")

OUT_BASE = os.path.join(FIG_DIR, "FIG5_peer_comparison")

# Shared palette
OLIGOVIGIL_BLUE = "#3A6EA5"
PEER_PALETTE = ["#C26B3E", "#6B7FB3", "#E0A458", "#2E8B83", "#C2BDB6"]

# Fonts
mpl.rcParams["font.family"] = "Arial"
mpl.rcParams["pdf.fonttype"] = 42  # editable text in PDF
mpl.rcParams["ps.fonttype"] = 42
mpl.rcParams["svg.fonttype"] = "none"


# ---------- Load real PMID sets ----------
def load_pmids(path):
    with open(path, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


pmids_ov = load_pmids(os.path.join(PEER_DIR, "oligovigil_pmids.txt"))
pmids_cr = load_pmids(os.path.join(PEER_DIR, "CRISPRoffT_pmids.txt"))
pmids_si = load_pmids(os.path.join(PEER_DIR, "siRNAEfficacyDB_pmids.txt"))

# Compute real set intersections
only_a = len(pmids_ov - pmids_cr - pmids_si)
only_b = len(pmids_cr - pmids_ov - pmids_si)
only_c = len(pmids_si - pmids_ov - pmids_cr)
ab = len((pmids_ov & pmids_cr) - pmids_si)
ac = len((pmids_ov & pmids_si) - pmids_cr)
bc = len((pmids_cr & pmids_si) - pmids_ov)
abc = len(pmids_ov & pmids_cr & pmids_si)

print("[Panel A] Real set intersections:")
print(f"  OligoVigil only      = {only_a}")
print(f"  CRISPRoffT only      = {only_b}")
print(f"  siRNAEfficacyDB only = {only_c}")
print(f"  ov n cr              = {ab}")
print(f"  ov n si              = {ac}")
print(f"  cr n si              = {bc}")
print(f"  all three            = {abc}")
print(f"  Total unique PMIDs   = {len(pmids_ov | pmids_cr | pmids_si)}")


# ---------- Panel B data ----------
features = [
    "Total curated records",
    "Source-anchored provenance (1:1 quote+PMID+section)",
    "Inter-rater reliability (kappa)",
    "AI/ML false-accept audit",
    "Benchmark + deterministic baselines",
    "Structured assay metadata (dose/exposure/tissue/organism)",
    "Chemical-modification coverage (per-position)",
    "Off-target gene-level resolution",
    "Open no-login web portal",
    "Programmatic interfaces (REST/OpenAPI/MCP/Bioschemas)",
    "Versioned bulk download + per-release DOI",
    "License (code + data)",
    "Maintenance + named curator",
]
dbs = ["OligoVigil", "theRNA", "siRNAEfficacyDB", "CMsiRNAdb", "siRNAmod", "CRISPRoffT"]
matrix = np.array([
    [1,   1,   1,   1,   1,   1  ],
    [1,   1,   0.5, 0.5, 0.5, 0.5],
    [1,   0,   0,   0,   0,   0  ],
    [1,   0,   0,   0,   0,   0  ],
    [1,   0,   0,   0,   0,   0.5],
    [0.5, 0.5, 1,   0.5, 0,   0.5],
    [0,   0.5, 0,   1,   1,   0  ],
    [0.5, 0,   0,   0,   0,   1  ],
    [1,   1,   1,   1,   0,   1  ],
    [1,   0.5, 0.5, 0.5, 0,   0.5],
    [1,   0.5, 0.5, 0.5, 0.5, 0.5],
    [1,   0,   1,   0,   0,   0.5],
    [1,   1,   1,   1,   0.5, 1  ],
])

# Validation per spec
yes_count = int((matrix == 1.0).sum())
partial_count = int((matrix == 0.5).sum())
absent_count = int((matrix == 0.0).sum())
print(f"\n[Panel B] Cell tallies: yes={yes_count}, partial={partial_count}, absent={absent_count}")
print(f"  Sum={yes_count + partial_count + absent_count} (expected 78)")
ov_col = matrix[:, 0]
print(f"  OligoVigil col: yes={(ov_col == 1.0).sum()}, partial={(ov_col == 0.5).sum()}, "
      f"absent={(ov_col == 0.0).sum()} (spec: 10/2/1)")


# ---------- Figure ----------
fig = plt.figure(figsize=(8.5, 4.0), dpi=600)
fig.patch.set_facecolor("white")
# Wider right panel + bigger wspace so the heatmap's long y-tick labels
# do not crash into Panel A on the left.
gs = fig.add_gridspec(1, 2, width_ratios=[1, 2.2], wspace=1.2,
                      left=0.07, right=0.92, top=0.88, bottom=0.22)
ax_a = fig.add_subplot(gs[0, 0])
ax_b = fig.add_subplot(gs[0, 1])

# ===== Panel A: area-proportional Venn3 =====
ax_a.set_facecolor("white")

# venn3 subset arg order: (Abc, aBc, ABc, abC, AbC, aBC, ABC)
# i.e. (only_a, only_b, ab, only_c, ac, bc, abc)
venn = venn3(
    subsets=(only_a, only_b, ab, only_c, ac, bc, abc),
    set_labels=("OligoVigil", "CRISPRoffT", "siRNAEfficacyDB"),
    set_colors=(OLIGOVIGIL_BLUE, PEER_PALETTE[0], PEER_PALETTE[1]),
    alpha=0.65,
    ax=ax_a,
)
circles = venn3_circles(
    subsets=(only_a, only_b, ab, only_c, ac, bc, abc),
    linestyle="solid",
    linewidth=0.8,
    color="#333333",
    ax=ax_a,
)

# Style set labels and subset labels
for lbl in venn.set_labels:
    if lbl is not None:
        lbl.set_fontsize(8.5)
        lbl.set_fontweight("bold")
for lbl in venn.subset_labels:
    if lbl is not None:
        lbl.set_fontsize(9)
        lbl.set_color("white")
        lbl.set_fontweight("bold")

ax_a.set_title(
    "Literature evidence (unique PMIDs)\nNo overlap across the three DBs",
    fontsize=9, pad=4,
)

# Panel A label (placed top-left, outside circles)
ax_a.text(
    -0.05, 1.05, "A",
    transform=ax_a.transAxes,
    fontsize=14, fontweight="bold", va="top", ha="right",
)

# Caption-style annotation under Panel A. Anchor it to the LEFT edge of
# ax_a (ha="left") so the italic text does NOT extend into Panel B's
# heatmap area on the right.
ax_a.text(
    0.0, -0.08,
    "Pairwise and triple\nintersections = 0 (real finding).",
    transform=ax_a.transAxes,
    fontsize=7, ha="left", va="top", color="#444444", style="italic",
)

# ===== Panel B: feature support heatmap =====
# RdYlGn cmap: 0=absent (red) -> 0.5=partial (yellow) -> 1=yes (green)
cmap = plt.get_cmap("RdYlGn")

hm = sns.heatmap(
    matrix,
    xticklabels=dbs,
    yticklabels=features,
    cmap=cmap,
    vmin=0, vmax=1,
    ax=ax_b,
    square=False,
    linewidths=0.5,
    linecolor="white",
    cbar_kws={
        "ticks": [0, 0.5, 1.0],
        "label": "Feature support",
        "shrink": 0.7,
        "aspect": 18,
        "pad": 0.02,
    },
)

# Bold OligoVigil x-tick (column index 0)
ax_b.set_xticklabels(
    [
        ("$\\mathbf{" + d + "}$" if d == "OligoVigil" else d)
        for d in dbs
    ],
    rotation=30, ha="right", fontsize=8,
)
ax_b.set_yticklabels(features, fontsize=7, rotation=0)

# Colorbar ticks label text
cbar = hm.collections[0].colorbar
cbar.set_ticks([0, 0.5, 1.0])
cbar.set_ticklabels(["absent /\nunknown", "partial", "yes"])
cbar.ax.tick_params(labelsize=7)
cbar.ax.yaxis.label.set_size(8)

# NO title on Panel B -- the panel label is enough; heatmap is self-
# explanatory with the cbar label.
# Panel B label placed OUTSIDE the heatmap on the left, far enough that
# the long y-tick labels do not collide with it.
ax_b.text(
    -0.55, 1.05, "B",
    transform=ax_b.transAxes,
    fontsize=14, fontweight="bold", va="top", ha="right",
)

# Do NOT call tight_layout -- it warns/breaks when matplotlib_venn axes
# are present. We sized the gridspec margins explicitly above.

# ---------- Save outputs ----------
for ext in ("pdf", "png", "svg"):
    out_path = f"{OUT_BASE}.{ext}"
    save_kwargs = {"facecolor": "white", "bbox_inches": "tight"}
    if ext == "png":
        save_kwargs["dpi"] = 600
    fig.savefig(out_path, **save_kwargs)
    size = os.path.getsize(out_path)
    print(f"[saved] {out_path}  ({size} bytes)")

plt.close(fig)
print("Done.")
