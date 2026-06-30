"""
Per-corner accuracy heatmap on a representative reconstructed board (MET-05).

Takes the board frame with the best corner coverage, rigidly aligns its
consensus corners to the ideal 60 mm board (no scale), and plots each corner at
its grid position colored by its 3-D residual from the ideal. A concrete "here is
an actual reconstructed board, here is how accurate it is across its face" figure
that complements the aggregate metrics.

Run:
    python -m analysis.deliverables.fig_board_heatmap
"""

import matplotlib
matplotlib.use("Agg")  # headless backend

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm

from analysis.deliverables._style import dissertation_style, COLORS, save_figure
from analysis.deliverables._artifacts import ANALYSIS_OUTPUT, FIGURES_DIR
from analysis.loader import GroundTruthDataset, DatasetConfig
from analysis.charuco_detect import build_board_geometry
from analysis.cross_camera import load_corners
from analysis.alignment import (
    build_consensus_corners, ideal_board_corners, matched_arrays, rigid_inlier_fit,
)

DATA_ROOT = "data/aquamvs_ground_truth_analysis"
CORNERS = str(ANALYSIS_OUTPUT / "corner_transfer" / "corners.npz")


def main() -> None:
    corners = load_corners(CORNERS)
    fi, cam, cid = corners["frame_idx"], corners["camera_id"], corners["corner_id"]
    pts = corners["points"].astype(np.float64)

    ds = GroundTruthDataset(DatasetConfig(data_root=DATA_ROOT))
    spec = ds.board_spec()
    n_cols = spec.squares_x - 1                  # internal-corner grid width (11)
    ideal_all = ideal_board_corners(build_board_geometry(spec))

    # Pick the frame with the most consensus corners (best coverage).
    best = None
    for frame in sorted(set(int(f) for f in fi)):
        cons = build_consensus_corners(fi, cam, cid, pts, frame)
        if best is None or len(cons) > len(best[1]):
            best = (frame, cons)
    frame, consensus = best

    ids, src_ideal, dst = matched_arrays(consensus, ideal_all)
    fit = rigid_inlier_fit(src_ideal, dst)
    R, t = fit["R"], fit["t"]
    res = dst - ((R @ src_ideal.T).T + t)         # (N,3) world-frame residuals
    res_mm = np.linalg.norm(res, axis=1) * 1000.0

    cols = ids % n_cols
    rows = ids // n_cols

    # Colour scale spans the INLIER range so the sub-mm bulk structure is visible;
    # a few gross-outlier corners are flagged separately rather than saturating it.
    inl = fit["inlier_mask"]
    vmax = float(np.ceil(res_mm[inl].max() * 2) / 2) if inl.any() else float(res_mm.max())
    outlier = res_mm > vmax
    n_out = int(outlier.sum())

    with dissertation_style():
        fig, ax = plt.subplots(figsize=(6.6, 4.8))
        sc = ax.scatter(cols, rows, c=res_mm, cmap="cividis", s=150,
                        marker="s", vmin=0.0, vmax=vmax,
                        edgecolors=COLORS["dark gray"], linewidths=0.4)
        if n_out:
            ax.scatter(cols[outlier], rows[outlier], s=150, marker="s",
                       facecolors="none", edgecolors=COLORS["coral"], linewidths=1.8)
            ax.text(0.99, 1.01, f"coral outline: outlier $>${vmax:.1f} mm ({n_out})",
                    transform=ax.transAxes, ha="right", va="bottom",
                    fontsize=7, color=COLORS["coral"])
        ax.set_aspect("equal")
        ax.set_xlabel("Board corner column")
        ax.set_ylabel("Board corner row")
        ax.set_xticks(range(int(cols.min()), int(cols.max()) + 1))
        ax.set_yticks(range(int(rows.min()), int(rows.max()) + 1))
        ax.set_title(
            f"Per-Corner Accuracy on a Reconstructed Board (frame {frame})\n"
            f"rigid-aligned to the ideal 60 mm board; "
            f"RMS {fit['rms_mm']:.2f} mm over {fit['n_inliers']} inlier corners"
        )
        cbar = fig.colorbar(sc, ax=ax, shrink=0.85, pad=0.03, extend="max")
        cbar.set_label("Corner residual from ideal [mm]")
        fig.tight_layout()

        paths = save_figure(fig, "board_accuracy_heatmap",
                            output_dir=FIGURES_DIR, formats=("svg", "pdf", "png"))
        for p in paths:
            print(f"Saved: {p}")
    print(f"[fig_board_heatmap] frame {frame}: {len(ids)} corners, "
          f"residual {res_mm.min():.2f}-{res_mm.max():.2f} mm")


if __name__ == "__main__":
    main()
