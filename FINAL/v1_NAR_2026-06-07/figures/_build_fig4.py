import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.image import imread

# Prefer Arial; fall back gracefully if unavailable
try:
    from matplotlib import font_manager
    avail = {f.name for f in font_manager.fontManager.ttflist}
    if "Arial" in avail:
        plt.rcParams["font.family"] = "Arial"
    else:
        plt.rcParams["font.family"] = "DejaVu Sans"
        print("WARN Arial not found, using DejaVu Sans")
except Exception as e:
    print("font setup warn:", e)

base = "C:/Users/Jie/Desktop/NAR_OligoSafetyDB/repo_ready/FINAL/v1_NAR_2026-06-07/figures/m2_panels/"
A = base + "m2_panel_a_landing.png"
B = base + "m2_panel_b_evidence.png"
C = base + "m2_panel_c_record.png"
D = base + "m2_panel_d_agent.png"

panels = [
    (A, "A", "Search & browse"),
    (B, "B", "Verified-release evidence"),
    (C, "C", "Citable-record provenance"),
    (D, "D", "Programmatic agent access"),
]

# Load images, track success
imgs = []
all_ok = True
for path, letter, sub in panels:
    try:
        img = imread(path)
        imgs.append(img)
        print(f"loaded {letter}: shape={img.shape}")
    except Exception as e:
        all_ok = False
        imgs.append(None)
        print(f"FAILED {letter}: {e}")

fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.0), dpi=600)  # 183mm wide double-column
flat = axes.flatten()  # order: top-left, top-right, bottom-left, bottom-right -> A B C D

for ax, (path, letter, sub), img in zip(flat, panels, imgs):
    if img is not None:
        ax.imshow(img)
    # hide ticks but keep frame for the grey border
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_edgecolor("#cccccc")
        spine.set_linewidth(0.5)
    # Keep panel labels outside screenshots so they never occlude portal content.
    ax.set_title(f"{letter}  {sub}", fontsize=8, fontweight="bold", loc="left", pad=3)

plt.tight_layout(pad=0.8)

out_pdf = "C:/Users/Jie/Desktop/NAR_OligoSafetyDB/repo_ready/FINAL/v1_NAR_2026-06-07/figures/FIG4_walkthrough.pdf"
out_png = "C:/Users/Jie/Desktop/NAR_OligoSafetyDB/repo_ready/FINAL/v1_NAR_2026-06-07/figures/FIG4_walkthrough.png"
fig.savefig(out_pdf, dpi=600, bbox_inches="tight")
fig.savefig(out_png, dpi=600, bbox_inches="tight")
plt.close(fig)

print("ALL_FOUR_OK", all_ok)
print("SAVED", out_pdf)
print("SAVED", out_png)
