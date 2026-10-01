"""
Temporal repeatability of the fish-present sequence (manuscript Fig. S1).

Port of DissertationFigures figures/aquamvs/real.py::plot_temporal_repeatability, on the
paper's own height-map procedure as already ported in scripts/temporal_coverage.py
(per-cell mean of the fused points on a 2 mm grid spanning frame 0; sand ROI = central
50 % x 50 % of the grid gated to within 3 sigma in Z of frame 0's median; cells are
compared only where both frames are valid, never interpolated).

Panels:
  (A) empirical CDF of |dh| over the sand ROI for the four consecutive pairs;
  (B) the first pair's signed dh map, with the sand ROI's central crop outlined;
  (C) mean signed dh per pair over the sand ROI, +/- 2 block SE (4 x 4 blocks; the
      per-cell SE overstates precision because neighbouring cells are correlated).

Sign convention: dh is the change in surface HEIGHT, positive up. The world frame has
+Z pointing down (cameras at z ~ 0, sand at z ~ +1.5 m), so dh = -(Z_later - Z_earlier);
the DissertationFigures original plotted dz = Z_later - Z_earlier.

Run:
    python -m analysis.deliverables.fig_temporal_repeatability \\
        --run data/runs_fish/modern_run5_filtered [--out DIR] [--name NAME]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless backend

import matplotlib.pyplot as plt
import numpy as np

from analysis.deliverables._artifacts import FIGURES_DIR
from analysis.deliverables._style import (CMAP_DIV, COLORS, DOUBLE_COL, dissertation_style,
                                          save_figure)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import temporal_coverage as tc  # noqa: E402

GRID_RES = 0.002
PAIR_COLORS = [COLORS["blue"], COLORS["teal"], COLORS["gold"], COLORS["coral"]]


def height_change_maps(run: Path):
    """Four consecutive dh maps (mm, positive = surface rose), the sand ROI, and the grid."""
    frames = tc._load_points(run, "cloud")
    maps, gx, gy = tc._height_maps_binned(frames, GRID_RES)
    names = [n for n, _ in frames]
    sand = tc._paper_sand_mask(maps[names[0]])
    dh = [-(maps[b] - maps[a]) * 1000.0 for a, b in zip(names, names[1:])]
    return dh, sand, gx, gy, names


def render(run: Path, out: Path, name: str) -> list[Path]:
    dh, sand, gx, gy, names = height_change_maps(run)
    labels = [rf"F{i} $\rightarrow$ F{i + 1}" for i in range(len(dh))]
    sand_vals = np.concatenate([d[sand & np.isfinite(d)] for d in dh])
    vmax = float(np.percentile(np.abs(sand_vals), 99))

    with dissertation_style():
        fig, (ax_cdf, ax_map, ax_drift) = plt.subplots(
            1, 3, figsize=(DOUBLE_COL, 2.9), constrained_layout=True,
            gridspec_kw={"width_ratios": [1.0, 1.15, 0.7]},
        )

        # (A) CDF of |dh| over the sand ROI
        for d, color, label in zip(dh, PAIR_COLORS, labels):
            a = np.sort(np.abs(d[sand & np.isfinite(d)]))
            if len(a) > 10_000:
                a = a[np.linspace(0, len(a) - 1, 10_000, dtype=int)]
            ax_cdf.plot(a, np.arange(1, len(a) + 1) / len(a), color=color, linewidth=1.2, label=label)
        for ref in (0.5, 1.0):
            ax_cdf.axvline(ref, color="#AAAAAA", linewidth=0.6, linestyle=":", zorder=0)
            ax_cdf.text(ref, 1.01, f"{ref:.1f}", fontsize=7, color="#888888", ha="center", va="bottom")
        ax_cdf.set_xlim(0, vmax * 1.1)
        ax_cdf.set_ylim(0, 1)
        ax_cdf.set_xlabel(r"$|\Delta h|$ (mm)")
        ax_cdf.set_ylabel("Cumulative fraction")
        ax_cdf.legend(loc="lower right", fontsize=7)
        ax_cdf.set_title(r"\textbf{(A)}", loc="left")

        # (B) representative signed map
        extent = [float(gx[0]), float(gx[-1]), float(gy[-1]), float(gy[0])]
        im = ax_map.imshow(np.ma.masked_invalid(dh[0]), cmap=CMAP_DIV, vmin=-vmax, vmax=vmax,
                           extent=extent, origin="upper", aspect="equal")
        ax_map.set_xlabel("X (m)")
        ax_map.set_ylabel("Y (m)")
        ax_map.set_title(r"\textbf{(B)}\quad " + labels[0], loc="left")
        ax_map.text(0.02, 0.04, f"min: {np.nanmin(dh[0]):+.0f} mm\nmax: {np.nanmax(dh[0]):+.0f} mm",
                    transform=ax_map.transAxes, fontsize=7, va="bottom", ha="left",
                    bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="none", alpha=0.8))
        ny, nx = sand.shape
        x0, x1 = gx[int(nx * 0.25)], gx[int(nx * 0.75)]
        y0, y1 = gy[int(ny * 0.25)], gy[int(ny * 0.75)]
        ax_map.plot([x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0], color="black",
                    linewidth=0.7, linestyle="--")
        cbar = fig.colorbar(im, ax=ax_map, fraction=0.046, pad=0.04)
        cbar.set_label(r"$\Delta h$ (mm)")

        # (C) signed drift per pair
        means = [float(d[sand & np.isfinite(d)].mean()) for d in dh]
        ses = [tc._block_se(d, sand & np.isfinite(d)) for d in dh]
        x = np.arange(len(dh))
        ax_drift.axhline(0, color="#AAAAAA", linewidth=0.6, linestyle=":", zorder=0)
        for i in x:
            ax_drift.errorbar(i, means[i], yerr=2 * ses[i], color=PAIR_COLORS[i], marker="o",
                              markersize=4, capsize=2, linewidth=1.0)
        ax_drift.set_xticks(x, [f"{i}--{i + 1}" for i in x], fontsize=7)
        ax_drift.set_xlabel("Frame pair")
        ax_drift.set_xlim(-0.5, len(dh) - 0.5)
        ax_drift.set_ylim(bottom=min(0.0, min(means) - 0.1), top=max(0.0, max(means)) * 1.15 + 0.02)
        ax_drift.set_ylabel(r"Mean $\Delta h$ over sand (mm)")
        ax_drift.set_title(r"\textbf{(C)}", loc="left")

        paths = save_figure(fig, name, output_dir=out)

    for lab, m, s in zip(labels, means, ses):
        print(f"{lab}: mean dh {m:+.3f} mm (block SE {s:.4f})")
    return paths


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--run", type=Path, required=True, help="run dir with output/frame_*/point_cloud")
    ap.add_argument("--out", type=Path, default=FIGURES_DIR)
    ap.add_argument("--name", default="aquamvs_real_temporal_repeatability")
    args = ap.parse_args()
    for p in render(args.run, args.out, args.name):
        print(f"Saved: {p}")


if __name__ == "__main__":
    main()
