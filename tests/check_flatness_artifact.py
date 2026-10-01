"""
Artifact shape checker for data/analysis_output/scale_independent_metrics/flatness_consistency.json.

Verifies:
  - "computed_before_alignment" is True
  - "per_frame" has exactly 8 records keyed by frame_idx (1,2,3,4,6,7,8,9)
  - Each record has a flatness_rms_mm in a plausible range (0.05–20 mm) OR a skipped_reason
  - "pooled" block has flatness_rms_mm_pooled
  - "variation" block has board_size_cv and per_frame_arrays

Exits 0 on pass, 1 on failure.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

# Follow AQUAMVS_GT_OUT so each output root can be checked independently.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis._paths import analysis_output_root  # noqa: E402

ARTIFACT_PATH = analysis_output_root() / "scale_independent_metrics" / "flatness_consistency.json"
EXPECTED_FRAME_IDXS = {1, 2, 3, 4, 6, 7, 8, 9}
PLAUSIBLE_MIN_MM = 0.05
PLAUSIBLE_MAX_MM = 20.0


def check(condition: bool, message: str) -> None:
    if not condition:
        print(f"FAIL: {message}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    if not ARTIFACT_PATH.exists():
        print(f"FAIL: artifact not found at {ARTIFACT_PATH}", file=sys.stderr)
        sys.exit(1)

    with ARTIFACT_PATH.open() as fh:
        data = json.load(fh)

    # ── Top-level keys ────────────────────────────────────────────────────────
    check("computed_before_alignment" in data,
          "missing key: computed_before_alignment")
    check(data["computed_before_alignment"] is True,
          f"computed_before_alignment must be True, got {data['computed_before_alignment']!r}")
    check("per_frame" in data, "missing key: per_frame")
    check("pooled" in data, "missing key: pooled")
    check("variation" in data, "missing key: variation")
    check("slab_thickness_m" in data, "missing key: slab_thickness_m")

    # ── per_frame records ─────────────────────────────────────────────────────
    per_frame = data["per_frame"]
    check(isinstance(per_frame, list), "per_frame must be a list")
    check(len(per_frame) == 8,
          f"per_frame must have exactly 8 records, got {len(per_frame)}")

    frame_idxs_found = set()
    for rec in per_frame:
        check("frame_idx" in rec, f"record missing frame_idx: {rec}")
        fidx = rec["frame_idx"]
        check(fidx in EXPECTED_FRAME_IDXS,
              f"unexpected frame_idx {fidx!r}; expected one of {EXPECTED_FRAME_IDXS}")
        frame_idxs_found.add(fidx)

        # Either the frame was processed (has flatness_rms_mm) or skipped
        if "skipped_reason" in rec and rec["skipped_reason"]:
            # Skipped frame: flatness_rms_mm should be absent or None
            rms = rec.get("flatness_rms_mm")
            check(rms is None,
                  f"frame {fidx} skipped but flatness_rms_mm={rms!r} (expected None)")
        else:
            # Processed frame: check required fields and plausibility
            check("flatness_rms_mm" in rec,
                  f"frame {fidx} missing flatness_rms_mm")
            rms = rec["flatness_rms_mm"]
            check(rms is not None,
                  f"frame {fidx}: flatness_rms_mm is None for non-skipped frame")
            check(isinstance(rms, (int, float)) and math.isfinite(rms),
                  f"frame {fidx}: flatness_rms_mm={rms!r} is not a finite number")
            check(PLAUSIBLE_MIN_MM <= rms <= PLAUSIBLE_MAX_MM,
                  f"frame {fidx}: flatness_rms_mm={rms:.4f} mm outside plausible range "
                  f"[{PLAUSIBLE_MIN_MM}, {PLAUSIBLE_MAX_MM}] mm")
            check("n_slab_points" in rec, f"frame {fidx} missing n_slab_points")
            check("n_inliers" in rec, f"frame {fidx} missing n_inliers")
            check("depth_m" in rec, f"frame {fidx} missing depth_m")
            check("tilt_deg" in rec, f"frame {fidx} missing tilt_deg")

    check(frame_idxs_found == EXPECTED_FRAME_IDXS,
          f"frame_idxs found {frame_idxs_found} != expected {EXPECTED_FRAME_IDXS}")

    # ── pooled block ──────────────────────────────────────────────────────────
    pooled = data["pooled"]
    check("flatness_rms_mm_pooled" in pooled,
          "pooled block missing flatness_rms_mm_pooled")
    check("n_frames_with_flatness" in pooled,
          "pooled block missing n_frames_with_flatness")

    pooled_rms = pooled["flatness_rms_mm_pooled"]
    if pooled_rms is not None:
        check(isinstance(pooled_rms, (int, float)) and math.isfinite(pooled_rms),
              f"pooled flatness_rms_mm_pooled={pooled_rms!r} is not finite")
        check(PLAUSIBLE_MIN_MM <= pooled_rms <= PLAUSIBLE_MAX_MM,
              f"pooled flatness_rms_mm_pooled={pooled_rms:.4f} mm outside plausible range")

    # ── variation block ───────────────────────────────────────────────────────
    variation = data["variation"]
    check("board_size_cv" in variation, "variation block missing board_size_cv")
    check("per_frame_arrays" in variation, "variation block missing per_frame_arrays")

    arrays = variation["per_frame_arrays"]
    for key in ("frame_idx", "depth_m", "tilt_deg", "flatness_rms_mm", "board_size_mm"):
        check(key in arrays, f"per_frame_arrays missing key: {key}")
        check(len(arrays[key]) == 8,
              f"per_frame_arrays[{key!r}] has {len(arrays[key])} entries, expected 8")

    print("check_flatness_artifact OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
