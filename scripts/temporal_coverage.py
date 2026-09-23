"""
R2.3 temporal coverage and large-error-tail readout for the fish-present sequence.

Grids each frame's fused point cloud (or, with --source mesh, its surface
mesh vertices) into a height map exactly as AquaMVS does
for its summary gallery (aquamvs.pipeline.helpers._collect_height_maps: linear
scipy griddata of Z over XY at config.reconstruction.grid_resolution, NaN
outside the hull) -- except on ONE grid shared by all frames (the union of the
frames' XY extents), so cells correspond across frames.

For each consecutive frame pair it reports:
  - valid coverage of each frame, as a fraction of the grid
  - valid-in-both (intersection of non-NaN cells)
  - the sand-surface ROI: central 50% x 50% crop of the grid, further gated to
    cells whose Z is within 3 sigma of that frame's crop mean in BOTH frames
  - how many common cells are actually used (ROI / valid-both)
  - missing values: NaN cells are excluded, never interpolated
  - repeatability: fraction of ROI cells with |dz| <= 0.5 mm and <= 1.0 mm
  - the large-error tail: count and fraction of valid-both cells with
    |dz| > 10 mm, split into inside/outside the ROI, and their radial position
  - median and p95 |dz| outside the ROI

Usage:
    python scripts/temporal_coverage.py <run dir with config.yaml + output/> [--json out.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import open3d as o3d
import yaml
from scipy.interpolate import griddata

TAIL_MM = 10.0


def _load_points(run: Path, source: str) -> list[tuple[str, np.ndarray]]:
    """XYZ per frame: fused point cloud, or the surface mesh's vertices."""
    out = []
    for frame_dir in sorted((run / "output").glob("frame_*")):
        if source == "mesh":
            mesh = o3d.io.read_triangle_mesh(str(frame_dir / "mesh" / "surface.ply"))
            pts = np.asarray(mesh.vertices)
        else:
            pts = np.asarray(o3d.io.read_point_cloud(str(frame_dir / "point_cloud" / "fused.ply")).points)
        out.append((frame_dir.name, pts))
    return out


def _grid_resolution(run: Path) -> float:
    cfg = yaml.safe_load(open(run / "config.yaml"))
    return float((cfg.get("reconstruction") or {}).get("grid_resolution", 0.002))


def _height_maps(frames, res):
    lo = np.min([p[:, :2].min(0) for _, p in frames], axis=0)
    hi = np.max([p[:, :2].max(0) for _, p in frames], axis=0)
    gx = np.arange(lo[0], hi[0] + res, res)
    gy = np.arange(lo[1], hi[1] + res, res)
    mx, my = np.meshgrid(gx, gy)
    maps = {name: griddata(p[:, :2], p[:, 2], (mx, my), method="linear", fill_value=np.nan)
            for name, p in frames}
    return maps, gx, gy


def _height_maps_binned(frames, res):
    """Per-cell mean of Z on a grid spanning frame 0's XY extent; empty cells NaN.

    Line-for-line port of DissertationFigures figures/aquamvs/real.py
    _extract_height_maps, which produced the paper's height_maps/*.npz.
    """
    p0 = frames[0][1]
    gx = np.arange(float(p0[:, 0].min()), float(p0[:, 0].max()) + res, res, dtype=np.float32)
    gy = np.arange(float(p0[:, 1].min()), float(p0[:, 1].max()) + res, res, dtype=np.float32)
    nx, ny = len(gx), len(gy)
    maps = {}
    for name, pts in frames:
        ix = np.floor((pts[:, 0] - gx[0]) / res).astype(np.int32)
        iy = np.floor((pts[:, 1] - gy[0]) / res).astype(np.int32)
        ok = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)
        z_sum = np.zeros((ny, nx), np.float64)
        z_cnt = np.zeros((ny, nx), np.int32)
        np.add.at(z_sum, (iy[ok], ix[ok]), pts[ok, 2])
        np.add.at(z_cnt, (iy[ok], ix[ok]), 1)
        hm = np.full((ny, nx), np.nan, np.float32)
        has = z_cnt > 0
        hm[has] = (z_sum[has] / z_cnt[has]).astype(np.float32)
        maps[name] = hm
    return maps, gx, gy


