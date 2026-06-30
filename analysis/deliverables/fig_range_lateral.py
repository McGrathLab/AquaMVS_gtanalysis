"""
Range-vs-lateral refraction-signature figure (MET-06).

Primary panel: grouped bars per frame — range_rms_mm vs lateral_rms_mm —
plus a pooled group at the right.  Range bars are clearly taller than lateral
bars for every frame, reflecting the range-dominated residual structure
(pooled dominance ratio ~4.41x = refraction signature).

Optional second panel: board-frame out-of-plane vs in-plane (pooled) as a
conceptual contrast.

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

    # --- pooled board-frame ---
    pooled_bf = data["pooled"]["board_frame"]
    out_of_plane = pooled_bf["out_of_plane_rms_mm"]
    in_plane = pooled_bf["in_plane_rms_mm"]

    n_frames = len(frames)
    x_per_frame = np.arange(n_frames)
    bar_width = 0.35

    color_range = COLORS["blue"]
    color_lateral = COLORS["gold"]
    color_oop = COLORS["teal"]
    color_ip = COLORS["coral"]

    with dissertation_style():
        fig, (ax1, ax2) = plt.subplots(
            1, 2,
            figsize=(11, 4.5),
            gridspec_kw={"width_ratios": [3, 1]}
        )

        # ---- Panel 1: per-frame + pooled grouped bars ----
        x_all = np.append(x_per_frame, n_frames + 0.5)  # extra gap before pooled
        labels_all = frame_labels + ["Pooled"]
        range_all = np.append(range_per_frame, pooled_range)
        lateral_all = np.append(lateral_per_frame, pooled_lateral)

        bars_range = ax1.bar(
            x_all - bar_width / 2, range_all, bar_width,
            label="Range RMS", color=color_range, zorder=3
        )
        bars_lateral = ax1.bar(
            x_all + bar_width / 2, lateral_all, bar_width,
            label="Lateral RMS", color=color_lateral, zorder=3
        )

        ax1.set_xticks(x_all)
        ax1.set_xticklabels(labels_all)
        ax1.set_xlabel("Frame index")
        ax1.set_ylabel("Residual RMS [mm]")
        ax1.set_title("Range vs Lateral Residual RMS per Frame")
        ax1.legend(loc="upper right")
        ax1.axhline(1.0, color="grey", linewidth=0.7, linestyle=":", zorder=2)

        # Annotate pooled dominance ratio (read from artifact)
        x_pooled = n_frames + 0.5
        y_annot = pooled_range + 0.15
        ax1.annotate(
            f"Range-dominated\n{dominance:.2f}× (pooled)\nLateral sub-mm",
            xy=(x_pooled, pooled_range),
            xytext=(x_pooled - 1.8, pooled_range + 1.2),
            fontsize=7,
            arrowprops=dict(arrowstyle="->", color="black", lw=0.8),
            ha="center",
            color="black",
        )

        # ---- Panel 2: board-frame out-of-plane vs in-plane (pooled) ----
        bf_labels = ["Out-of-plane", "In-plane"]
        bf_vals = [out_of_plane, in_plane]
        bf_colors = [color_oop, color_ip]
        ax2.bar(bf_labels, bf_vals, color=bf_colors, zorder=3, width=0.45)
        ax2.set_ylabel("Residual RMS [mm]")
        ax2.set_title("Board-Frame\nDecomposition (pooled)")
        ax2.set_ylim(0, max(bf_vals) * 1.5)
        for i, v in enumerate(bf_vals):
            ax2.text(i, v + 0.02, f"{v:.2f}", ha="center", va="bottom", fontsize=8)

        fig.suptitle(
            f"Refraction Signature: Range-dominated ~{dominance:.1f}× "
            f"(range {pooled_range:.2f} mm vs lateral {pooled_lateral:.2f} mm)"
        )
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
