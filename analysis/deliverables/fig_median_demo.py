"""
What the temporal median removes (supplementary figure for R1.5 / R1.6).

One camera, one frame (session 021826, frame 1799):
  (A) the raw frame, with fish;
  (B) the trailing 1800-frame (60 s) temporal-median frame the pipeline reconstructs;
  (C) the reconstructed surface-height difference, raw minus median, over the tank
      (dh positive up; paper's 2 mm binning on the median cloud's grid, as in
      scripts/median_comparison.py).
(A) and (B) are cropped to the same window around the largest changed region, and the
window's footprint is not marked in (C): the image is a perspective view, (C) is plan.

Camera choice (default): the one whose raw and median frames differ in the largest
connected region (per-pixel max channel difference > 40 grey levels, inside its mask).

Run:
    python -m analysis.deliverables.fig_median_demo \\
        --raw-run data/runs_fish/modern_run3_raw --median-run data/runs_fish/modern_run5_filtered \\
        [--frame frame_001799] [--camera e3v831e] [--out DIR] [--name NAME]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless backend

import cv2
import matplotlib.pyplot as plt
import numpy as np
import open3d as o3d

from analysis.deliverables._artifacts import FIGURES_DIR
from analysis.deliverables._style import CMAP_DIV, DOUBLE_COL, dissertation_style, save_figure

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import temporal_coverage as tc  # noqa: E402

DIFF_GREY = 40
CROP_W, CROP_H = 640, 480


def _images(raw_run: Path, med_run: Path, cam: str, frame: str):
    raw = cv2.cvtColor(cv2.imread(str(raw_run / "frames" / cam / f"{frame}.png")), cv2.COLOR_BGR2RGB)
    med = cv2.cvtColor(cv2.imread(str(med_run / "frames" / cam / f"{frame}.png")), cv2.COLOR_BGR2RGB)
    mask_p = med_run / "masks" / f"{cam}.png"
    mask = cv2.imread(str(mask_p), 0) > 0 if mask_p.exists() else np.ones(raw.shape[:2], bool)
    return raw, med, mask


def _largest_change(raw, med, mask):
    changed = (np.abs(raw.astype(np.int16) - med.astype(np.int16)).max(2) > DIFF_GREY) & mask
    n, _, stats, cents = cv2.connectedComponentsWithStats(changed.astype(np.uint8))
    if n < 2:
        return 0, (raw.shape[1] / 2, raw.shape[0] / 2)
    k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return int(stats[k, cv2.CC_STAT_AREA]), tuple(cents[k])


def pick_camera(raw_run: Path, med_run: Path, frame: str) -> str:
    cams = sorted(p.name for p in (raw_run / "frames").iterdir() if p.is_dir())
    return max(cams, key=lambda c: _largest_change(*_images(raw_run, med_run, c, frame))[0])


def height_difference(raw_run: Path, med_run: Path, frame_dir: str):
    """dh = raw minus median surface height (mm, positive up) on the median cloud's grid."""
    clouds = [(n, np.asarray(o3d.io.read_point_cloud(
        str(r / "output" / frame_dir / "point_cloud" / "fused.ply")).points))
        for n, r in (("median", med_run), ("raw", raw_run))]
    maps, gx, gy = tc._height_maps_binned(clouds, 0.002)
    return -(maps["raw"] - maps["median"]) * 1000.0, gx, gy


def render(raw_run: Path, med_run: Path, frame: str, cam: str | None, out: Path, name: str) -> list[Path]:
    cam = cam or pick_camera(raw_run, med_run, frame)
    raw, med, mask = _images(raw_run, med_run, cam, frame)
    area, (cx, cy) = _largest_change(raw, med, mask)
    h, w = raw.shape[:2]
    x0 = int(np.clip(cx - CROP_W / 2, 0, w - CROP_W))
    y0 = int(np.clip(cy - CROP_H / 2, 0, h - CROP_H))
    dh, gx, gy = height_difference(raw_run, med_run, "frame_000000")
    lim = 10.0

    with dissertation_style():
        fig, axes = plt.subplots(1, 3, figsize=(DOUBLE_COL, 2.35), constrained_layout=True,
                                 gridspec_kw={"width_ratios": [1, 1, 1.05]})
        for ax, img, tag, title in ((axes[0], raw, "(A)", "Raw frame"),
                                    (axes[1], med, "(B)", "Temporal median")):
            ax.imshow(img[y0:y0 + CROP_H, x0:x0 + CROP_W])
            ax.set_axis_off()
            ax.set_title(rf"\textbf{{{tag}}}\quad {title}", loc="left")
        extent = [float(gx[0]), float(gx[-1]), float(gy[-1]), float(gy[0])]
        im = axes[2].imshow(np.ma.masked_invalid(dh), cmap=CMAP_DIV, vmin=-lim, vmax=lim,
                            extent=extent, origin="upper", aspect="equal")
        axes[2].set_xlabel("X (m)")
        axes[2].set_ylabel("Y (m)")
        axes[2].set_title(r"\textbf{(C)}\quad Raw $-$ median", loc="left")
        cbar = fig.colorbar(im, ax=axes[2], fraction=0.046, pad=0.04)
        cbar.set_label(r"$\Delta h$ (mm)")
        paths = save_figure(fig, name, output_dir=out)
    print(f"camera {cam}, frame {frame}, crop x{x0} y{y0} {CROP_W}x{CROP_H}, largest change {area} px")
    return paths


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--raw-run", type=Path, required=True)
    ap.add_argument("--median-run", type=Path, required=True)
    ap.add_argument("--frame", default="frame_001799", help="source frame name of both runs' frame 0")
    ap.add_argument("--camera", default=None)
    ap.add_argument("--out", type=Path, default=FIGURES_DIR)
    ap.add_argument("--name", default="aquamvs_real_median_demo")
    args = ap.parse_args()
    for p in render(args.raw_run, args.median_run, args.frame, args.camera, args.out, args.name):
        print(f"Saved: {p}")


if __name__ == "__main__":
    main()
