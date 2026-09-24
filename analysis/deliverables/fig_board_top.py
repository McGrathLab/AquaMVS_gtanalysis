"""
Board top-down renders (manuscript Fig. 3, panels a-d).

Four held-out board poses rendered top-down from the reconstructed surface mesh, one
file per panel (panel letters are set in LaTeX). Direction and orientation follow
AquaMVS's canonical "top" view (looking straight down, world +Y up in the image);
each camera is centred on its board with a narrow field of view, so every panel has
the same, nearly orthographic scale. Each panel carries a scale bar (valid at the
board centroid's depth) and a world-axis triad (R2.5).

Frame choice (default): the four frames with the highest total board coverage by the
mesh, all at distinct poses ("unique positions"): two frames count as the same pose when
their board centroids are closer than --min-sep (0.15 m) AND their tilts differ by less
than --min-tilt (10 deg); a board re-placed at the same spot but tilted is a new pose.
Coverage = fraction of a 5 mm sample grid over the full 12 x 9-square board, placed by
an affine fit of board coordinates to the frame's direct-depth corners, that has a mesh
vertex within 3 mm. Pass --frames to override.

Run:
    python -m analysis.deliverables.fig_board_top \\
        --run data/runs/modern_refractive --analysis data/analysis_output.modern_refractive \\
        [--frames 8 6 3 1] [--min-sep 0.15] [--min-tilt 10] [--out DIR] [--name aquamvs_gt_board_top]
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless backend

import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import cKDTree

from analysis.deliverables._artifacts import FIGURES_DIR, load_flatness
from analysis.deliverables._render3d import (camera_looking, draw_scale_bar, draw_triad,
                                             load_mesh, render)
from analysis.deliverables._style import dissertation_style, save_figure

SQUARE_M = 0.06
INNER_X, INNER_Y = 11, 8          # inner corners of the 12 x 9-square ChArUco board
FIELD_M = 1.15                     # field of view at the board, per panel
DISTANCE_M = 3.0                   # camera distance: fov ~19 deg, nearly orthographic
RENDER_PX = 1600
PANEL_IN = 3.3


def board_coverage(run: Path, analysis: Path, frame: int, tol_m: float = 0.003) -> float:
    z = np.load(analysis / "corner_transfer" / "corners.npz", allow_pickle=True)
    m = (z["frame_idx"] == frame) & (z["method"] == "direct")
    ids, pts = z["corner_id"][m], z["points"][m].astype(float)
    uid = np.unique(ids)
    world = np.array([pts[ids == u].mean(0) for u in uid])
    board = np.stack([uid % INNER_X, uid // INNER_X], 1) * SQUARE_M
    affine, *_ = np.linalg.lstsq(np.c_[board, np.ones(len(board))], world, rcond=None)
    gu, gv = np.meshgrid(np.arange(-SQUARE_M, INNER_X * SQUARE_M + 1e-9, 0.005),
                         np.arange(-SQUARE_M, INNER_Y * SQUARE_M + 1e-9, 0.005))
    grid = np.c_[gu.ravel(), gv.ravel(), np.ones(gu.size)] @ affine
    verts = np.asarray(load_mesh(_mesh_path(run, frame)).vertices)
    d, _ = cKDTree(verts).query(grid, distance_upper_bound=2 * tol_m)
    return float(np.mean(d < tol_m))


def _mesh_path(run: Path, frame: int) -> Path:
    return run / "output" / f"frame_{frame:06d}" / "mesh" / "surface.ply"


def choose_frames(cov: dict[int, float], centroid: dict[int, np.ndarray], tilt: dict[int, float],
                  n: int = 4, min_sep: float = 0.15, min_tilt: float = 10.0) -> tuple[int, ...]:
    def distinct(a: int, b: int) -> bool:
        return (np.linalg.norm(centroid[a] - centroid[b]) >= min_sep
                or abs(tilt[a] - tilt[b]) >= min_tilt)
    ok = [s for s in itertools.combinations(sorted(cov), n)
          if all(distinct(a, b) for a, b in itertools.combinations(s, 2))]
    if not ok:
        raise SystemExit(f"no {n} mutually distinct poses; lower --min-sep / --min-tilt")
    return max(ok, key=lambda s: sum(cov[f] for f in s))


def render_panel(run: Path, frame: int, centroid: np.ndarray, out: Path, name: str) -> list[Path]:
    mesh = load_mesh(_mesh_path(run, frame))
    fov = float(np.degrees(2 * np.arctan(FIELD_M / 2 / DISTANCE_M)))
    cam = camera_looking(centroid, direction=[0, 0, 1], up=[0, 1, 0], distance=DISTANCE_M,
                         width=RENDER_PX, height=RENDER_PX, fov_deg=fov)
    img = render([mesh], cam)
    with dissertation_style():
        fig, ax = plt.subplots(figsize=(PANEL_IN, PANEL_IN))
        ax.imshow(img, interpolation="lanczos")
        ax.set_xlim(0, RENDER_PX)
        ax.set_ylim(RENDER_PX, 0)
        ax.set_axis_off()
        draw_scale_bar(ax, cam, centroid, 100.0, color="white")
        triad_at = cam.unproject((0.86 * RENDER_PX, 0.86 * RENDER_PX), centroid)
        draw_triad(ax, cam, triad_at, length_m=0.10)
        fig.subplots_adjust(0, 0, 1, 1)
        return save_figure(fig, name, output_dir=out, formats=("pdf", "png"), pad_inches=0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--run", type=Path, required=True, help="run dir with output/frame_*/mesh")
    ap.add_argument("--analysis", type=Path, required=True, help="that run's analysis-output root")
    ap.add_argument("--frames", type=int, nargs=4, default=None)
    ap.add_argument("--min-sep", type=float, default=0.15, help="same-pose centroid distance (m)")
    ap.add_argument("--min-tilt", type=float, default=10.0, help="same-pose tilt difference (deg)")
    ap.add_argument("--out", type=Path, default=FIGURES_DIR)
    ap.add_argument("--name", default="aquamvs_gt_board_top")
    args = ap.parse_args()

    per_frame = {f["frame_idx"]: f for f in load_flatness(args.analysis)["per_frame"]}
    centroid = {i: np.asarray(f["centroid_xyz_m"]) for i, f in per_frame.items()}
    cov = {i: board_coverage(args.run, args.analysis, i) for i in per_frame}
    tilt = {i: f["tilt_deg"] for i, f in per_frame.items()}
    frames = args.frames or choose_frames(cov, centroid, tilt, min_sep=args.min_sep,
                                          min_tilt=args.min_tilt)
    frames = sorted(frames, key=lambda i: per_frame[i]["tilt_deg"])

    manifest = []
    for letter, fr in zip("abcd", frames):
        for p in render_panel(args.run, fr, centroid[fr], args.out, f"{args.name}_{letter}"):
            print(f"Saved: {p}")
        manifest.append({"panel": letter, "frame_idx": fr,
                         "tilt_deg": round(per_frame[fr]["tilt_deg"], 1),
                         "depth_m": round(abs(per_frame[fr]["depth_m"]), 3),
                         "board_coverage": round(cov[fr], 3)})
    (args.out / f"{args.name}.json").write_text(json.dumps(
        {"rule": None if args.frames else (f"max total coverage over distinct poses (centroids >= "
                                           f"{args.min_sep} m apart or tilts >= {args.min_tilt} deg apart)"),
         "coverage_all_frames": {str(k): round(v, 3) for k, v in sorted(cov.items())},
         "panels": manifest}, indent=2))
    for m in manifest:
        print(m)


if __name__ == "__main__":
    main()
