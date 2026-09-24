"""
RoMa vs LightGlue surface meshes, oblique view (manuscript Fig. 2).

The two dense pathways' Poisson meshes for one fish-present temporal-median frame
(session 021826, frame 1799), each written as its own file (panel letters are set in
LaTeX). Both are rendered with ONE camera -- AquaMVS's canonical "oblique" viewpoint
(aquamvs.visualization.scene.compute_canonical_viewpoints) computed from the RoMa mesh's
bounding box -- and the same crop, so the panels are directly comparable.

Scale and coordinates (R2.5): a perspective oblique view has no single valid scale bar,
so each panel carries a world-axis triad with 20 cm arms, anchored on the sand floor
near the front of the view; its arms are the scale reference along each axis.

Run:
    python -m analysis.deliverables.fig_pathway_meshes \\
        --roma data/runs_fish/modern_run5_filtered/output/frame_000000/mesh/surface.ply \\
        --lightglue data/runs_fish/modern_lg_full/output/frame_000000/mesh/surface.ply \\
        [--out DIR] [--names roma_mesh_oblique lightglue_full_mesh_oblique]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless backend

import matplotlib.pyplot as plt
import numpy as np

from analysis.deliverables._artifacts import FIGURES_DIR
from analysis.deliverables._render3d import (canonical_camera, crop_box, draw_triad,
                                             load_mesh, render)
from analysis.deliverables._style import DOUBLE_COL, dissertation_style, save_figure

RENDER_W, RENDER_H = 2400, 1800
TRIAD_M = 0.20


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--roma", type=Path, required=True, help="RoMa surface.ply")
    ap.add_argument("--lightglue", type=Path, required=True, help="LightGlue surface.ply")
    ap.add_argument("--out", type=Path, default=FIGURES_DIR)
    ap.add_argument("--names", nargs=2, default=["roma_mesh_oblique", "lightglue_full_mesh_oblique"])
    args = ap.parse_args()

    meshes = [load_mesh(args.roma), load_mesh(args.lightglue)]
    cam = canonical_camera(meshes[0], "oblique", RENDER_W, RENDER_H)
    imgs = [render([m], cam) for m in meshes]

    # one crop for both panels: the union of their content
    boxes = np.array([crop_box(im, pad=30) for im in imgs])
    r0, c0 = boxes[:, [0, 2]].min(0)
    r1, c1 = boxes[:, [1, 3]].max(0)

    # triad on the sand floor near the front of the view: among RoMa vertices on the
    # floor (Z within 5 cm of its 95th percentile; Z points down) and inside 60 % of the
    # tank radius (off the wall), the mean of the 2000 closest to the camera
    v = np.asarray(meshes[0].vertices)
    centre_xy = np.median(v[:, :2], axis=0)
    r = np.linalg.norm(v[:, :2] - centre_xy, axis=1)
    floor = v[(v[:, 2] > np.percentile(v[:, 2], 95) - 0.05) & (r < 0.6 * np.percentile(r, 99))]
    origin = floor[np.argsort(np.linalg.norm(floor - cam.eye, axis=1))[:2000]].mean(0)

    width_in = DOUBLE_COL / 2
    for img, name in zip(imgs, args.names):
        with dissertation_style():
            h, w = r1 - r0, c1 - c0
            fig, ax = plt.subplots(figsize=(width_in, width_in * h / w))
            ax.imshow(img[r0:r1, c0:c1], extent=(c0, c1, r1, r0), interpolation="lanczos")
            ax.set_xlim(c0, c1)
            ax.set_ylim(r1, r0)
            ax.set_axis_off()
            draw_triad(ax, cam, origin, TRIAD_M, fontsize=7)
            fig.subplots_adjust(0, 0, 1, 1)
            for p in save_figure(fig, name, output_dir=args.out, formats=("pdf", "png"),
                                 pad_inches=0, dpi=600):
                print(f"Saved: {p}")


if __name__ == "__main__":
    main()
