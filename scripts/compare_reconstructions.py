"""
Compare two AquaMVS reconstruction output trees frame-by-frame.

Used to check that a re-run reconstruction (e.g. data/runs/control_refractive/output)
reproduces the archived one (data/aquamvs_ground_truth_analysis/output). Reports, per
frame: per-camera depth-map validity agreement and |depth difference| on the common
valid pixels, plus fused point counts.

Usage:
    python scripts/compare_reconstructions.py <reference output dir> <candidate output dir>
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


def _load_depth(path: Path) -> np.ndarray:
    with np.load(path) as z:
        key = "depth" if "depth" in z.files else z.files[0]
        return z[key].astype(np.float64)


def _ply_vertex_count(path: Path) -> int:
    with path.open("rb") as fh:
        for raw in fh:
            line = raw.decode("ascii", errors="replace").strip()
            if line.startswith("element vertex"):
                return int(line.split()[-1])
            if line == "end_header":
                break
    return -1


def main(ref_root: Path, cand_root: Path) -> None:
    frames = sorted(p.name for p in ref_root.glob("frame_*") if p.is_dir())
    print(f"reference: {ref_root}\ncandidate: {cand_root}\n")
    print(f"{'frame':13s} {'cams':>4s} {'valid ref':>9s} {'valid cand':>10s} {'valid IoU':>9s} "
          f"{'med|dd| mm':>10s} {'p95|dd| mm':>10s} {'max|dd| mm':>10s} {'fused ref':>10s} {'fused cand':>10s}")
    all_dd = []
    for fr in frames:
        rd, cd = ref_root / fr / "depth_maps", cand_root / fr / "depth_maps"
        if not cd.exists():
            print(f"{fr:13s} MISSING in candidate")
            continue
        vr = vc = inter = union = 0
        dds = []
        cams = sorted(p.stem for p in rd.glob("*.npz"))
        for cam in cams:
            a, b = _load_depth(rd / f"{cam}.npz"), _load_depth(cd / f"{cam}.npz")
            ma, mb = np.isfinite(a) & (a > 0), np.isfinite(b) & (b > 0)
            vr += ma.sum(); vc += mb.sum()
            inter += (ma & mb).sum(); union += (ma | mb).sum()
            both = ma & mb
            dds.append(np.abs(a[both] - b[both]) * 1e3)
        dd = np.concatenate(dds) if dds else np.array([np.nan])
        all_dd.append(dd)
        fr_ref = _ply_vertex_count(ref_root / fr / "point_cloud" / "fused.ply")
        fr_cand = _ply_vertex_count(cand_root / fr / "point_cloud" / "fused.ply")
        print(f"{fr:13s} {len(cams):4d} {vr:9d} {vc:10d} {inter / max(union, 1):9.4f} "
              f"{np.median(dd):10.4f} {np.percentile(dd, 95):10.4f} {dd.max():10.4f} "
              f"{fr_ref:10d} {fr_cand:10d}")
    dd = np.concatenate(all_dd)
    print(f"\nALL FRAMES: common-valid pixels {dd.size:,}; |dd| median {np.median(dd):.4f} mm, "
          f"p95 {np.percentile(dd, 95):.4f} mm, p99 {np.percentile(dd, 99):.4f} mm, "
          f"max {dd.max():.4f} mm; exactly equal {np.mean(dd == 0) * 100:.2f}%")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
