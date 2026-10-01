"""
R1.5 temporal median on/off: raw vs median-filtered reconstruction of one frame.

Compares two fused point clouds of the same frame -- one reconstructed from the
temporal-median image set, one from the raw frames -- using the paper's height-map
procedure (scripts/temporal_coverage.py --method bin: per-cell mean on a 2 mm grid
spanning the median-filtered cloud, sand mask from the median-filtered map).

Reports fused point counts and the surface difference: over the sand ROI, over all
cells valid in both, and the count of cells differing by more than 10 mm.

Usage:
    python scripts/median_comparison.py <filtered fused.ply> <raw fused.ply> [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import open3d as o3d

sys.path.insert(0, str(Path(__file__).resolve().parent))
from temporal_coverage import TAIL_MM, _height_maps_binned, _paper_sand_mask  # noqa: E402

GRID_RES = 0.002


def compare(filtered_ply: Path, raw_ply: Path) -> dict:
    frames = [
        ("filtered", np.asarray(o3d.io.read_point_cloud(str(filtered_ply)).points)),
        ("raw", np.asarray(o3d.io.read_point_cloud(str(raw_ply)).points)),
    ]
    n_filt, n_raw = len(frames[0][1]), len(frames[1][1])
    maps, _gx, _gy = _height_maps_binned(frames, GRID_RES)
    zf, zr = maps["filtered"], maps["raw"]
    both = np.isfinite(zf) & np.isfinite(zr)
    roi = _paper_sand_mask(zf) & both
    dz = np.abs(zr - zf) * 1000  # mm
    return {
        "filtered_ply": str(filtered_ply.resolve()),
        "raw_ply": str(raw_ply.resolve()),
        "points_filtered": n_filt,
        "points_raw": n_raw,
        "points_change_pct": 100 * (n_raw / n_filt - 1),
        "valid_filtered": float(np.isfinite(zf).mean()),
        "valid_raw": float(np.isfinite(zr).mean()),
        "valid_both": float(both.mean()),
        "roi_cells": int(roi.sum()),
        "roi_median_abs_dz_mm": float(np.median(dz[roi])),
        "roi_p95_abs_dz_mm": float(np.percentile(dz[roi], 95)),
        "roi_within_0p5mm": float((dz[roi] <= 0.5).mean()),
        "roi_within_1p0mm": float((dz[roi] <= 1.0).mean()),
        "roi_tail_cells": int((dz[roi] > TAIL_MM).sum()),
        "valid_both_median_abs_dz_mm": float(np.median(dz[both])),
        "valid_both_tail_cells": int((dz[both] > TAIL_MM).sum()),
        "valid_both_tail_fraction": float((dz[both] > TAIL_MM).mean()),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("filtered_ply", type=Path)
    ap.add_argument("raw_ply", type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    r = compare(args.filtered_ply, args.raw_ply)
    text = json.dumps(r, indent=2)
    if args.json:
        args.json.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
