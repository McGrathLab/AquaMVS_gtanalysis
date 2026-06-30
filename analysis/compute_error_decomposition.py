"""
AquaMVS Analysis — Compute Error-Direction Decomposition (MET-06)
=================================================================
Driver for the two residual decompositions (see analysis/error_decomposition.py):

  A. Board frame  — in-plane vs out-of-plane, from the MET-05 rigid fit of
                    consensus corners to the ideal board (per frame, inliers).
  B. Camera frame — range vs lateral, from each per-camera corner's offset from
                    the cross-camera consensus, projected onto that camera's
                    in-water viewing ray (cast_ray). The refraction-relevant test.

Runs AFTER Phase 3 + Phase 4 (consumes the cleaned corners + reuses their hooks),
in the RAW MVS frame. Writes data/analysis_output/error_decomposition.json.

Usage
-----
    conda run -n AquaMVS python analysis/compute_error_decomposition.py \
        --corners data/analysis_output/corner_transfer/corners.npz \
        --data-root data/aquamvs_ground_truth_analysis \
        --out data/analysis_output
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Allow running from the repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import torch

from analysis.loader import GroundTruthDataset, DatasetConfig
from analysis.charuco_detect import build_board_geometry
from analysis.cross_camera import load_corners
from analysis.projection import build_projection_models
from analysis.alignment import (
    build_consensus_corners,
    ideal_board_corners,
    matched_arrays,
    rigid_inlier_fit,
)
from analysis.error_decomposition import (
    board_frame_residuals,
    decompose_board_frame,
    decompose_range_lateral,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

OUT_NAME = "error_decomposition.json"


def _rms(vals: list[float]) -> float:
    a = np.asarray(vals, dtype=np.float64)
    a = a[np.isfinite(a)]
    return float(np.sqrt(np.mean(a ** 2))) if len(a) else float("nan")


def frame_cross_camera_samples(frame_idx, camera_id, corner_id, points, pixels, models, frame):
    """
    Per-observation cross-camera residual vectors + viewing rays for one frame.

    Mirrors the range-vs-lateral collection in main(): for each corner co-observed
    by >=2 cameras, residual = per-camera point minus the cross-camera consensus;
    ray = the in-water cast_ray direction at that corner's pixel for that camera.

    Returns (residuals (N,3) world metres, ray_dirs (N,3) unit-ish) — possibly empty.
    """
    fmask = frame_idx == frame
    f_cid = corner_id[fmask]
    f_cam = np.array([str(c) for c in camera_id[fmask]])
    f_pts = np.asarray(points, dtype=np.float64)[fmask]
    f_pix = np.asarray(pixels, dtype=np.float64)[fmask]

    by_corner: dict[int, list[int]] = {}
    for i, c in enumerate(f_cid):
        by_corner.setdefault(int(c), []).append(i)

    res_list, cam_of_res, pix_of_res = [], [], []
    for cid, rows in by_corner.items():
        if len(rows) < 2:
            continue
        cons = f_pts[rows].mean(axis=0)
        for r in rows:
            res_list.append(f_pts[r] - cons)
            cam_of_res.append(f_cam[r])
            pix_of_res.append(f_pix[r])

    if not res_list:
        return np.zeros((0, 3)), np.zeros((0, 3))

    res_arr = np.array(res_list, dtype=np.float64)
    pix_arr = np.array(pix_of_res, dtype=np.float64)
    cam_arr = np.array(cam_of_res)
    ray_dirs = np.zeros_like(res_arr)
    for cam in set(cam_arr):
        sel = np.where(cam_arr == cam)[0]
        with torch.no_grad():
            _, dirs = models[cam].cast_ray(torch.tensor(pix_arr[sel], dtype=torch.float32))
        ray_dirs[sel] = dirs.detach().cpu().numpy().astype(np.float64)
    return res_arr, ray_dirs


def main(corners_path: str, data_root: str, out: str) -> None:
    t0 = time.time()

    # ── Load cleaned corners (Z>0 gated in load_corners) ──────────────────────
    corners = load_corners(corners_path)
    frame_idx = corners["frame_idx"]
    camera_id = corners["camera_id"]
    corner_id = corners["corner_id"]
    points = corners["points"].astype(np.float64)
    pixels = corners["pixels"].astype(np.float64)
    logger.info("Loaded %d valid corner rows", len(frame_idx))

    # ── Dataset / board / projection models ───────────────────────────────────
    ds = GroundTruthDataset(DatasetConfig(data_root=Path(data_root)))
    calib = ds.calibration()
    board = build_board_geometry(ds.board_spec())
    ideal_all = ideal_board_corners(board)
    cams = sorted(set(str(c) for c in camera_id))
    models = build_projection_models(calib, cams)

    unique_frames = sorted(set(int(f) for f in frame_idx))
    logger.info("Frames: %s", unique_frames)

    per_frame: list[dict] = []
    # Pooled per-observation component arrays
    oop_all: list[float] = []
    ip_all: list[float] = []
    range_all: list[float] = []
    lateral_all: list[float] = []

    for frame in unique_frames:
        fmask = frame_idx == frame

        # ── A. Board-frame decomposition (in-plane vs out-of-plane) ───────────
        consensus = build_consensus_corners(frame_idx, camera_id, corner_id, points, frame)
        board_res = {"out_of_plane_rms_mm": None, "in_plane_rms_mm": None, "n": 0}
        if len(consensus) >= 3:
            ids, src_ideal, dst_consensus = matched_arrays(consensus, ideal_all)
            fit = rigid_inlier_fit(src_ideal, dst_consensus)
            inl = fit["inlier_mask"]
            res_vecs, normal = board_frame_residuals(
                fit["R"], fit["t"], src_ideal[inl], dst_consensus[inl]
            )
            d = decompose_board_frame(res_vecs, normal)
            board_res = {
                "out_of_plane_rms_mm": d["out_of_plane_rms_mm"],
                "in_plane_rms_mm": d["in_plane_rms_mm"],
                "n": d["n"],
                "degenerate": bool(fit["degenerate"]),
            }
            oop_all.extend(d["out_of_plane_mm"].tolist())
            ip_all.extend(d["in_plane_mm"].tolist())

        # ── B. Range-vs-lateral decomposition (cross-camera offsets) ──────────
        # Consensus per corner counting cameras (>=2 needed to define an offset).
        f_cid = corner_id[fmask]
        f_cam = np.array([str(c) for c in camera_id[fmask]])
        f_pts = points[fmask]
        f_pix = pixels[fmask]

        # group rows by corner_id
        by_corner: dict[int, list[int]] = {}
        for i, c in enumerate(f_cid):
            by_corner.setdefault(int(c), []).append(i)

        res_list: list[np.ndarray] = []
        cam_of_res: list[str] = []
        pix_of_res: list[np.ndarray] = []
        for cid, rows in by_corner.items():
            if len(rows) < 2:
                continue  # need >=2 cameras to define a cross-camera offset
            cons = f_pts[rows].mean(axis=0)
            for r in rows:
                res_list.append(f_pts[r] - cons)
                cam_of_res.append(f_cam[r])
                pix_of_res.append(f_pix[r])

        range_res = {"range_rms_mm": None, "lateral_rms_mm": None,
                     "range_dominance": None, "n": 0}
        if res_list:
            res_arr = np.array(res_list, dtype=np.float64)
            pix_arr = np.array(pix_of_res, dtype=np.float64)
            cam_arr = np.array(cam_of_res)

            # Viewing-ray direction per observation via cast_ray (in-water ray),
            # batched per camera for efficiency.
            ray_dirs = np.zeros_like(res_arr)
            for cam in set(cam_arr):
                sel = np.where(cam_arr == cam)[0]
                with torch.no_grad():
                    _, dirs = models[cam].cast_ray(
                        torch.tensor(pix_arr[sel], dtype=torch.float32)
                    )
                ray_dirs[sel] = dirs.detach().cpu().numpy().astype(np.float64)

            d = decompose_range_lateral(res_arr, ray_dirs)
            range_res = {
                "range_rms_mm": d["range_rms_mm"],
                "lateral_rms_mm": d["lateral_rms_mm"],
                "range_dominance": d["range_dominance"],
                "n": d["n"],
            }
            range_all.extend(d["range_mm"].tolist())
            lateral_all.extend(d["lateral_mm"].tolist())

        per_frame.append({
            "frame_idx": frame,
            "board_frame": board_res,
            "range_lateral": range_res,
        })
        logger.info(
            "Frame %d: board[oop=%s ip=%s] | range/lat[rng=%s lat=%s dom=%s]",
            frame,
            _fmt(board_res["out_of_plane_rms_mm"]), _fmt(board_res["in_plane_rms_mm"]),
            _fmt(range_res["range_rms_mm"]), _fmt(range_res["lateral_rms_mm"]),
            _fmt(range_res["range_dominance"]),
        )

    # ── Pooled ────────────────────────────────────────────────────────────────
    pooled_range_rms = _rms(range_all)
    pooled_lateral_rms = _rms(lateral_all)
    pooled = {
        "board_frame": {
            "out_of_plane_rms_mm": _rms(oop_all),
            "in_plane_rms_mm": _rms(ip_all),
            "n": len(oop_all),
        },
        "range_lateral": {
            "range_rms_mm": pooled_range_rms,
            "lateral_rms_mm": pooled_lateral_rms,
            "range_dominance": (pooled_range_rms / pooled_lateral_rms
                                if pooled_lateral_rms > 1e-9 else float("inf")),
            "n": len(range_all),
        },
    }

    note = {
        "metric": "MET-06 error-direction decomposition",
        "computed_after": ["phase3_scale_independent", "phase4_scale_alignment"],
        "board_frame": (
            "Residuals of the MET-05 rigid (no-scale) ideal-board fit, split into "
            "out-of-plane (board normal) vs in-plane (board surface). Out-of-plane "
            "is a flatness-type error; in-plane is lateral grid distortion."
        ),
        "range_lateral": (
            "Per-camera corner offsets from the cross-camera consensus, split into "
            "range (along the in-water viewing ray, cast_ray) vs lateral. Refraction "
            "biases range, so range_dominance > 1 is the refractive signature; ~1 is "
            "generic noise. This is the refraction-relevant decomposition of MET-03."
        ),
        "interpretation": (
            f"range_dominance(pooled) = {pooled['range_lateral']['range_dominance']:.2f} "
            f"(range {pooled_range_rms:.2f} mm vs lateral {pooled_lateral_rms:.2f} mm)"
        ),
    }

    out_path = Path(out) / OUT_NAME
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        json.dump({
            "units": "mm",
            "per_frame": per_frame,
            "pooled": pooled,
            "note": note,
        }, fh, indent=2)
    logger.info("Saved %s", out_path)

    # ── Console summary ───────────────────────────────────────────────────────
    print("\n=== MET-06: Error-Direction Decomposition ===")
    print("  Board frame (rigid-fit residuals):")
    print(f"    out-of-plane RMS = {pooled['board_frame']['out_of_plane_rms_mm']:.3f} mm")
    print(f"    in-plane     RMS = {pooled['board_frame']['in_plane_rms_mm']:.3f} mm")
    print("  Camera frame (cross-camera offsets):")
    print(f"    range   RMS = {pooled_range_rms:.3f} mm")
    print(f"    lateral RMS = {pooled_lateral_rms:.3f} mm")
    print(f"    range_dominance = {pooled['range_lateral']['range_dominance']:.2f} "
          f"({'range-dominated (refractive signature)' if pooled['range_lateral']['range_dominance'] > 1.0 else 'balanced / lateral-dominated'})")
    print(f"\nComputed in {time.time() - t0:.1f} s — RAW MVS frame, after Phase 3/4.")
    print("=== MET-06 PASSED ===")


def _fmt(v) -> str:
    return "None" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.2f}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute MET-06 error-direction decomposition.")
    parser.add_argument("--corners", default="data/analysis_output/corner_transfer/corners.npz")
    parser.add_argument("--data-root", default="data/aquamvs_ground_truth_analysis")
    parser.add_argument("--out", default="data/analysis_output")
    args = parser.parse_args()
    main(args.corners, args.data_root, args.out)
