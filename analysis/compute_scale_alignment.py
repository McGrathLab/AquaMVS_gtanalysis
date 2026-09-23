"""
AquaMVS Scale Alignment — MET-04 / MET-05 Consistency-Check CLI (Phase 4)
========================================================================
Aligns the per-frame consensus MVS ChArUco corners to the IDEAL 60 mm planar
board (known one-to-one correspondence by corner_id) and reports:

  MET-05 — Rigid (NO-scale) alignment inlier RMSE (mm), per frame + pooled,
            with an inlier count per frame.

  MET-04 — Absolute scale: the reconstructed square size (mm) and the
            Umeyama-with-scale factor (+ %), per frame + pooled, EXPLICITLY
            labelled a consistency check.

ORDERING INVARIANT (enforced at runtime)
----------------------------------------
This script runs AFTER the Phase 3 scale-independent headline. Before computing
anything it ASSERTS the two Phase 3 artifacts exist and carry
"computed_before_alignment": true, then sys.exit(1) if not. It writes ONLY
data/analysis_output/scale_alignment.json (+ schema sidecar) on a path SEPARATE
from scale_independent_metrics/, and NEVER opens the Phase 3 artifacts for writing.

HONEST FRAMING (embedded in the artifact `note` block)
------------------------------------------------------
The 60 mm ChArUco square is the calibration scale anchor — a system INPUT that
set the scale — so recovering ~60 mm / scale~1 is PARTLY CIRCULAR. The scale
result is contextualised against the Maas (2015) factor-of-two refractive
precision penalty. The "0.5 % of dimension" misread is banned and appears nowhere.

Run
---
    conda run -n AquaMVS python analysis/compute_scale_alignment.py
    conda run -n AquaMVS python analysis/compute_scale_alignment.py \\
        --corners data/analysis_output/corner_transfer/corners.npz \\
        --data-root data/aquamvs_ground_truth_analysis \\
        --out data/analysis_output/scale_alignment.json
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from pathlib import Path

# Allow running from the repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis._paths import analysis_output_root  # noqa: E402

import numpy as np

from analysis.loader import GroundTruthDataset, DatasetConfig
from analysis.charuco_detect import build_board_geometry
from analysis.cross_camera import load_corners
from analysis.flatness import board_size_from_corners
from analysis.alignment import (
    build_consensus_corners,
    ideal_board_corners,
    matched_arrays,
    rigid_inlier_fit,
    umeyama_fit,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Phase 3 artifacts (READ-ONLY for Phase 4). Their existence + ordering flag is
# the runtime guard that proves Phase 4 runs AFTER Phase 3.
# Follows AQUAMVS_GT_OUT so an alternative run is guarded by its OWN Phase 3.
PHASE3_DIR = analysis_output_root() / "scale_independent_metrics"
PHASE3_ARTIFACTS = (
    "flatness_consistency.json",
    "cross_camera_agreement.json",
)

# Outlier rule used by MET-05 rigid_inlier_fit (documented in the artifact).
OUTLIER_RULE = {
    "abs_thresh_mm": 5.0,
    "mad_k": 3.0,
    "min_inliers": 3,
    "description": (
        "Rigid (no-scale) fit on all matched corners, reject corners with residual "
        "> max(abs_thresh_mm, median + mad_k*MAD), then refit on the inliers."
    ),
}


def _ordering_invariant_guard() -> None:
    """Assert Phase 3 ran first; refuse (exit 1) otherwise. Never opens for write."""
    for name in PHASE3_ARTIFACTS:
        path = PHASE3_DIR / name
        if not path.exists():
            logger.error(
                "Phase 4 must run AFTER Phase 3 scale-independent metrics: missing %s",
                path,
            )
            sys.exit(1)
        with path.open("r") as fh:
            data = json.load(fh)
        if data.get("computed_before_alignment") is not True:
            logger.error(
                "Phase 4 must run AFTER Phase 3: %s lacks computed_before_alignment=true",
                path,
            )
            sys.exit(1)
    logger.info("Ordering invariant OK: Phase 3 artifacts present and locked.")


def main(corners_path: str, data_root: str, out: str) -> None:
    t0 = time.time()

    # ── 1. Ordering-invariant guard ───────────────────────────────────────────
    _ordering_invariant_guard()

    # ── 2. Load cleaned corners (Z>0 gated already; defensive gate below too) ──
    logger.info("Loading corners from %s", corners_path)
    corners = load_corners(corners_path)
    frame_idx = corners["frame_idx"]
    camera_id = corners["camera_id"]
    corner_id = corners["corner_id"]
    points = corners["points"].astype(np.float64)
    logger.info("Loaded %d corner rows", len(frame_idx))

    # ── 3. Ideal board (built once) ───────────────────────────────────────────
    config = DatasetConfig(data_root=Path(data_root))
    ds = GroundTruthDataset(config)
    board_spec = ds.board_spec()
    board = build_board_geometry(board_spec)
    ideal_all = ideal_board_corners(board)
    logger.info("Ideal board corners: %s (board-local metres, z=0)", ideal_all.shape)

    unique_frames = sorted(set(int(f) for f in frame_idx))
    logger.info("Frames in data: %s", unique_frames)

    # ── 4. Per-frame alignment sweep ──────────────────────────────────────────
    per_frame: list[dict] = []
    pooled_inlier_residual_sq_mm: list[float] = []  # accumulate for pooled RMSE

    for frame in unique_frames:
        consensus = build_consensus_corners(
            frame_idx, camera_id, corner_id, points, frame
        )
        if len(consensus) < 3:
            logger.warning("Frame %d: < 3 consensus corners — skipping", frame)
            per_frame.append({
                "frame_idx": frame,
                "skipped_reason": f"too few consensus corners ({len(consensus)} < 3)",
                "rigid_rms_mm": None,
                "n_inliers": 0,
                "n_corners": len(consensus),
                "scale_factor": None,
                "scale_error": None,
                "scale_error_pct": None,
                "board_size_mm": None,
            })
            continue

        ids, src_ideal, dst_consensus = matched_arrays(consensus, ideal_all)

        # MET-05: rigid (no-scale) inlier RMSE
        rigid = rigid_inlier_fit(
            src_ideal, dst_consensus,
            abs_thresh_mm=OUTLIER_RULE["abs_thresh_mm"],
            mad_k=OUTLIER_RULE["mad_k"],
            min_inliers=OUTLIER_RULE["min_inliers"],
        )
        inlier_mask = rigid["inlier_mask"]

        # MET-04 estimator (b): Umeyama-with-scale on the SAME inlier set
        scaled = umeyama_fit(
            src_ideal[inlier_mask], dst_consensus[inlier_mask], with_scale=True
        )
        scale_factor = scaled["s"]
        scale_error = scale_factor - 1.0
        scale_error_pct = scale_error * 100.0

        # MET-04 estimator (a): reconstructed square size from the SAME matched
        # consensus points (median inter-corner spacing in mm)
        size_res = board_size_from_corners(ids, dst_consensus, board_spec)
        board_size_mm = size_res["size_mm"]

        # Accumulate inlier squared residuals (mm) for the pooled rigid RMSE
        refit_inlier = umeyama_fit(
            src_ideal[inlier_mask], dst_consensus[inlier_mask], with_scale=False
        )
        pooled_inlier_residual_sq_mm.extend(
            (refit_inlier["per_corner_residual_mm"] ** 2).tolist()
        )

        rec = {
            "frame_idx": frame,
            "rigid_rms_mm": float(rigid["rms_mm"]) if np.isfinite(rigid["rms_mm"]) else None,
            "n_inliers": int(rigid["n_inliers"]),
            "n_corners": int(len(ids)),
            "scale_factor": float(scale_factor) if np.isfinite(scale_factor) else None,
            "scale_error": float(scale_error) if np.isfinite(scale_error) else None,
            "scale_error_pct": float(scale_error_pct) if np.isfinite(scale_error_pct) else None,
            "board_size_mm": float(board_size_mm) if math.isfinite(board_size_mm) else None,
            "degenerate": bool(rigid["degenerate"]),
        }
        per_frame.append(rec)

        logger.info(
            "Frame %d: corners=%d inliers=%d rigid_rms=%.3f mm scale=%.5f (%.3f%%) size=%.3f mm",
            frame, rec["n_corners"], rec["n_inliers"],
            rec["rigid_rms_mm"] if rec["rigid_rms_mm"] is not None else float("nan"),
            rec["scale_factor"] if rec["scale_factor"] is not None else float("nan"),
            rec["scale_error_pct"] if rec["scale_error_pct"] is not None else float("nan"),
            rec["board_size_mm"] if rec["board_size_mm"] is not None else float("nan"),
        )

    # ── 5. Pooled summary ─────────────────────────────────────────────────────
    valid = [r for r in per_frame if r.get("rigid_rms_mm") is not None]

    if pooled_inlier_residual_sq_mm:
        pooled_rigid_rms_mm = float(
            math.sqrt(sum(pooled_inlier_residual_sq_mm) / len(pooled_inlier_residual_sq_mm))
        )
    else:
        pooled_rigid_rms_mm = None

    def _stats(key: str) -> dict:
        vals = [r[key] for r in valid if r.get(key) is not None]
        if not vals:
            return {"mean": None, "min": None, "max": None}
        return {
            "mean": float(np.mean(vals)),
            "min": float(np.min(vals)),
            "max": float(np.max(vals)),
        }

    scale_stats = _stats("scale_factor")
    scale_pct_stats = _stats("scale_error_pct")
    size_stats = _stats("board_size_mm")

    pooled = {
        "rigid_rms_mm_pooled": pooled_rigid_rms_mm,
        "n_inlier_residuals": len(pooled_inlier_residual_sq_mm),
        "n_frames": len(valid),
        "scale_factor_mean": scale_stats["mean"],
        "scale_factor_min": scale_stats["min"],
        "scale_factor_max": scale_stats["max"],
        "scale_error_pct_mean": scale_pct_stats["mean"],
        "scale_error_pct_min": scale_pct_stats["min"],
        "scale_error_pct_max": scale_pct_stats["max"],
        "board_size_mm_mean": size_stats["mean"],
        "board_size_mm_min": size_stats["min"],
        "board_size_mm_max": size_stats["max"],
    }

    # ── 6. Machine-readable honest-framing note (REQUIRED) ────────────────────
    note = {
        "circularity_caveat": (
            "The 60 mm ChArUco square size is the calibration scale anchor (a system "
            "INPUT that set the scale), not an output. Reconstructing the board and "
            "recovering ~60 mm / scale~1 is therefore PARTLY CIRCULAR: near-zero scale "
            "error is partly true by construction. Reported as a consistency check AFTER "
            "the scale-independent headline (Phase 3: flatness 1.09 mm, cross-camera "
            "3.46 mm), never as the headline."
        ),
        "maas_2015_context": (
            "Refractive (through-water) reconstruction carries a precision penalty of "
            "approximately a FACTOR OF TWO relative to in-air (Maas 2015). The scale/RMSE "
            "numbers here should be read against that factor-of-two benchmark."
        ),
        "scale_independent_headline_first": True,
    }

    # ── 7. Build + persist artifact ───────────────────────────────────────────
    artifact = {
        "metric": (
            "MET-04 absolute scale (consistency check) + "
            "MET-05 rigid alignment inlier RMSE"
        ),
        "units": (
            "rms/board_size in mm, scale_factor dimensionless, scale_error_pct in %"
        ),
        "computed_after_alignment": True,
        "ordering_invariant": (
            "Computed AFTER Phase 3 scale-independent metrics; does not modify them."
        ),
        "outlier_rule": OUTLIER_RULE,
        "per_frame": per_frame,
        "pooled": pooled,
        "note": note,
    }

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        json.dump(artifact, fh, indent=2)
    logger.info("Saved artifact -> %s", out_path)

    # Schema sidecar
    schema = {
        "description": "Schema for scale_alignment.json (MET-04 + MET-05, Phase 4)",
        "generated_by": "analysis/compute_scale_alignment.py",
        "ordering_invariant": (
            "Computed AFTER Phase 3 scale-independent metrics; Phase 3 artifacts are "
            "byte-identical before/after this run; this file lands on the separate "
            "data/analysis_output path (NOT scale_independent_metrics/)."
        ),
        "fields": {
            "metric": "str — metric identifiers (MET-04 + MET-05)",
            "units": "str — unit conventions for the reported numbers",
            "computed_after_alignment": (
                "bool — always true; these are the Phase 4 'after alignment' numbers"
            ),
            "ordering_invariant": "str — ordering guarantee vs Phase 3",
            "outlier_rule": {
                "abs_thresh_mm": "float — absolute residual floor (mm) for inlier keep",
                "mad_k": "float — MAD multiplier for the robust (median + k*MAD) cutoff",
                "min_inliers": "int — minimum inliers for a non-degenerate refit",
                "description": "str — human-readable outlier-rejection summary",
            },
            "per_frame": {
                "type": "list[dict]",
                "fields": {
                    "frame_idx": "int — output frame index (validation: 1,2,3,4,6,7,8,9)",
                    "rigid_rms_mm": "float|null — MET-05 rigid (no-scale) inlier RMSE (mm)",
                    "n_inliers": "int — inlier corner count used for the rigid refit",
                    "n_corners": "int — matched consensus corners for this frame",
                    "scale_factor": "float|null — MET-04 Umeyama-with-scale ratio (reconstructed/ideal)",
                    "scale_error": "float|null — scale_factor - 1 (dimensionless)",
                    "scale_error_pct": "float|null — scale_error * 100 (%)",
                    "board_size_mm": "float|null — MET-04 reconstructed square size (median inter-corner spacing, mm)",
                    "degenerate": "bool — True if inlier rejection fell back to the all-corner fit",
                    "skipped_reason": "str (only if skipped) — reason the frame was skipped",
                },
            },
            "pooled": {
                "rigid_rms_mm_pooled": "float|null — pooled RMSE from all inlier residuals across frames (mm)",
                "n_inlier_residuals": "int — total inlier residuals pooled",
                "n_frames": "int — frames with a valid rigid fit",
                "scale_factor_mean/min/max": "float|null — pooled scale-factor stats",
                "scale_error_pct_mean/min/max": "float|null — pooled scale-error stats (%)",
                "board_size_mm_mean/min/max": "float|null — pooled reconstructed-size stats (mm)",
            },
            "note": {
                "circularity_caveat": "str — states the 60 mm anchor circularity; headline-first",
                "maas_2015_context": "str — factor-of-two refractive precision benchmark (Maas 2015)",
                "scale_independent_headline_first": "bool — always true",
            },
        },
    }
    schema_path = out_path.parent / "scale_alignment_schema.json"
    with schema_path.open("w") as fh:
        json.dump(schema, fh, indent=2)
    logger.info("Saved schema -> %s", schema_path)

    # ── 8. Stdout table ───────────────────────────────────────────────────────
    print()
    print("=== MET-04 / MET-05: Scale Alignment Consistency Check (Phase 4) ===")
    print()
    hdr = (
        f"  {'Frame':>5}  {'Corners':>7}  {'Inliers':>7}  {'Rigid RMSE(mm)':>14}  "
        f"{'Scale factor':>12}  {'Scale err %':>11}  {'Size(mm)':>8}"
    )
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for rec in per_frame:
        if rec.get("skipped_reason"):
            print(f"  {rec['frame_idx']:>5}  SKIPPED — {rec['skipped_reason']}")
            continue
        print(
            f"  {rec['frame_idx']:>5}  {rec['n_corners']:>7}  {rec['n_inliers']:>7}  "
            f"{rec['rigid_rms_mm']:>14.3f}  {rec['scale_factor']:>12.5f}  "
            f"{rec['scale_error_pct']:>11.3f}  {rec['board_size_mm']:>8.3f}"
        )

    print()
    if pooled_rigid_rms_mm is not None:
        print(
            f"  POOLED rigid inlier RMSE (MET-05): {pooled_rigid_rms_mm:.3f} mm  "
            f"(n_inliers={len(pooled_inlier_residual_sq_mm)}, frames={len(valid)})"
        )
    if scale_pct_stats["mean"] is not None:
        print(
            f"  Scale (MET-04): factor mean={scale_stats['mean']:.5f}  "
            f"error mean={scale_pct_stats['mean']:.3f}%  "
            f"size mean={size_stats['mean']:.3f} mm"
        )
    print()
    print(
        "  CONSISTENCY CHECK ONLY: the 60 mm square is the calibration scale anchor, so "
        "near-zero scale error is PARTLY CIRCULAR. Reported AFTER the Phase 3 "
        "scale-independent headline and read against the Maas (2015) factor-of-two "
        "refractive precision benchmark."
    )
    print()

    elapsed = time.time() - t0
    logger.info("compute_scale_alignment complete in %.1f s", elapsed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "AquaMVS scale alignment consistency check (MET-04 + MET-05). Aligns "
            "per-frame consensus MVS corners to the ideal 60 mm board and reports "
            "rigid inlier RMSE + absolute scale, per frame and pooled. Runs AFTER "
            "Phase 3 (guarded) and writes a separate artifact."
        )
    )
    parser.add_argument(
        "--corners",
        default=str(analysis_output_root() / "corner_transfer/corners.npz"),
        help="Path to Phase-2 corners.npz (default: data/analysis_output/corner_transfer/corners.npz)",
    )
    parser.add_argument(
        "--data-root",
        default="data/aquamvs_ground_truth_analysis",
        help="Path to extracted dataset root (default: data/aquamvs_ground_truth_analysis)",
    )
    parser.add_argument(
        "--out",
        default=str(analysis_output_root() / "scale_alignment.json"),
        help=(
            "Output JSON path (default: data/analysis_output/scale_alignment.json) — "
            "NOTE: top-level analysis_output, NOT scale_independent_metrics/"
        ),
    )
    args = parser.parse_args()
    main(args.corners, args.data_root, args.out)
