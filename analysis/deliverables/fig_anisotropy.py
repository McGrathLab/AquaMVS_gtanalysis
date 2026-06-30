"""
Error-anisotropy figure (MET-06, refraction signature) — the "money figure".

Instead of bar magnitudes, this shows the residual structure geometrically: each
per-camera corner offset from the cross-camera consensus is expressed in its own
viewing-ray frame (range = along the in-water cast_ray; lateral = perpendicular).
Pooling all observations, the residual cloud is strongly elongated ALONG the line
of sight and tight across it — the 1-sigma covariance ellipse's elongation IS the
range-dominance ratio (~4.41x). That makes the refraction signature self-evident:
errors smear along the camera's line of sight, not laterally.

Honest construction: each observation contributes its (lat_u, range) and
(lat_v, range) components (both perpendicular axes vs range), giving a
lateral-symmetric cloud. Marginal histograms show the range vs lateral spread.

Run:
    python -m analysis.deliverables.fig_anisotropy
"""

import matplotlib
matplotlib.use("Agg")  # headless backend

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse

from analysis.deliverables._style import dissertation_style, COLORS, save_figure
from analysis.deliverables._artifacts import (
    load_error_decomp, ANALYSIS_OUTPUT, FIGURES_DIR,
)

# Compute helpers (same code path as the MET-06 metric — no drift)
from analysis.loader import GroundTruthDataset, DatasetConfig
from analysis.charuco_detect import build_board_geometry
from analysis.cross_camera import load_corners
from analysis.projection import build_projection_models
from analysis.error_decomposition import local_frame_components
from analysis.compute_error_decomposition import frame_cross_camera_samples

DATA_ROOT = "data/aquamvs_ground_truth_analysis"
CORNERS = str(ANALYSIS_OUTPUT / "corner_transfer" / "corners.npz")


def _collect_components():
    """Pool (lateral, range) signed components across all frames, in mm."""
    corners = load_corners(CORNERS)
    fi, cam, cid = corners["frame_idx"], corners["camera_id"], corners["corner_id"]
    pts, pix = corners["points"].astype(np.float64), corners["pixels"].astype(np.float64)

    ds = GroundTruthDataset(DatasetConfig(data_root=DATA_ROOT))
    models = build_projection_models(ds.calibration(), sorted(set(str(c) for c in cam)))

    lat, rng = [], []
    for frame in sorted(set(int(f) for f in fi)):
        res, rays = frame_cross_camera_samples(fi, cam, cid, pts, pix, models, frame)
        if len(res) == 0:
            continue
        comp = local_frame_components(res, rays)
        # each obs contributes both perpendicular axes vs range -> symmetric lateral
        lat.extend(comp["lat_u_mm"].tolist()); rng.extend(comp["range_mm"].tolist())
        lat.extend(comp["lat_v_mm"].tolist()); rng.extend(comp["range_mm"].tolist())
    return np.array(lat), np.array(rng)


def _cov_ellipse(x, y, ax, n_std=1.0, **kw):
    """Draw an n_std covariance ellipse for the (x, y) cloud."""
    cov = np.cov(x, y)
    vals, vecs = np.linalg.eigh(cov)
    order = vals.argsort()[::-1]
    vals, vecs = vals[order], vecs[:, order]
    theta = np.degrees(np.arctan2(vecs[1, 0], vecs[0, 0]))
    w, h = 2 * n_std * np.sqrt(vals)
    e = Ellipse((np.mean(x), np.mean(y)), w, h, angle=theta, **kw)
    ax.add_patch(e)
    return np.sqrt(vals[0] / vals[1])  # major/minor std ratio


def main() -> None:
    lat, rng = _collect_components()
    pooled = load_error_decomp()["pooled"]["range_lateral"]
    dominance = pooled["range_dominance"]
    range_rms, lateral_rms = pooled["range_rms_mm"], pooled["lateral_rms_mm"]

    # Zoom to the core (equal aspect preserved so anisotropy stays honest). A heavy
    # range tail of a few cm-scale corners is part of the story but would otherwise
    # blow out the scale; crop it on the main axes and note the count.
    lim = float(np.ceil(4.5 * np.std(rng)))                 # ~core extent along range
    n_crop = int(np.sum((np.abs(lat) > lim) | (np.abs(rng) > lim)))

    with dissertation_style():
        fig = plt.figure(figsize=(6.2, 5.6))
        gs = fig.add_gridspec(
            2, 2, width_ratios=(4, 1), height_ratios=(1, 4),
            wspace=0.04, hspace=0.04,
        )
        ax = fig.add_subplot(gs[1, 0])
        ax_top = fig.add_subplot(gs[0, 0], sharex=ax)
        ax_right = fig.add_subplot(gs[1, 1], sharey=ax)

        # central scatter (core only) + 2-sigma covariance ellipse (full data).
        # Colour convention shared with the range-vs-lateral figure: range = blue,
        # lateral = gold (used on the marginals below). The scatter cloud is a
        # neutral third colour so the directional marginals carry the encoding.
        core = (np.abs(lat) <= lim) & (np.abs(rng) <= lim)
        ax.scatter(lat[core], rng[core], s=7, alpha=0.30, color=COLORS["teal"],
                   edgecolors="none", zorder=3, rasterized=True)
        ratio = _cov_ellipse(lat, rng, ax, n_std=2.0, facecolor="none",
                             edgecolor=COLORS["coral"], lw=1.8, zorder=5)
        ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim)
        ax.set_aspect("equal")
        ax.axhline(0, color=COLORS["dark gray"], lw=0.5, zorder=1)
        ax.axvline(0, color=COLORS["dark gray"], lw=0.5, zorder=1)
        ax.set_xlabel("Lateral offset [mm]  (perpendicular to viewing ray)")
        ax.set_ylabel("Range offset [mm]  (along viewing ray)")

        # marginals over the FULL distribution (tail visible here).
        # lateral marginal (top) = gold; range marginal (right) = blue.
        bins = np.linspace(-lim, lim, 50)
        ax_top.hist(np.clip(lat, -lim, lim), bins=bins, color=COLORS["gold"])
        ax_right.hist(np.clip(rng, -lim, lim), bins=bins, orientation="horizontal",
                      color=COLORS["blue"])
        for a in (ax_top, ax_right):
            a.axis("off")

        if n_crop:
            ax.text(0.97, 0.02, f"+{n_crop} obs beyond axis (range tail)",
                    transform=ax.transAxes, ha="right", va="bottom",
                    fontsize=6.5, color=COLORS["dark gray"])

        ax_top.set_title("Cross-Camera Corner Offsets in the Viewing-Ray Frame", pad=8)
        paths = save_figure(fig, "error_anisotropy",
                            output_dir=FIGURES_DIR, formats=("svg", "pdf", "png"))
        for p in paths:
            print(f"Saved: {p}")
    print(f"[fig_anisotropy] ellipse std ratio (major/minor) = {ratio:.2f}; "
          f"artifact dominance = {dominance:.2f}; cropped tail = {n_crop}")


if __name__ == "__main__":
    main()
