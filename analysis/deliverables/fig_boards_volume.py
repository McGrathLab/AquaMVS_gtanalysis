"""
Boards-in-the-working-volume figure (spatial-consistency story, made physical).

Renders the 8 held-out board poses at their reconstructed positions and tilts
inside the camera working volume, each board quad colored by its flatness RMS.
One glance shows BOTH the spatial/angular coverage (a strength) AND that accuracy
is uniform wherever the board went. Camera centres are drawn for context.

Run:
    python -m analysis.deliverables.fig_boards_volume
"""

import matplotlib
matplotlib.use("Agg")  # headless backend

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from analysis.deliverables._style import dissertation_style, COLORS, save_figure
from analysis.deliverables._artifacts import load_flatness, FIGURES_DIR
from analysis._paths import data_root
from analysis.loader import GroundTruthDataset, DatasetConfig

BOARD_W, BOARD_H = 0.72, 0.54  # full ChArUco board extent (12x9 x 60 mm), metres


def _board_quad(centroid, normal, w=BOARD_W, h=BOARD_H):
    """Return the 4 corners of a board rectangle at `centroid` with given `normal`."""
    n = np.asarray(normal, float); n /= max(np.linalg.norm(n), 1e-12)
    ref = np.array([0.0, 0.0, 1.0]) if abs(n[2]) < 0.95 else np.array([1.0, 0.0, 0.0])
    u = np.cross(ref, n); u /= max(np.linalg.norm(u), 1e-12)
    v = np.cross(n, u)
    c = np.asarray(centroid, float)
    return np.array([
        c + (w/2)*u + (h/2)*v, c - (w/2)*u + (h/2)*v,
        c - (w/2)*u - (h/2)*v, c + (w/2)*u - (h/2)*v,
    ])


def _camera_centres(ds):
    centres = []
    calib = ds.calibration()
    for name, cam in calib.cameras.items():
        R = np.asarray(cam.R.detach().cpu() if hasattr(cam.R, "detach") else cam.R, float).reshape(3, 3)
        t = np.asarray(cam.t.detach().cpu() if hasattr(cam.t, "detach") else cam.t, float).ravel()
        centres.append(-R.T @ t)
    return np.array(centres)


def main() -> None:
    frames = [f for f in load_flatness()["per_frame"] if f.get("flatness_rms_mm")]
    flat = np.array([f["flatness_rms_mm"] for f in frames])

    cmap = cm.get_cmap("cividis")
    norm = plt.Normalize(vmin=flat.min(), vmax=flat.max())

    ds = GroundTruthDataset(DatasetConfig(data_root=data_root()))
    cams = _camera_centres(ds)

    with dissertation_style():
        fig = plt.figure(figsize=(7.0, 5.8))
        ax = fig.add_subplot(111, projection="3d")

        # Boards drawn as colored OUTLINES (with a faint fill) so overlapping
        # poses stay distinguishable; colour encodes flatness RMS.
        for f in frames:
            quad = _board_quad(f["centroid_xyz_m"], f["plane_normal"])
            col = cmap(norm(f["flatness_rms_mm"]))
            poly = Poly3DCollection([quad], alpha=0.12)
            poly.set_facecolor(col)
            poly.set_edgecolor(col); poly.set_linewidth(2.2)
            ax.add_collection3d(poly)
            c = np.asarray(f["centroid_xyz_m"], float)
            ax.text(c[0], c[1], c[2], f" {f['frame_idx']}", fontsize=6,
                    color=COLORS["dark gray"])

        ax.scatter(cams[:, 0], cams[:, 1], cams[:, 2], marker="^", s=28,
                   color=COLORS["coral"], depthshade=False, label="cameras")

        ax.set_xlabel("X [m]"); ax.set_ylabel("Y [m]"); ax.set_zlabel("Z [m]")
        ax.set_title("Reconstructed Board Poses in the Working Volume\n"
                     f"(colour = flatness RMS, {flat.min():.2f}-{flat.max():.2f} mm and "
                     "uniform; poses vary in tilt above the camera array)")
        ax.view_init(elev=18, azim=-60)
        try:
            ax.set_box_aspect((1, 1, 0.6))
        except Exception:
            pass
        ax.legend(loc="upper right", fontsize=7)

        sm = cm.ScalarMappable(cmap=cmap, norm=norm); sm.set_array([])
        cbar = fig.colorbar(sm, ax=ax, shrink=0.6, pad=0.10)
        cbar.set_label("Flatness RMS [mm]")

        paths = save_figure(fig, "boards_in_volume",
                            output_dir=FIGURES_DIR, formats=("svg", "pdf", "png"))
        for p in paths:
            print(f"Saved: {p}")
    print(f"[fig_boards_volume] {len(frames)} boards; flatness "
          f"{flat.min():.2f}-{flat.max():.2f} mm; {len(cams)} cameras")


if __name__ == "__main__":
    main()
