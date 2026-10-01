"""
AquaMVS Corner Transfer — XFER-02/03/04 Evidence CLI
======================================================
Runs corner transfer over 8 validation frames x 12 depth-bearing cameras:
  - Direct back-projection via RefractiveProjectionModel (XFER-02)
  - Plane-fit fallback from fused-cloud thin-slab when depth is missing (XFER-03)
  - Per-frame/per-camera dropout report + headline rate (XFER-04)

Memory strategy: the fused dense cloud (~650 MB) is loaded at most ONCE per
frame (reused across all 12 cameras), then dropped before the next frame.

Outputs:
  <out-dir>/corners.npz           — reloadable corner set (schema in corners_schema.json)
  <out-dir>/corners_schema.json   — column descriptions
  <out-dir>/dropout_report.json   — per-(frame,camera) + headline dropout rate

Run:
    python analysis/transfer_corners.py
    python analysis/transfer_corners.py --data-root /path --out-dir /path/out
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

# Allow running from the repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis._paths import analysis_output_root  # noqa: E402

import numpy as np
import open3d as o3d

from analysis.loader import GroundTruthDataset, DatasetConfig
from analysis.charuco_detect import (
    build_board_geometry,
    depth_bearing_cameras,
    detect_corners,
)
from analysis.projection import build_projection_models
from analysis.corner_transfer import transfer_frame_camera

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main(data_root: str, out_dir: str, min_confidence: float) -> None:
    t0 = time.time()

    # ── Setup ──────────────────────────────────────────────────────────────────
    config = DatasetConfig(data_root=Path(data_root))
    ds = GroundTruthDataset(config)

    calib = ds.calibration()
    cams = depth_bearing_cameras(ds)
    models = build_projection_models(calib, cams)
    board = build_board_geometry(ds.board_spec())
    frames = ds.validation_frames()

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    logger.info(
        "transfer_corners: %d validation frames x %d cameras, min_confidence=%.2f",
        len(frames), len(cams), min_confidence,
    )

    # ── Sweep over frames x cameras ───────────────────────────────────────────
    from analysis.corner_transfer import CornerRecord  # imported here to avoid circular ref at top
    all_records: list[CornerRecord] = []
    report_rows: list[dict] = []
    total_detected = 0
    total_direct = 0
    total_plane_fit = 0
    total_unrecovered = 0

    for frame in frames:
        logger.info("=== Frame %d (raw=%d) ===", frame.output_idx, frame.raw_frame_idx)

        # Fused cloud is lazily loaded on the first camera that needs the fallback.
        # It is reused across all cameras in this frame, then dropped.
        cloud_xyz: Optional[np.ndarray] = None
        cloud_loaded = False

        for camera in cams:
            detection = detect_corners(ds, frame, camera, board=board)

            if detection is None or detection.num_corners == 0:
                report_rows.append({
                    "frame_idx": frame.output_idx,
                    "camera_id": camera,
                    "n_detected": 0,
                    "n_direct": 0,
                    "n_plane_fit": 0,
                    "n_unrecovered": 0,
                    "direct_fraction": None,
                    "plane_fit_fraction": None,
                })
                continue

            # Load the fused cloud on first camera in this frame that has detections.
            # We always supply it so the fallback is always tried when needed.
            if not cloud_loaded:
                cloud_path = ds.fused_cloud_path(frame)
                if cloud_path.exists():
                    logger.info(
                        "Loading fused cloud for frame %d (%s) ...",
                        frame.output_idx, cloud_path.name,
                    )
                    cloud_xyz = np.asarray(
                        o3d.io.read_point_cloud(str(cloud_path)).points,
                        dtype=np.float64,
                    )
                    logger.info(
                        "Fused cloud loaded: %d points (frame %d)",
                        len(cloud_xyz), frame.output_idx,
                    )
                else:
                    logger.warning(
                        "Fused cloud not found for frame %d: %s", frame.output_idx, cloud_path
                    )
                    cloud_xyz = None
                cloud_loaded = True

            records, counts = transfer_frame_camera(
                ds=ds,
                model=models[camera],
                frame=frame,
                camera=camera,
                detection=detection,
                board=board,
                calib=calib,
                min_confidence=min_confidence,
                fused_cloud_points=cloud_xyz,
            )

            all_records.extend(records)
            total_detected += counts["n_detected"]
            total_direct += counts["n_direct"]
            total_plane_fit += counts["n_plane_fit"]
            total_unrecovered += counts["n_unrecovered"]

            n = counts["n_detected"]
            direct_frac = counts["n_direct"] / n if n > 0 else None
            pf_frac = counts["n_plane_fit"] / n if n > 0 else None

            report_rows.append({
                "frame_idx": frame.output_idx,
                "camera_id": camera,
                "n_detected": counts["n_detected"],
                "n_direct": counts["n_direct"],
                "n_plane_fit": counts["n_plane_fit"],
                "n_unrecovered": counts["n_unrecovered"],
                "direct_fraction": direct_frac,
                "plane_fit_fraction": pf_frac,
            })
            logger.info(
                "  [%s] det=%d direct=%d plane_fit=%d unrec=%d",
                camera, counts["n_detected"], counts["n_direct"],
                counts["n_plane_fit"], counts["n_unrecovered"],
            )

        # Drop fused cloud before loading the next frame to bound memory
        cloud_xyz = None

    # ── Persist corner set ─────────────────────────────────────────────────────
    if all_records:
        frame_idxs  = np.array([r.frame_idx  for r in all_records], dtype=np.int32)
        camera_ids  = np.array([r.camera_id  for r in all_records], dtype=object)
        corner_ids  = np.array([r.corner_id  for r in all_records], dtype=np.int32)
        points      = np.array([r.point_3d   for r in all_records], dtype=np.float32)  # (N,3)
        methods     = np.array([r.method     for r in all_records], dtype=object)
        confidences = np.array([r.confidence for r in all_records], dtype=np.float32)
        pixels      = np.array([r.pixel      for r in all_records], dtype=np.float32)  # (N,2)

        corners_path = out_path / "corners.npz"
        np.savez(
            str(corners_path),
            frame_idx=frame_idxs,
            camera_id=camera_ids,
            corner_id=corner_ids,
            points=points,
            method=methods,
            confidence=confidences,
            pixels=pixels,
        )
        logger.info("Saved %d corners -> %s", len(all_records), corners_path)

        # Schema sidecar
        schema = {
            "description": "AquaMVS transferred ChArUco corners (MVS world frame)",
            "file": "corners.npz",
            "generated_by": "analysis/transfer_corners.py",
            "columns": {
                "frame_idx":  "int32 — output frame index (validation: 1,2,3,4,6,7,8,9)",
                "camera_id":  "str   — camera name (12 depth-bearing cameras)",
                "corner_id":  "int32 — ChArUco corner id (0-87)",
                "points":     "float32 (N,3) — 3-D position in MVS world frame (metres)",
                "method":     "str   — 'direct' (depth back-projection) or 'plane_fit' (fallback)",
                "confidence": "float32 — bilinearly-sampled MVS depth confidence; NaN if unavailable",
                "pixels":     "float32 (N,2) — source 2-D pixel (u, v) on undistorted image",
            },
            "min_confidence_used": min_confidence,
            "total_corners": len(all_records),
        }
        schema_path = out_path / "corners_schema.json"
        with schema_path.open("w") as fh:
            json.dump(schema, fh, indent=2)
        logger.info("Saved schema -> %s", schema_path)
    else:
        logger.warning("No corners were transferred — check data and detection results.")

    # ── Dropout report (XFER-04) ───────────────────────────────────────────────
    headline_rate = (
        total_plane_fit / total_detected if total_detected > 0 else float("nan")
    )

    report = {
        "headline": {
            "total_detected": total_detected,
            "total_direct": total_direct,
            "total_plane_fit": total_plane_fit,
            "total_unrecovered": total_unrecovered,
            "dropout_rate": headline_rate,
            "description": (
                "Fraction of detected corners requiring plane-fit fallback "
                "(depth missing or below min_confidence threshold)"
            ),
        },
        "per_frame_camera": report_rows,
    }

    report_path = out_path / "dropout_report.json"
    with report_path.open("w") as fh:
        json.dump(report, fh, indent=2)
    logger.info("Saved dropout report -> %s", report_path)

    # ── Per-frame/camera dropout table (stdout) ────────────────────────────────
    print()
    print("=== Corner-depth dropout by (frame, camera) ===")
    hdr = (
        f"  {'Frame':>5}  {'Camera':<10}  "
        f"{'Detected':>8}  {'Direct':>6}  {'Plane':>5}  {'Unrec':>5}  {'Dropout%':>8}"
    )
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for row in report_rows:
        if row["n_detected"] == 0:
            continue
        n = row["n_detected"]
        pf_pct = 100.0 * row["n_plane_fit"] / n
        print(
            f"  {row['frame_idx']:>5}  {row['camera_id']:<10}  "
            f"{n:>8}  {row['n_direct']:>6}  {row['n_plane_fit']:>5}  "
            f"{row['n_unrecovered']:>5}  {pf_pct:>7.1f}%"
        )

    print()
    print(
        f"HEADLINE corner-depth dropout: {headline_rate * 100:.1f}% "
        f"(plane-fit fallback over {total_detected} detected corners)"
    )
    print()

    # ── Summary ────────────────────────────────────────────────────────────────
    elapsed = time.time() - t0
    logger.info("transfer_corners complete in %.1f s", elapsed)
    logger.info(
        "Totals: detected=%d  direct=%d  plane_fit=%d  unrecovered=%d",
        total_detected, total_direct, total_plane_fit, total_unrecovered,
    )

    if total_detected == 0:
        logger.error("ZERO corners detected across the entire validation set.")
        sys.exit(1)

    print("=== XFER-02/03/04 PASSED ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "AquaMVS corner transfer — XFER-02/03/04 evidence. "
            "Transfers ChArUco corners to 3-D MVS world points via refractive "
            "depth back-projection and a fused-cloud-slab plane-fit fallback. "
            "Persists corners.npz and dropout_report.json."
        )
    )
    parser.add_argument(
        "--data-root",
        default="data/aquamvs_ground_truth_analysis",
        help="Path to extracted dataset root (default: data/aquamvs_ground_truth_analysis)",
    )
    parser.add_argument(
        "--out-dir",
        default=str(analysis_output_root() / "corner_transfer"),
        help="Output directory for corners and dropout report (default: data/analysis_output/corner_transfer)",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.1,
        help="Minimum depth-confidence for direct back-projection (default: 0.1)",
    )
    args = parser.parse_args()
    main(args.data_root, args.out_dir, args.min_confidence)
