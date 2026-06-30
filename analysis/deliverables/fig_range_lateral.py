"""
Range-vs-lateral refraction-signature figure (MET-06).

Single panel: grouped bars per validation frame — range_rms_mm vs lateral_rms_mm —
with the pooled value set off to the right behind a divider. Range bars are clearly
taller than lateral bars for every frame, reflecting the range-dominated residual
structure (pooled dominance ratio = refraction signature, read from the artifact).

Run:
    python -m analysis.deliverables.fig_range_lateral
"""

import matplotlib
matplotlib.use("Agg")  # headless backend

import matplotlib.pyplot as plt
import numpy as np

from analysis.deliverables._style import dissertation_style, COLORS, save_figure
from analysis.deliverables._artifacts import load_error_decomp, FIGURES_DIR


def main() -> None:
    data = load_error_decomp()

    # --- per-frame arrays ---
    frames = data["per_frame"]
    frame_labels = [str(f["frame_idx"]) for f in frames]
    range_per_frame = np.array([f["range_lateral"]["range_rms_mm"] for f in frames])
    lateral_per_frame = np.array([f["range_lateral"]["lateral_rms_mm"] for f in frames])

    # --- pooled range/lateral ---
    pooled_rl = data["pooled"]["range_lateral"]
    pooled_range = pooled_rl["range_rms_mm"]
    pooled_lateral = pooled_rl["lateral_rms_mm"]
    dominance = pooled_rl["range_dominance"]  # read from artifact — never hardcoded

    n_frames = len(frames)
    x_per_frame = np.arange(n_frames)
    bar_width = 0.38

    color_range = COLORS["blue"]
    color_lateral = COLORS["gold"]

    with dissertation_style():
        fig, ax1 = plt.subplots(figsize=(7.6, 4.4))

        # Per-frame bars, then the pooled group set off after a clear gap.
        x_sep = n_frames - 0.4            # divider sits in the gap
        x_pooled = n_frames + 0.6
        x_all = np.append(x_per_frame, x_pooled)
        labels_all = frame_labels + ["Pooled"]
        range_all = np.append(range_per_frame, pooled_range)
        lateral_all = np.append(lateral_per_frame, pooled_lateral)

        # Shade + divider to separate per-frame from pooled
        ax1.axvspan(x_sep, x_pooled + 0.6, color=COLORS["gray"], alpha=0.15, zorder=0)
        ax1.axvline(x_sep, color=COLORS["dark gray"], lw=0.9, ls="--", zorder=1)

        ax1.bar(x_all - bar_width / 2, range_all, bar_width,
                label="Range RMS", color=color_range, zorder=3)
        ax1.bar(x_all + bar_width / 2, lateral_all, bar_width,
                label="Lateral RMS", color=color_lateral, zorder=3)

        ax1.axhline(1.0, color=COLORS["dark gray"], linewidth=0.7, linestyle=":", zorder=2)
        ax1.set_xticks(x_all)
        ax1.set_xticklabels(labels_all)
        ax1.set_xlabel("Validation frame number")
        ax1.set_ylabel("Residual RMS [mm]")
        ax1.set_title("Range and Lateral Residual RMS per Validation Frame")
        ax1.legend(loc="upper left")

        # Region labels above the bars
        ymax = max(range_all.max(), 1.0) * 1.18
        ax1.set_ylim(0, ymax)
        ax1.text((n_frames - 1) / 2, ymax * 0.97, "per-frame", ha="center", va="top",
                 fontsize=7.5, color=COLORS["dark gray"], style="italic")
        ax1.text(x_pooled, ymax * 0.97, "pooled", ha="center", va="top",
                 fontsize=7.5, color=COLORS["dark gray"], style="italic")

        fig.tight_layout()

        paths = save_figure(
            fig, "range_vs_lateral",
            output_dir=FIGURES_DIR,
            formats=("svg", "pdf", "png")
        )
        for p in paths:
            print(f"Saved: {p}")


if __name__ == "__main__":
    main()
