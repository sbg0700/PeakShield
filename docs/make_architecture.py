"""Generate docs/architecture.png — the PeakShield system architecture diagram.

Pure matplotlib (no graphviz). English labels keep it font-independent.
Run: python docs/make_architecture.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path(__file__).resolve().parent / "architecture.png"

# palette
C_DATA = "#9aa5b1"
C_PIPE = "#4f83cc"
C_ML = "#3fa66a"
C_OPT = "#8b5fbf"
C_ECON = "#e08a3c"
C_SERVE = "#2bb6b0"
C_ART = "#eef2f7"
C_EDGE = "#33414f"

fig, ax = plt.subplots(figsize=(12.5, 15.5))
ax.set_xlim(0, 12)
ax.set_ylim(0, 16.5)
ax.axis("off")


def box(cx, cy, w, h, text, fc, fontsize=9, bold=False, text_color="white", artifact=False):
    style = "round,pad=0.02,rounding_size=0.12"
    if artifact:
        style = "round,pad=0.02,rounding_size=0.04"
    p = FancyBboxPatch(
        (cx - w / 2, cy - h / 2), w, h,
        boxstyle=style, linewidth=1.3,
        edgecolor=C_EDGE, facecolor=fc, zorder=2,
    )
    ax.add_patch(p)
    ax.text(
        cx, cy, text, ha="center", va="center",
        fontsize=fontsize, color=text_color,
        fontweight="bold" if bold else "normal", zorder=3, wrap=True,
    )
    return (cx, cy, w, h)


def arrow(src, dst, style="-|>", color=C_EDGE, dashed=False, label=None, rad=0.0, lw=1.6):
    sx, sy, sw, sh = src
    dx, dy, dw, dh = dst
    # connect bottom-of-src to top-of-dst by default (vertical-ish)
    x1, y1 = sx, sy - sh / 2
    x2, y2 = dx, dy + dh / 2
    a = FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle=style, mutation_scale=14,
        linewidth=lw, color=color, zorder=1,
        connectionstyle=f"arc3,rad={rad}",
        linestyle="--" if dashed else "-",
    )
    ax.add_patch(a)
    if label:
        ax.text((x1 + x2) / 2 + 0.15, (y1 + y2) / 2, label, fontsize=7.5,
                color=color, ha="left", va="center", style="italic", zorder=3)


def hlabel(y, text):
    ax.text(0.15, y, text, fontsize=10, fontweight="bold", color=C_EDGE,
            ha="left", va="center", rotation=90)


ax.text(6, 16.1, "PeakShield — System Architecture", ha="center",
        fontsize=16, fontweight="bold", color="#1b2733")
ax.text(6, 15.65, "Steel-process electricity peak-shaving & cost optimization "
        "(notebook analysis → reproducible Python pipeline + realtime dashboard)",
        ha="center", fontsize=9, color="#55636f")

# ---- Inputs ----
i1 = box(3.05, 14.7, 5.2, 1.0,
         "data/raw/Steel_industry_data.csv\nUCI Steel Industry Energy · 15-min · 35,040 rows",
         C_DATA, 8.5)
i2 = box(8.95, 14.7, 5.2, 1.0,
         "config/electricity_config_master.json\n8 KEPCO tariff scenarios (2018 / 2026 · opt1-3 …)",
         C_DATA, 8.5)

# ---- Feature pipeline ----
p1 = box(6, 12.9, 10.2, 1.15,
         "scripts/01_build_features.py\n"
         "time + cyclic + power features · CO2 RandomForest imputation · operating-state flag · PSI",
         C_PIPE, 9, bold=True)
a1 = box(6, 11.45, 5.0, 0.7,
         "data/processed/features.parquet  (+ reactive_maxima.json)",
         C_ART, 8.5, text_color="#1b2733", artifact=True)

# ---- Surrogate models ----
m1 = box(6, 9.95, 10.2, 1.1,
         "scripts/02_train_surrogate.py  →  XGBoost surrogates\n"
         "Usage_kWh & PF_Physical (monotonic constraints)  →  models/*.json",
         C_ML, 9, bold=True)

# ---- Optimization ----
o1 = box(6, 8.15, 10.4, 1.25,
         "scripts/03_run_optimization.py  →  HybridFastSimulator\n"
         "grid precompute (motor × capacitor) + Optuna fine-tune ·\n"
         "monthly power-factor mileage · production-deficit tracking",
         C_OPT, 9, bold=True)
a2 = box(6, 6.7, 5.2, 0.7,
         "data/processed/sim_<scenario>.parquet",
         C_ART, 8.5, text_color="#1b2733", artifact=True)

# ---- Economics & export ----
e1 = box(3.05, 4.95, 5.4, 1.35,
         "scripts/04_evaluate_roi.py\nKEPCO PF penalty · financial ROI · settlement\n"
         "→ roi_summary.csv · final_opt3_kepco_ready.csv",
         C_ECON, 8.5, bold=True)
e2 = box(8.95, 4.95, 5.4, 1.35,
         "scripts/05_export_dashboard.py\nrealtime cost + PSI stream\n"
         "→ final_2018ver.csv · final_2026ver.csv",
         C_ECON, 8.5, bold=True)

# ---- Serving ----
s0 = box(2.0, 2.7, 3.0, 1.0,
         "dashboard/sender.py\nreplay CSV → /ingest", C_SERVE, 8.2)
s1 = box(6.0, 2.7, 5.0, 1.2,
         "dashboard/app.py  :5001\nEnergy + CO2 (SSE · single page · 3 tabs)",
         C_SERVE, 8.8, bold=True)
s2 = box(10.3, 2.7, 3.0, 1.2,
         "process_app/app.py\n:4444  Process flow", C_SERVE, 8.5, bold=True)
note = box(6, 0.85, 10.2, 0.85,
           "Browser opens :5001  →  the 'Process' tab embeds :4444 via iframe (lazy-load)  "
           "⇒  one unified 3-tab dashboard",
           "#dff5f4", 8.6, text_color="#0c3b39")

# ---- Arrows ----
arrow(i1, p1)
arrow(i2, p1)
arrow(p1, a1)
arrow(a1, m1)
arrow(m1, o1)
arrow(o1, a2)
arrow(a2, e1, rad=0.12)
arrow(a2, e2, rad=-0.12)
arrow(e2, s1)
# config feeds the simulator and economics (long dashed on the right)
arrow(i2, o1, dashed=True, color=C_OPT, rad=-0.45)
ax.text(11.35, 11.3, "tariff\nscenarios", fontsize=7.5, color=C_OPT,
        style="italic", ha="center", va="center", zorder=3)
# sender → 5001, and 4444 → 5001 (iframe)
arrow(s0, s1, style="-|>", rad=0.0)
a = FancyArrowPatch((s2[0] - s2[2] / 2, s2[1]), (s1[0] + s1[2] / 2, s1[1]),
                    arrowstyle="-|>", mutation_scale=14, linewidth=1.6,
                    color="#0c3b39", linestyle="--", zorder=1,
                    connectionstyle="arc3,rad=0.0")
ax.add_patch(a)
ax.text(8.6, 3.15, "iframe embed", fontsize=7.5, color="#0c3b39", style="italic", ha="center")

# legend
from matplotlib.patches import Patch
legend = [
    Patch(facecolor=C_DATA, edgecolor=C_EDGE, label="Inputs"),
    Patch(facecolor=C_PIPE, edgecolor=C_EDGE, label="Feature pipeline"),
    Patch(facecolor=C_ML, edgecolor=C_EDGE, label="Surrogate ML"),
    Patch(facecolor=C_OPT, edgecolor=C_EDGE, label="Optimization"),
    Patch(facecolor=C_ECON, edgecolor=C_EDGE, label="Economics / export"),
    Patch(facecolor=C_SERVE, edgecolor=C_EDGE, label="Serving (dashboards)"),
    Patch(facecolor=C_ART, edgecolor=C_EDGE, label="Artifact (gitignored)"),
]
ax.legend(handles=legend, loc="lower center", bbox_to_anchor=(0.5, -0.035),
          ncol=4, fontsize=8, frameon=False)

plt.tight_layout()
fig.savefig(OUT, dpi=150, bbox_inches="tight", facecolor="white")
print(f"saved: {OUT}")
