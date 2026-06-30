"""
Spatial-consistency figure (OUT-02).

Shows flatness RMS and board size vs working-volume position (depth, lateral, tilt)
across the 8 evaluation frames, in DissertationFigures style.

Visual message: both flatness (~1.1 mm) and board size (~60 mm, CV 0.0016) remain
essentially flat across the full working volume — the refractive model holds.

Run:
    python -m analysis.deliverables.fig_spatial_consistency
"""

import matplotlib
matplotlib.use("Agg")  # headless backend

import matplotlib.pyplot as plt
import numpy as np

from analysis.deliverables._style import dissertation_style, COLORS, PALETTE, save_figure
from analysis.deliverables._artifacts import load_flatness, FIGURES_DIR


def main() -> None:
    data = load_flatness()
    pfa = data["variation"]["per_frame_arrays"]

    # --- read arrays ---
    depth_m = np.array(pfa["depth_m"])
    lateral_m = np.array(pfa["lateral_xy_m"])
    tilt_deg = np.array(pfa["tilt_deg"])
    flatness_mm = np.array(pfa["flatness_rms_mm"])
    board_mm = np.array(pfa["board_size_mm"])

    pooled_flatness = data["pooled"]["flatness_rms_mm_pooled"]
    board_mean = data["variation"]["board_size_mm_mean"]
    # nominal board size = 60 mm
    board_nominal = 60.0

    # depth is negative (below surface) — display as positive depth below surface
    depth_pos = np.abs(depth_m)

    # colour-encode tilt (3rd dimension) with a sequential palette
    tilt_norm = (tilt_deg - tilt_deg.min()) / (tilt_deg.max() - tilt_deg.min())
    cmap_colors = [COLORS["blue"], COLORS["teal"], COLORS["gold"]]
    # build a simple linear colormap from palette extremes
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("tilt_cmap", cmap_colors)
    marker_colors = cmap(tilt_norm)

    fig_width = 10.0   # inches (dissertation full-width)
    fig_height = 6.0

    with dissertation_style():
        fig, axes = plt.subplots(2, 3, figsize=(fig_width, fig_height))

        x_labels = [
            ("Depth below surface [m]", depth_pos),
            ("Lateral position [m]", lateral_m),
            ("Tilt angle [deg]", tilt_deg),
        ]

        scatter_kw = dict(s=60, zorder=5, edgecolors="none")

        # Row 0: flatness_rms_mm
        for col, (xlabel, xdata) in enumerate(x_labels):
            ax = axes[0, col]
            sc = ax.scatter(xdata, flatness_mm, c=marker_colors, **scatter_kw)
            ax.axhline(pooled_flatness, color=COLORS["coral"], linewidth=1.2,
                       linestyle="--", label=f"Pooled RMS {pooled_flatness:.2f} mm")
            ax.set_xlabel(xlabel)
            if col == 0:
                ax.set_ylabel("Flatness RMS [mm]")
            ax.set_title(f"Flatness vs {xlabel.split('[')[0].strip()}")
            ax.legend(fontsize=7, loc="upper right")

        # Row 1: board_size_mm
        for col, (xlabel, xdata) in enumerate(x_labels):
            ax = axes[1, col]
            sc = ax.scatter(xdata, board_mm, c=marker_colors, **scatter_kw)
            ax.axhline(board_nominal, color=COLORS["indigo"], linewidth=1.2,
                       linestyle=":", label=f"Nominal {board_nominal:.0f} mm")
            ax.axhline(board_mean, color=COLORS["olive"], linewidth=1.2,
                       linestyle="--", label=f"Measured mean {board_mean:.1f} mm")
            ax.set_xlabel(xlabel)
            if col == 0:
                ax.set_ylabel("Board size [mm]")
            ax.set_title(f"Board size vs {xlabel.split('[')[0].strip()}")
            ax.legend(fontsize=7, loc="upper right")

        # Shared colorbar for tilt
        sm = plt.cm.ScalarMappable(
            cmap=cmap,
            norm=plt.Normalize(vmin=tilt_deg.min(), vmax=tilt_deg.max())
        )
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=axes[:, 2], shrink=0.8, pad=0.04)
        cbar.set_label("Tilt angle [deg]")

        fig.suptitle(
            "Spatial Consistency: Flatness and Board Size vs Working-Volume Position",
            y=1.01
        )
        fig.tight_layout()

        paths = save_figure(
            fig, "spatial_consistency",
            output_dir=FIGURES_DIR,
            formats=("svg", "pdf", "png")
        )
        for p in paths:
            print(f"Saved: {p}")


if __name__ == "__main__":
    main()
