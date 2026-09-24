"""
Spatial-consistency figure (OUT-02).

Shows flatness RMS and board size vs working-volume position (depth, lateral, tilt)
across the 8 evaluation frames, in DissertationFigures style.

Visual message: both flatness (~1.1 mm) and board size (~60 mm, CV 0.0016) remain
essentially flat across the full working volume — the refractive model holds.

With --pinhole, the pinhole-ablation run is overlaid (R2.1): each of its frames is placed
at the refractive run's depth / lateral position / tilt for the same physical pose, so the
two arms can be compared pose by pose.

Run:
    python -m analysis.deliverables.fig_spatial_consistency \
        [--root ANALYSIS_OUTPUT] [--pinhole PINHOLE_ANALYSIS_OUTPUT] [--out DIR] [--name NAME]
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless backend

import matplotlib.pyplot as plt
import numpy as np

from analysis.deliverables._style import dissertation_style, COLORS, PALETTE, save_figure
from analysis.deliverables._artifacts import load_flatness, FIGURES_DIR


def render(root: Path | None = None, pinhole: Path | None = None,
           out: Path | None = None, name: str = "spatial_consistency") -> list[Path]:
    data = load_flatness(root)
    frames = sorted(data["per_frame"], key=lambda f: f["frame_idx"])

    # --- read arrays ---
    depth_m = np.array([f["depth_m"] for f in frames])
    lateral_m = np.array([f["lateral_xy_m"] for f in frames])
    tilt_deg = np.array([f["tilt_deg"] for f in frames])
    flatness_mm = np.array([f["flatness_rms_mm"] for f in frames])
    board_mm = np.array([f["board_size_mm"] for f in frames])

    ph = None
    if pinhole is not None:
        by_idx = {f["frame_idx"]: f for f in load_flatness(pinhole)["per_frame"]}
        keep = [i for i, f in enumerate(frames) if f["frame_idx"] in by_idx]
        ph = {
            "idx": keep,
            "flatness_mm": np.array([by_idx[frames[i]["frame_idx"]]["flatness_rms_mm"] for i in keep]),
            "board_mm": np.array([by_idx[frames[i]["frame_idx"]]["board_size_mm"] for i in keep]),
        }

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
        fig, axes = plt.subplots(
            2, 3, figsize=(fig_width, fig_height), constrained_layout=True
        )

        x_labels = [
            ("Depth below surface [m]", depth_pos),
            ("Lateral position [m]", lateral_m),
            ("Tilt angle [deg]", tilt_deg),
        ]

        scatter_kw = dict(s=60, zorder=5, edgecolors="none")

        # Row 0: flatness_rms_mm
        for col, (xlabel, xdata) in enumerate(x_labels):
            ax = axes[0, col]
            sc = ax.scatter(xdata, flatness_mm, c=marker_colors, label="Refractive", **scatter_kw)
            if ph is not None:
                ax.scatter(xdata[ph["idx"]], ph["flatness_mm"], marker="s", s=34, zorder=4,
                           facecolors="none", edgecolors=COLORS["coral"], linewidths=1.1,
                           label="Pinhole (re-fitted)")
            ax.axhline(pooled_flatness, color=COLORS["dark gray"], linewidth=1.2,
                       linestyle="--", label=f"Refractive pooled RMS {pooled_flatness:.2f} mm")
            ax.set_xlabel(xlabel)
            if col == 0:
                ax.set_ylabel("Flatness RMS [mm]")
            ax.set_title(f"Flatness vs {xlabel.split('[')[0].strip()}")

        # Row 1: board_size_mm
        for col, (xlabel, xdata) in enumerate(x_labels):
            ax = axes[1, col]
            sc = ax.scatter(xdata, board_mm, c=marker_colors, label="Refractive", **scatter_kw)
            if ph is not None:
                ax.scatter(xdata[ph["idx"]], ph["board_mm"], marker="s", s=34, zorder=4,
                           facecolors="none", edgecolors=COLORS["coral"], linewidths=1.1,
                           label="Pinhole (re-fitted)")
            ax.axhline(board_nominal, color=COLORS["indigo"], linewidth=1.2,
                       linestyle=":", label=f"Nominal {board_nominal:.0f} mm")
            ax.axhline(board_mean, color=COLORS["olive"], linewidth=1.2,
                       linestyle="--", label=f"Refractive mean {board_mean:.3f} mm")
            ax.set_xlabel(xlabel)
            if col == 0:
                ax.set_ylabel("Board size [mm]")
            ax.set_title(f"Board size vs {xlabel.split('[')[0].strip()}")

        # One legend for the whole figure, below the panels (in-panel legends collided
        # with points). The refractive marker is a neutral proxy: its points are
        # coloured by tilt, so the first point's colour would mislabel the series.
        from matplotlib.lines import Line2D
        handles = [Line2D([], [], marker="o", linestyle="none", markersize=7,
                          markerfacecolor=COLORS["dark gray"], markeredgecolor="none",
                          label="Refractive (colour = tilt)")]
        for row in (0, 1):
            for h, lab in zip(*axes[row, 0].get_legend_handles_labels()):
                if lab not in ("Refractive",) and lab not in [x.get_label() for x in handles]:
                    handles.append(h)
        # Reserve a strip at the bottom of the layout for the legend.
        fig.get_layout_engine().set(rect=(0.0, 0.05, 1.0, 0.95))
        fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.0),
                   ncol=len(handles), fontsize=8)

        # Shared colorbar for tilt
        sm = plt.cm.ScalarMappable(
            cmap=cmap,
            norm=plt.Normalize(vmin=tilt_deg.min(), vmax=tilt_deg.max())
        )
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=axes[:, 2], shrink=0.8, pad=0.02)
        cbar.set_label("Tilt angle [deg]")

        return save_figure(
            fig, name,
            output_dir=out if out is not None else FIGURES_DIR,
            formats=("svg", "pdf", "png")
        )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--root", type=Path, default=None, help="analysis-output root (default: module default)")
    ap.add_argument("--pinhole", type=Path, default=None, help="pinhole-ablation analysis-output root to overlay")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--name", default="spatial_consistency")
    args = ap.parse_args()
    for p in render(args.root, args.pinhole, args.out, args.name):
        print(f"Saved: {p}")


if __name__ == "__main__":
    main()