def _paper_sand_mask(hmap: np.ndarray, z_sigma: float = 3.0, xy_crop: float = 0.25) -> np.ndarray:
    """Port of DissertationFigures _sand_surface_mask (applied to frame 0 only)."""
    ny, nx = hmap.shape
    x0, x1 = int(nx * xy_crop), int(nx * (1 - xy_crop))
    y0, y1 = int(ny * xy_crop), int(ny * (1 - xy_crop))
    spatial = np.zeros((ny, nx), dtype=bool)
    spatial[y0:y1, x0:x1] = True
    central = hmap[spatial & ~np.isnan(hmap)]
    med, std = float(np.median(central)), float(np.std(central))
    return spatial & (np.abs(hmap - med) <= z_sigma * std) & ~np.isnan(hmap)


def _crop(shape) -> np.ndarray:
    h, w = shape
    m = np.zeros(shape, bool)
    m[h // 4: h - h // 4, w // 4: w - w // 4] = True
    return m


def _sand_gate(z: np.ndarray, crop: np.ndarray) -> np.ndarray:
    vals = z[crop & np.isfinite(z)]
    mu, sd = vals.mean(), vals.std()
    return crop & np.isfinite(z) & (np.abs(z - mu) <= 3 * sd)


def readout(run: Path, source: str = "cloud", method: str = "bin") -> dict:
    res = _grid_resolution(run)
    frames = _load_points(run, source)
    if method == "bin":
        maps, gx, gy = _height_maps_binned(frames, res)
    else:
        maps, gx, gy = _height_maps(frames, res)
    names = [n for n, _ in frames]
    paper_roi = _paper_sand_mask(maps[names[0]]) if method == "bin" else None
    shape = maps[names[0]].shape
    n_cells = shape[0] * shape[1]
    crop = _crop(shape)
    # radial distance of each cell from the grid centre, in mm
    cx, cy = gx.mean(), gy.mean()
    rr = np.hypot(*np.meshgrid(gx - cx, gy - cy)) * 1000

    result = {
        "run": str(run.resolve()),
        "source": source,
        "method": method,
        "grid_resolution_m": res,
        "grid_shape": list(shape),
        "grid_cells": n_cells,
        "crop_cells": int(crop.sum()),
        "per_frame_valid_fraction": {n: float(np.isfinite(maps[n]).mean()) for n in names},
        "pairs": [],
    }
    for a, b in zip(names, names[1:]):
        za, zb = maps[a], maps[b]
        both = np.isfinite(za) & np.isfinite(zb)
        if paper_roi is not None:
            roi = paper_roi & both
        else:
            roi = _sand_gate(za, crop) & _sand_gate(zb, crop)
        dz = np.abs(za - zb) * 1000  # mm
        tail = both & (dz > TAIL_MM)
        outside = both & ~roi
        result["pairs"].append({
            "pair": f"{a}-{b}",
            "valid_a": float(np.isfinite(za).mean()),
            "valid_b": float(np.isfinite(zb).mean()),
            "valid_both_fraction": float(both.mean()),
            "valid_both_cells": int(both.sum()),
            "roi_cells": int(roi.sum()),
            "roi_fraction_of_grid": float(roi.sum() / n_cells),
            "roi_valid_fraction_of_crop": float(roi.sum() / crop.sum()),
            "common_cells_used_fraction": float(roi.sum() / both.sum()),
            "roi_within_0p5mm": float((dz[roi] <= 0.5).mean()),
            "roi_within_1p0mm": float((dz[roi] <= 1.0).mean()),
            "roi_median_abs_dz_mm": float(np.median(dz[roi])),
            "tail_cells": int(tail.sum()),
            "tail_fraction_of_valid_both": float(tail.sum() / both.sum()),
            "tail_cells_in_roi": int((tail & roi).sum()),
            "tail_radius_mm_p5_p50_p95": [float(v) for v in np.percentile(rr[tail], [5, 50, 95])] if tail.any() else None,
            "valid_both_radius_mm_p95": float(np.percentile(rr[both], 95)),
            "outside_roi_median_abs_dz_mm": float(np.median(dz[outside])),
            "outside_roi_p95_abs_dz_mm": float(np.percentile(dz[outside], 95)),
        })
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("run", type=Path)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--source", choices=["cloud", "mesh"], default="cloud",
                    help="grid the fused point cloud (default) or the surface mesh vertices")
    ap.add_argument("--method", choices=["interp", "bin"], default="bin",
                    help="interp: linear griddata on the union grid (AquaMVS gallery); "
                         "bin: per-cell mean on frame 0's grid with the frame-0 sand mask "
                         "(the paper's DissertationFigures procedure)")
    args = ap.parse_args()
    r = readout(args.run, args.source, args.method)
    text = json.dumps(r, indent=2)
    if args.json:
        args.json.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
