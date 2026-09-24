"""
AquaMVS Cross-Camera Agreement — MET-03 Evidence CLI
=====================================================
Sweeps Phase-2 transferred corners (corners.npz) to produce MET-03:
per-frame and overall cross-camera board-localization agreement (RMS in mm).

For each (frame_idx, corner_id) co-observed by >= 2 included depth cameras,
the 3-D positions each camera independently places that corner at are compared.
Dispersion = RMS distance to the per-camera centroid, in mm.

ORDERING INVARIANT: computed in the RAW MVS reconstruction frame BEFORE any
rigid alignment, scale calibration, Umeyama, or ICP (Phase 4).
A camera that sees no board corners in a given frame is a non-event, not an
error — board-blind cameras are never counted as agreement failures.

Outputs
-------
  <out-dir>/cross_camera_agreement.json        — reloadable per-frame + overall artifact
  <out-dir>/cross_camera_agreement_schema.json — field descriptions

Run
---
    python analysis/compute_cross_camera.py
    python analysis/compute_cross_camera.py \\
        --corners data/analysis_output/corner_transfer/corners.npz \\
        --out-dir data/analysis_output/scale_independent_metrics \\
        --min-corners 6 --min-cameras 2
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis._paths import analysis_output_root  # noqa: E402

import numpy as np

from analysis.cross_camera import (
    frame_agreement,
    included_cameras,
    load_corners,
    per_camera_coverage,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main(
    corners_path: str,
    out_dir: str,
    min_corners: int,
    min_cameras: int,
) -> None:
    t0 = time.time()

    # ── Load corners ──────────────────────────────────────────────────────────
    logger.info("Loading corners from %s", corners_path)
    corners = load_corners(corners_path)
    n_total = len(corners["frame_idx"])
    logger.info("Loaded %d corner rows", n_total)

    frame_idx_arr = corners["frame_idx"]
    camera_id_arr = corners["camera_id"]
    corner_id_arr = corners["corner_id"]
    points_arr    = corners["points"]

    unique_frames = sorted(set(int(f) for f in frame_idx_arr))
    logger.info(
        "Frames in data: %s  |  min_corners=%d  min_cameras=%d",
        unique_frames, min_corners, min_cameras,
    )

    # ── Per-frame sweep ───────────────────────────────────────────────────────
    per_frame_records: list[dict] = []
    all_per_corner_rms: list[float] = []  # accumulate for overall pooled RMS

    for frame in unique_frames:
        frame_mask = frame_idx_arr == frame
        cam_f   = camera_id_arr[frame_mask]
        cid_f   = corner_id_arr[frame_mask]
        pts_f   = points_arr[frame_mask]

        # Coverage and filtering
        cov = per_camera_coverage(frame_idx_arr, camera_id_arr, frame)
        inc, exc = included_cameras(cov, min_corners)

        corners_for_frame = {
            "camera_id": cam_f,
            "corner_id": cid_f,
            "points":    pts_f,
        }
        result = frame_agreement(corners_for_frame, included_cams=inc, min_cameras=min_cameras)

        # Accumulate per-corner RMS values for pooled overall calculation
        all_per_corner_rms.extend(result["per_corner_rms_mm"])

        rec = {
            "frame_idx":           frame,
            "frame_rms_mm":        result["frame_rms_mm"] if not math.isnan(result["frame_rms_mm"]) else None,
            "n_corners_compared":  result["n_corners_compared"],
            "n_cameras_included":  result["n_cameras_included"],
            "mean_per_corner_mm":  result["mean_per_corner_mm"] if not math.isnan(result["mean_per_corner_mm"]) else None,
            "median_per_corner_mm": result["median_per_corner_mm"] if not math.isnan(result["median_per_corner_mm"]) else None,
            "cameras_included":    sorted(inc),
            "cameras_excluded":    exc,
            "per_corner_rms_mm":   result["per_corner_rms_mm"],
        }
        per_frame_records.append(rec)

        logger.info(
            "Frame %d: n_cam_inc=%d n_corners=%d frame_rms=%.3f mm  exc=%s",
            frame,
            result["n_cameras_included"],
            result["n_corners_compared"],
            result["frame_rms_mm"] if not math.isnan(result["frame_rms_mm"]) else float("nan"),
            exc,
        )

    # ── Overall aggregate ─────────────────────────────────────────────────────
    if all_per_corner_rms:
        arr = np.array(all_per_corner_rms)
        overall_rms = float(np.sqrt(np.mean(arr ** 2)))
        overall_mean = float(np.mean(arr))
        overall_median = float(np.median(arr))
        overall_min = float(np.min(arr))
        overall_max = float(np.max(arr))
    else:
        overall_rms = float("nan")
        overall_mean = float("nan")
        overall_median = float("nan")
        overall_min = float("nan")
        overall_max = float("nan")

    # Range of per-frame frame_rms_mm
    frame_rms_values = [
        r["frame_rms_mm"] for r in per_frame_records if r["frame_rms_mm"] is not None
    ]
    frame_rms_range = (
        [float(min(frame_rms_values)), float(max(frame_rms_values))]
        if frame_rms_values
        else [None, None]
    )

    overall = {
        "overall_rms_mm":       overall_rms,
        "mean_per_corner_mm":   overall_mean,
        "median_per_corner_mm": overall_median,
        "range_per_frame_rms_mm": frame_rms_range,
        "n_corners_total":      len(all_per_corner_rms),
        "description": (
            "Pooled RMS computed from all per-corner rms_mm values across all frames "
            "(not a mean-of-frame-means); a low value means cameras agree on corner placement."
        ),
    }

    # ── Persist artifact ──────────────────────────────────────────────────────
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    artifact = {
        "metric":                        "MET-03 cross-camera board-localization agreement",
        "units":                         "rms in mm",
        "computed_before_alignment":     True,
        "coverage_threshold_min_corners": min_corners,
        "min_cameras":                   min_cameras,
        "per_frame":                     per_frame_records,
        "overall":                       overall,
    }

    artifact_path = out_path / "cross_camera_agreement.json"
    with artifact_path.open("w") as fh:
        json.dump(artifact, fh, indent=2)
    logger.info("Saved artifact -> %s", artifact_path)

    # Schema sidecar
    schema = {
        "description": "Schema for cross_camera_agreement.json (MET-03)",
        "generated_by": "analysis/compute_cross_camera.py",
        "fields": {
            "metric":   "str — metric identifier",
            "units":    "str — 'rms in mm'",
            "computed_before_alignment": (
                "bool — always true; no Umeyama/ICP/scaling applied before these numbers"
            ),
            "coverage_threshold_min_corners": (
                "int — a camera must contribute >= this many corners in a frame to be included"
            ),
            "min_cameras": (
                "int — a corner_id must be co-observed by >= this many included cameras to be compared"
            ),
            "per_frame": {
                "type": "list[dict]",
                "fields": {
                    "frame_idx":           "int — output frame index (validation: 1,2,3,4,6,7,8,9)",
                    "frame_rms_mm":        "float|null — RMS of per-corner rms_mm for this frame (mm); null if no co-observed corners",
                    "n_corners_compared":  "int — number of corner_ids co-observed by >= min_cameras included cameras",
                    "n_cameras_included":  "int — number of cameras meeting coverage threshold",
                    "mean_per_corner_mm":  "float|null — mean of per-corner rms_mm (mm)",
                    "median_per_corner_mm":"float|null — median of per-corner rms_mm (mm)",
                    "cameras_included":    "list[str] — camera ids that met the coverage threshold",
                    "cameras_excluded":    "dict[str,int] — camera ids below threshold with their corner counts",
                    "per_corner_rms_mm":   "list[float] — per-corner rms_mm values (mm); Phase 5 distribution input",
                },
            },
            "overall": {
                "overall_rms_mm":         "float — pooled RMS from all per-corner rms_mm across all frames (mm)",
                "mean_per_corner_mm":     "float — pooled mean",
                "median_per_corner_mm":   "float — pooled median",
                "range_per_frame_rms_mm": "list[float,float] — [min, max] of per-frame frame_rms_mm",
                "n_corners_total":        "int — total number of co-observed (frame,corner) pairs pooled",
            },
        },
    }

    schema_path = out_path / "cross_camera_agreement_schema.json"
    with schema_path.open("w") as fh:
        json.dump(schema, fh, indent=2)
    logger.info("Saved schema -> %s", schema_path)

    # ── Stdout table ──────────────────────────────────────────────────────────
    print()
    print("=== MET-03  Cross-Camera Board-Localization Agreement ===")
    print()
    hdr = f"  {'Frame':>5}  {'Cams':>4}  {'Corners':>7}  {'RMS (mm)':>8}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for rec in per_frame_records:
        rms_str = f"{rec['frame_rms_mm']:.3f}" if rec["frame_rms_mm"] is not None else "   N/A"
        print(
            f"  {rec['frame_idx']:>5}  {rec['n_cameras_included']:>4}  "
            f"{rec['n_corners_compared']:>7}  {rms_str:>8}"
        )

    print()
    print(f"  OVERALL RMS (pooled): {overall_rms:.3f} mm  "
          f"(mean {overall_mean:.3f} mm, median {overall_median:.3f} mm, "
          f"n_corners={len(all_per_corner_rms)})")
    print()

    # Excluded-cameras audit (rig-fact auditability)
    print("  Coverage-threshold exclusions per frame (min_corners=%d):" % min_corners)
    any_excluded = False
    for rec in per_frame_records:
        exc = rec["cameras_excluded"]
        if exc:
            exc_str = ", ".join(f"{cam}({cnt})" for cam, cnt in sorted(exc.items()))
            print(f"    Frame {rec['frame_idx']}: excluded {exc_str}")
            any_excluded = True
    if not any_excluded:
        print("    (none — all cameras met the coverage threshold in every frame)")

    print()
    print(
        "Computed in RAW MVS frame BEFORE any alignment/scaling (MET-03); "
        "board-blind cameras are not errors."
    )
    print()

    elapsed = time.time() - t0
    logger.info("compute_cross_camera complete in %.1f s", elapsed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "AquaMVS cross-camera board-localization agreement (MET-03). "
            "Sweeps Phase-2 corners.npz and reports per-frame + overall cross-camera "
            "dispersion (RMS mm) computed in the raw MVS frame, before any alignment."
        )
    )
    parser.add_argument(
        "--corners",
        default=str(analysis_output_root() / "corner_transfer/corners.npz"),
        help="Path to corners.npz (default: data/analysis_output/corner_transfer/corners.npz)",
    )
    parser.add_argument(
        "--out-dir",
        default=str(analysis_output_root() / "scale_independent_metrics"),
        help="Output directory for JSON artifacts (default: data/analysis_output/scale_independent_metrics)",
    )
    parser.add_argument(
        "--min-corners",
        type=int,
        default=6,
        help="Coverage threshold: min corners a camera must contribute per frame to be included (default: 6)",
    )
    parser.add_argument(
        "--min-cameras",
        type=int,
        default=2,
        help="Min included cameras for a corner_id to be co-observed and compared (default: 2)",
    )
    args = parser.parse_args()
    main(args.corners, args.out_dir, args.min_corners, args.min_cameras)
