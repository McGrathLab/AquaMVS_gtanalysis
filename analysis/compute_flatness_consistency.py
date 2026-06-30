"""
AquaMVS Analysis — MET-01 / MET-02 Flatness & Consistency Sweep
=================================================================
Sweeps the 8 held-out validation frames, computing:

  MET-01 — Board flatness: RANSAC + SVD plane-fit RMS on the dense board slab
            (point-to-plane residuals in mm, per frame + pooled across frames).

  MET-02 — Spatial / angular consistency: per frame records board centroid
            (XY + depth), tilt (fitted-plane-normal angle vs interface_normal),
            flatness RMS, and a board size measure (median adjacent-corner spacing
            from the transferred ChArUco corners).  Reports how flatness and size
            VARY across the working volume (depth, lateral position, tilt) via
            ranges, mean, and coefficient of variation.

ORDERING INVARIANT: everything is computed in the RAW MVS reconstruction as-is.
No Umeyama / ICP / rigid or scale alignment to the ideal board is applied before
these numbers are written.  Phase 4 may align afterward; this script must run first.

Outputs (under --out-dir):
  flatness_consistency.json         — per-frame records + pooled + variation summary
  flatness_consistency_schema.json  — field descriptions sidecar

Run:
    conda run -n AquaMVS python analysis/compute_flatness_consistency.py
    conda run -n AquaMVS python analysis/compute_flatness_consistency.py \\
        --data-root data/aquamvs_ground_truth_analysis \\
        --corners data/analysis_output/corner_transfer/corners.npz \\
        --out-dir data/analysis_output/scale_independent_metrics
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from pathlib import Path
from typing import Optional

# Allow running from the repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import open3d as o3d

from analysis.loader import GroundTruthDataset, DatasetConfig
from analysis.corner_transfer import fit_board_plane, crop_cloud_to_slab, DEFAULT_SLAB_THICKNESS
from analysis.flatness import robust_plane_fit, plane_tilt_deg, board_size_from_corners

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Per-frame processing ───────────────────────────────────────────────────────

def process_frame(
    frame,
    ds: GroundTruthDataset,
    calib,
    npz_frame_idx: np.ndarray,
    npz_corner_id: np.ndarray,
    npz_points: np.ndarray,
    slab_thickness: float,
) -> tuple[dict, Optional[np.ndarray]]:
    """
    Process one validation frame: crop dense cloud to board slab, run MET-01/MET-02.

    Returns (record_dict, inlier_residuals_m) where inlier_residuals_m is the
    array of per-inlier signed distances (metres) for pooled RMS accumulation,
    or None if the frame was skipped.
    """
    fidx = int(frame.output_idx)

    # ── 1. Select this frame's corner rows ────────────────────────────────────
    frame_mask = npz_frame_idx == fidx
    frame_corner_ids = npz_corner_id[frame_mask]
    frame_points = npz_points[frame_mask].astype(np.float64)  # (K, 3) metres

    n_corners_used = int(frame_mask.sum())
    logger.info("Frame %d: %d transferred corners available", fidx, n_corners_used)

    if n_corners_used < 3:
        logger.warning("Frame %d: fewer than 3 corners — skipping", fidx)
        return {
            "frame_idx": fidx,
            "skipped_reason": f"too few corners ({n_corners_used} < 3)",
            "flatness_rms_mm": None,
            "n_slab_points": 0,
            "n_inliers": 0,
            "n_corners_used": n_corners_used,
        }, None

    # ── 2. Seed plane from corners (COARSE; only to locate the board slab) ───
    seed = fit_board_plane(frame_points)
    if seed is None:
        logger.warning("Frame %d: corner seed plane fit failed — skipping", fidx)
        return {
            "frame_idx": fidx,
            "skipped_reason": "corner plane fit failed",
            "flatness_rms_mm": None,
            "n_slab_points": 0,
            "n_inliers": 0,
            "n_corners_used": n_corners_used,
        }, None

    seed_point, seed_normal = seed

    # ── 3. Load fused cloud ONCE for this frame, crop to board slab, then DROP
    cloud_path = ds.fused_cloud_path(frame)
    if not cloud_path.exists():
        logger.warning("Frame %d: fused cloud not found at %s — skipping", fidx, cloud_path)
        return {
            "frame_idx": fidx,
            "skipped_reason": f"fused cloud not found: {cloud_path}",
            "flatness_rms_mm": None,
            "n_slab_points": 0,
            "n_inliers": 0,
            "n_corners_used": n_corners_used,
        }, None

    logger.info("Frame %d: loading fused cloud %s ...", fidx, cloud_path.name)
    cloud_xyz = np.asarray(
        o3d.io.read_point_cloud(str(cloud_path)).points, dtype=np.float64
    )
    logger.info("Frame %d: fused cloud loaded (%d points)", fidx, len(cloud_xyz))

    slab = crop_cloud_to_slab(cloud_xyz, seed_point, seed_normal, slab_thickness)
    n_slab = int(len(slab))
    logger.info("Frame %d: slab crop -> %d points (thickness=%.1f mm)",
                fidx, n_slab, slab_thickness * 1000)

    # Drop the full cloud immediately to bound memory before the next frame
    del cloud_xyz
    cloud_xyz = None  # noqa: F841

    if n_slab < 50:
        logger.warning("Frame %d: too few slab points (%d < 50) — skipping", fidx, n_slab)
        return {
            "frame_idx": fidx,
            "skipped_reason": f"too few slab points ({n_slab} < 50)",
            "flatness_rms_mm": None,
            "n_slab_points": n_slab,
            "n_inliers": 0,
            "n_corners_used": n_corners_used,
        }, None

    # ── 4. MET-01: robust plane fit on slab points ────────────────────────────
    fit = robust_plane_fit(slab, dist_threshold=0.002, n_iters=200, seed=0)
    flatness_rms_mm = fit["rms_mm"]
    n_inliers = fit["n_inliers"]
    plane_normal = fit["normal"]
    plane_point_fit = fit["point"]

    # Collect inlier signed residuals (metres) for pooled RMS
    inlier_residuals_m: Optional[np.ndarray] = None
    if plane_normal is not None and n_inliers >= 3:
        inlier_pts = slab[fit["inlier_mask"]]
        inlier_residuals_m = (inlier_pts - plane_point_fit) @ plane_normal

    # ── 5. MET-02 per-frame record ────────────────────────────────────────────
    # Centroid: mean of slab inlier points; if fit failed, fall back to slab mean
    if plane_normal is not None and n_inliers >= 3:
        centroid_xyz = slab[fit["inlier_mask"]].mean(axis=0)
    else:
        centroid_xyz = slab.mean(axis=0)

    centroid_xyz_m = centroid_xyz.tolist()

    # Depth: projection of centroid onto the rig viewing axis (interface_normal).
    # interface_normal points in the direction the rig "looks into the water".
    # Projecting the centroid onto this axis gives a signed depth coordinate
    # consistent across all frames (larger = deeper into the scene).
    interface_normal = np.asarray(calib.interface_normal, dtype=np.float64).ravel()
    depth_m = float(centroid_xyz @ interface_normal)

    # Lateral position: centroid component orthogonal to interface_normal in XY
    lateral_xy_m = float(np.linalg.norm(
        centroid_xyz[:2] - depth_m * interface_normal[:2]
    ))

    # Tilt: angle between fitted plane normal and interface_normal
    if plane_normal is not None:
        tilt_deg = plane_tilt_deg(plane_normal, interface_normal)
        plane_normal_list = plane_normal.tolist()
    else:
        tilt_deg = float("nan")
        plane_normal_list = None

    # Board size from per-frame median 3-D position per corner_id across cameras
    # Use only this frame's corners
    if n_corners_used >= 2:
        size_result = board_size_from_corners(frame_corner_ids, frame_points,
                                              _BoardSpecProxy(ds))
        board_size_mm = size_result["size_mm"]
        n_pairs = size_result["n_pairs"]
    else:
        board_size_mm = float("nan")
        n_pairs = 0

    record = {
        "frame_idx": fidx,
        "centroid_xyz_m": centroid_xyz_m,
        "depth_m": depth_m,
        "lateral_xy_m": lateral_xy_m,
        "tilt_deg": tilt_deg if math.isfinite(tilt_deg) else None,
        "flatness_rms_mm": flatness_rms_mm if math.isfinite(flatness_rms_mm) else None,
        "board_size_mm": board_size_mm if math.isfinite(board_size_mm) else None,
        "n_pairs": n_pairs,
        "n_slab_points": n_slab,
        "n_inliers": n_inliers,
        "n_corners_used": n_corners_used,
        "plane_normal": plane_normal_list,
    }

    return record, inlier_residuals_m


class _BoardSpecProxy:
    """Lightweight proxy so board_size_from_corners gets squares_x/squares_y."""
    def __init__(self, ds: GroundTruthDataset) -> None:
        spec = ds.board_spec()
        self.squares_x = spec.squares_x
        self.squares_y = spec.squares_y
        self.square_size = spec.square_size


# ── Main ───────────────────────────────────────────────────────────────────────

def main(
    data_root: str,
    corners_path: str,
    out_dir: str,
    slab_thickness: float,
) -> None:
    t0 = time.time()

    # ── Setup ──────────────────────────────────────────────────────────────────
    config = DatasetConfig(data_root=Path(data_root))
    ds = GroundTruthDataset(config)
    calib = ds.calibration()
    frames = ds.validation_frames()

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    logger.info(
        "compute_flatness_consistency: %d validation frames, slab=%.1f mm",
        len(frames), slab_thickness * 1000,
    )

    # ── Load corners.npz once (shared across all frames) ──────────────────────
    corners_file = Path(corners_path)
    if not corners_file.exists():
        logger.error("corners.npz not found at %s", corners_file)
        sys.exit(1)

    npz = np.load(str(corners_file), allow_pickle=True)
    npz_frame_idx = npz["frame_idx"].astype(np.int32)     # (N,)
    npz_corner_id = npz["corner_id"].astype(np.int32)     # (N,)
    npz_points    = npz["points"].astype(np.float32)       # (N,3) metres
    npz_method    = np.array([str(m) for m in npz["method"]], dtype=object)

    # Validity gate: drop non-physical corners (non-finite or Z<=0) AND the
    # plane-fit FALLBACK corners. The fallback (~0.2%) is physical but cm-inaccurate
    # and is the dominant residual-error source; all reported metrics use direct
    # refractive-depth corners only. Both the corner-seed plane (MET-01 slab crop)
    # and inter-corner spacing (MET-02) use this gated set.
    _keep = (
        np.isfinite(npz_points).all(axis=1)
        & (npz_points[:, 2] > 0.0)
        & (npz_method != "plane_fit")
    )
    _n_dropped = int((~_keep).sum())
    if _n_dropped:
        logger.warning(
            "Dropped %d corner(s) (non-physical or plane-fit fallback); "
            "metrics use direct-depth corners only", _n_dropped,
        )
    npz_frame_idx = npz_frame_idx[_keep]
    npz_corner_id = npz_corner_id[_keep]
    npz_points    = npz_points[_keep]
    logger.info("Loaded corners.npz: %d valid corner observations", len(npz_frame_idx))

    # ── Sweep frames ──────────────────────────────────────────────────────────
    per_frame: list[dict] = []
    all_inlier_residuals_sq: list[float] = []  # accumulated squared residuals (m^2)

    for frame in frames:
        record, residuals_m = process_frame(
            frame, ds, calib,
            npz_frame_idx, npz_corner_id, npz_points,
            slab_thickness,
        )
        per_frame.append(record)

        if residuals_m is not None and len(residuals_m) > 0:
            all_inlier_residuals_sq.extend((residuals_m ** 2).tolist())

    # ── Pooled MET-01 flatness (true RMS across ALL inlier residuals) ─────────
    valid_rms = [r["flatness_rms_mm"] for r in per_frame
                 if r.get("flatness_rms_mm") is not None]
    valid_size = [r["board_size_mm"] for r in per_frame
                  if r.get("board_size_mm") is not None]
    valid_tilt = [r["tilt_deg"] for r in per_frame
                  if r.get("tilt_deg") is not None]
    valid_depth = [r["depth_m"] for r in per_frame
                   if r.get("depth_m") is not None and r.get("flatness_rms_mm") is not None]

    if all_inlier_residuals_sq:
        pooled_rms_mm = float(
            math.sqrt(sum(all_inlier_residuals_sq) / len(all_inlier_residuals_sq)) * 1000.0
        )
    else:
        pooled_rms_mm = float("nan")

    pooled = {
        "flatness_rms_mm_pooled": pooled_rms_mm if math.isfinite(pooled_rms_mm) else None,
        "flatness_rms_mm_mean": float(np.mean(valid_rms)) if valid_rms else None,
        "flatness_rms_mm_min": float(min(valid_rms)) if valid_rms else None,
        "flatness_rms_mm_max": float(max(valid_rms)) if valid_rms else None,
        "flatness_rms_mm_range": float(max(valid_rms) - min(valid_rms)) if len(valid_rms) >= 2 else None,
        "n_frames_with_flatness": len(valid_rms),
    }

    # ── MET-02 variation: size, tilt, depth ───────────────────────────────────
    if valid_size:
        size_mean = float(np.mean(valid_size))
        size_std = float(np.std(valid_size, ddof=0))
        size_cv = float(size_std / size_mean) if size_mean > 0 else float("nan")
    else:
        size_mean = size_std = size_cv = float("nan")

    variation = {
        "board_size_mm_mean": size_mean if math.isfinite(size_mean) else None,
        "board_size_mm_std": size_std if math.isfinite(size_std) else None,
        "board_size_mm_min": float(min(valid_size)) if valid_size else None,
        "board_size_mm_max": float(max(valid_size)) if valid_size else None,
        "board_size_mm_range": float(max(valid_size) - min(valid_size)) if len(valid_size) >= 2 else None,
        "board_size_cv": size_cv if math.isfinite(size_cv) else None,
        "tilt_deg_min": float(min(valid_tilt)) if valid_tilt else None,
        "tilt_deg_max": float(max(valid_tilt)) if valid_tilt else None,
        "tilt_deg_range": float(max(valid_tilt) - min(valid_tilt)) if len(valid_tilt) >= 2 else None,
        # Parallel arrays for Phase 5 (depth vs flatness, tilt vs size, etc.)
        "per_frame_arrays": {
            "frame_idx": [r["frame_idx"] for r in per_frame],
            "depth_m": [r.get("depth_m") for r in per_frame],
            "lateral_xy_m": [r.get("lateral_xy_m") for r in per_frame],
            "tilt_deg": [r.get("tilt_deg") for r in per_frame],
            "flatness_rms_mm": [r.get("flatness_rms_mm") for r in per_frame],
            "board_size_mm": [r.get("board_size_mm") for r in per_frame],
        },
    }

    # ── Persist JSON artifact ─────────────────────────────────────────────────
    artifact = {
        "metric": "MET-01 flatness + MET-02 spatial/angular consistency",
        "units": "flatness_rms in mm, distances in m, tilt in deg",
        "computed_before_alignment": True,
        "slab_thickness_m": slab_thickness,
        "per_frame": per_frame,
        "pooled": pooled,
        "variation": variation,
    }

    json_path = out_path / "flatness_consistency.json"
    with json_path.open("w") as fh:
        json.dump(artifact, fh, indent=2)
    logger.info("Saved flatness_consistency.json -> %s", json_path)

    # ── Schema sidecar ────────────────────────────────────────────────────────
    schema = {
        "description": "AquaMVS MET-01/MET-02 flatness and spatial/angular consistency metrics",
        "file": "flatness_consistency.json",
        "generated_by": "analysis/compute_flatness_consistency.py",
        "ordering_invariant": (
            "All values computed in the raw MVS reconstruction BEFORE any rigid/scale "
            "alignment to the ideal board (Umeyama/ICP). Phase 4 may align afterward."
        ),
        "fields": {
            "metric": "Human-readable metric identifiers (MET-01, MET-02)",
            "units": "Unit conventions: flatness_rms in mm, distances in metres, tilt in degrees",
            "computed_before_alignment": "Always true — structural ordering guarantee",
            "slab_thickness_m": "Total slab thickness used for dense cloud crop (metres)",
            "per_frame": {
                "description": "List of per-frame MET-01/MET-02 records",
                "frame_idx": "int — output frame index (validation: 1,2,3,4,6,7,8,9)",
                "centroid_xyz_m": "(3,) float — mean of slab inlier points in MVS world frame (metres)",
                "depth_m": "float — centroid projection onto interface_normal (rig viewing axis, metres)",
                "lateral_xy_m": "float — centroid XY distance from the rig optical axis (metres)",
                "tilt_deg": "float — angle between fitted plane normal and interface_normal (degrees, 0–90)",
                "flatness_rms_mm": "float — MET-01: RMS of point-to-plane inlier residuals (mm); null if skipped",
                "board_size_mm": "float — median adjacent-corner spacing in mm (MET-02 consistency proxy); null if < 1 pair",
                "n_pairs": "int — number of adjacent corner pairs used for board_size_mm",
                "n_slab_points": "int — points in the board slab crop",
                "n_inliers": "int — RANSAC inlier count for flatness fit",
                "n_corners_used": "int — transferred corners available for this frame",
                "plane_normal": "(3,) float — unit normal of the fitted plane in MVS world frame",
                "skipped_reason": "str (only present if frame was skipped) — reason for skip",
            },
            "pooled": {
                "description": "MET-01 pooled summary across all valid frames",
                "flatness_rms_mm_pooled": "float — true pooled RMS: sqrt(mean of all inlier residuals^2) in mm",
                "flatness_rms_mm_mean": "float — mean of per-frame RMS values (mm)",
                "flatness_rms_mm_min": "float — minimum per-frame RMS (mm)",
                "flatness_rms_mm_max": "float — maximum per-frame RMS (mm)",
                "flatness_rms_mm_range": "float — max - min per-frame RMS (mm)",
                "n_frames_with_flatness": "int — number of frames with a valid flatness estimate",
            },
            "variation": {
                "description": "MET-02 variation summary across the working volume",
                "board_size_mm_mean": "float — mean reconstructed square edge length (mm)",
                "board_size_mm_std": "float — std dev of per-frame board_size_mm (mm)",
                "board_size_mm_min": "float — minimum per-frame board_size_mm (mm)",
                "board_size_mm_max": "float — maximum per-frame board_size_mm (mm)",
                "board_size_mm_range": "float — max - min board_size_mm (mm)",
                "board_size_cv": "float — coefficient of variation (std/mean) for board_size_mm",
                "tilt_deg_min": "float — minimum per-frame tilt (deg)",
                "tilt_deg_max": "float — maximum per-frame tilt (deg)",
                "tilt_deg_range": "float — max - min tilt (deg)",
                "per_frame_arrays": {
                    "description": "Parallel arrays for Phase 5 figure rendering",
                    "frame_idx": "int list — frame indices",
                    "depth_m": "float list — per-frame depth (m)",
                    "lateral_xy_m": "float list — per-frame lateral position (m)",
                    "tilt_deg": "float list — per-frame tilt (deg)",
                    "flatness_rms_mm": "float list — per-frame MET-01 flatness RMS (mm)",
                    "board_size_mm": "float list — per-frame board size (mm)",
                },
            },
        },
    }

    schema_path = out_path / "flatness_consistency_schema.json"
    with schema_path.open("w") as fh:
        json.dump(schema, fh, indent=2)
    logger.info("Saved schema -> %s", schema_path)

    # ── Stdout summary table ──────────────────────────────────────────────────
    print()
    print("=== MET-01 / MET-02: Flatness & Spatial/Angular Consistency ===")
    print()
    header = (
        f"  {'Frame':>5}  {'Depth(m)':>8}  {'Tilt(°)':>7}  "
        f"{'Flatness RMS(mm)':>16}  {'Size(mm)':>8}"
    )
    print(header)
    print("  " + "-" * (len(header) - 2))
    for rec in per_frame:
        fidx = rec["frame_idx"]
        depth = rec.get("depth_m")
        tilt = rec.get("tilt_deg")
        rms = rec.get("flatness_rms_mm")
        sz = rec.get("board_size_mm")
        reason = rec.get("skipped_reason", "")
        if reason:
            print(f"  {fidx:>5}  SKIPPED — {reason}")
        else:
            depth_s = f"{depth:.4f}" if depth is not None else "   N/A"
            tilt_s  = f"{tilt:.2f}" if tilt is not None else "  N/A"
            rms_s   = f"{rms:.4f}" if rms is not None else "           N/A"
            sz_s    = f"{sz:.2f}" if sz is not None else "    N/A"
            print(f"  {fidx:>5}  {depth_s:>8}  {tilt_s:>7}  {rms_s:>16}  {sz_s:>8}")

    print()
    print(f"  Pooled flatness RMS (MET-01):  "
          f"{pooled_rms_mm:.4f} mm" if math.isfinite(pooled_rms_mm) else "  Pooled flatness RMS: N/A")
    if valid_rms:
        print(f"  Per-frame range:               "
              f"{min(valid_rms):.4f} – {max(valid_rms):.4f} mm  "
              f"(mean {np.mean(valid_rms):.4f} mm)")
    if valid_size and math.isfinite(size_cv):
        print(f"  Board size (MET-02):           "
              f"mean={size_mean:.2f} mm  CV={size_cv:.4f}  "
              f"range=[{min(valid_size):.2f}, {max(valid_size):.2f}] mm")
    print()
    print("Computed in RAW MVS frame BEFORE any alignment/scaling (MET-01, MET-02)")

    elapsed = time.time() - t0
    logger.info("compute_flatness_consistency complete in %.1f s", elapsed)


# ── Argument parsing ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "AquaMVS flatness & spatial/angular consistency sweep. "
            "Computes MET-01 (board flatness RMS in mm, RANSAC + SVD plane fit on "
            "the dense board slab) and MET-02 (per-frame centroid / depth / tilt / "
            "size + variation across the working volume). "
            "Runs in the RAW MVS frame BEFORE any alignment/scaling. "
            "Persists flatness_consistency.json and a schema sidecar."
        )
    )
    parser.add_argument(
        "--data-root",
        default="data/aquamvs_ground_truth_analysis",
        help="Path to extracted dataset root (default: data/aquamvs_ground_truth_analysis)",
    )
    parser.add_argument(
        "--corners",
        default="data/analysis_output/corner_transfer/corners.npz",
        help="Path to Phase-2 corners.npz (default: data/analysis_output/corner_transfer/corners.npz)",
    )
    parser.add_argument(
        "--out-dir",
        default="data/analysis_output/scale_independent_metrics",
        help="Output directory (default: data/analysis_output/scale_independent_metrics)",
    )
    parser.add_argument(
        "--slab-thickness",
        type=float,
        default=DEFAULT_SLAB_THICKNESS,
        help=f"Board slab crop total thickness in metres (default: {DEFAULT_SLAB_THICKNESS})",
    )
    args = parser.parse_args()
    main(args.data_root, args.corners, args.out_dir, args.slab_thickness)
