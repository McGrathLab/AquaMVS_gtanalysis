"""
Artifact checker for cross_camera_agreement.json (MET-03).

Validates JSON shape, required keys, and semantic invariants.
Exits with non-zero status and prints a diagnostic if any check fails.

Run:
    python tests/check_cross_camera_artifact.py
    python tests/check_cross_camera_artifact.py --artifact path/to/cross_camera_agreement.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Follow AQUAMVS_GT_OUT so each output root can be checked independently.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis._paths import analysis_output_root  # noqa: E402


DEFAULT_ARTIFACT = (
    analysis_output_root() / "scale_independent_metrics" / "cross_camera_agreement.json"
)


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}", file=sys.stderr)
    sys.exit(1)


def check(condition: bool, msg: str) -> None:
    if not condition:
        fail(msg)


def main(artifact_path: Path) -> None:
    if not artifact_path.exists():
        fail(f"Artifact not found: {artifact_path}")

    with artifact_path.open() as fh:
        data = json.load(fh)

    # ── Top-level keys ────────────────────────────────────────────────────────
    required_top = {
        "metric", "units", "computed_before_alignment",
        "coverage_threshold_min_corners", "min_cameras",
        "per_frame", "overall",
    }
    missing = required_top - set(data.keys())
    check(not missing, f"Missing top-level keys: {missing}")

    # ── Ordering invariant ────────────────────────────────────────────────────
    check(
        data["computed_before_alignment"] is True,
        f"computed_before_alignment must be true, got {data['computed_before_alignment']!r}",
    )

    check(
        data["units"] == "rms in mm",
        f"Expected units='rms in mm', got {data['units']!r}",
    )

    # ── per_frame ─────────────────────────────────────────────────────────────
    per_frame = data["per_frame"]
    check(isinstance(per_frame, list), "per_frame must be a list")
    check(len(per_frame) > 0, "per_frame must not be empty")

    required_frame_keys = {
        "frame_idx", "frame_rms_mm", "n_corners_compared",
        "n_cameras_included", "cameras_included", "cameras_excluded",
        "per_corner_rms_mm",
    }
    for rec in per_frame:
        missing_f = required_frame_keys - set(rec.keys())
        check(
            not missing_f,
            f"Frame {rec.get('frame_idx', '?')} missing keys: {missing_f}",
        )
        check(
            isinstance(rec["frame_idx"], int),
            f"frame_idx must be int, got {type(rec['frame_idx'])}",
        )
        check(
            rec["n_corners_compared"] >= 0,
            f"Frame {rec['frame_idx']}: n_corners_compared must be >= 0",
        )
        check(
            rec["n_cameras_included"] >= 0,
            f"Frame {rec['frame_idx']}: n_cameras_included must be >= 0",
        )
        check(
            isinstance(rec["cameras_included"], list),
            f"Frame {rec['frame_idx']}: cameras_included must be a list",
        )
        check(
            isinstance(rec["cameras_excluded"], dict),
            f"Frame {rec['frame_idx']}: cameras_excluded must be a dict",
        )
        check(
            isinstance(rec["per_corner_rms_mm"], list),
            f"Frame {rec['frame_idx']}: per_corner_rms_mm must be a list",
        )
        # frame_rms_mm: either a positive float or null
        frms = rec["frame_rms_mm"]
        if frms is not None:
            check(
                isinstance(frms, (int, float)) and frms >= 0,
                f"Frame {rec['frame_idx']}: frame_rms_mm must be >= 0, got {frms}",
            )
        # per_corner_rms_mm length matches n_corners_compared
        check(
            len(rec["per_corner_rms_mm"]) == rec["n_corners_compared"],
            f"Frame {rec['frame_idx']}: per_corner_rms_mm length {len(rec['per_corner_rms_mm'])} "
            f"!= n_corners_compared {rec['n_corners_compared']}",
        )

    # ── overall ───────────────────────────────────────────────────────────────
    overall = data["overall"]
    check(isinstance(overall, dict), "overall must be a dict")
    required_overall_keys = {
        "overall_rms_mm", "mean_per_corner_mm", "median_per_corner_mm",
        "range_per_frame_rms_mm", "n_corners_total",
    }
    missing_o = required_overall_keys - set(overall.keys())
    check(not missing_o, f"overall missing keys: {missing_o}")

    orms = overall["overall_rms_mm"]
    check(
        isinstance(orms, (int, float)) and orms >= 0,
        f"overall_rms_mm must be >= 0, got {orms}",
    )

    rng = overall["range_per_frame_rms_mm"]
    check(
        isinstance(rng, list) and len(rng) == 2,
        f"range_per_frame_rms_mm must be a 2-element list, got {rng}",
    )

    check(
        isinstance(overall["n_corners_total"], int) and overall["n_corners_total"] >= 0,
        f"n_corners_total must be a non-negative int, got {overall['n_corners_total']}",
    )

    # ── Sanity: no alignment code ─────────────────────────────────────────────
    # (Cannot check source code from here; instead verify the invariant flag)
    check(
        data["computed_before_alignment"] is True,
        "computed_before_alignment flag must be true",
    )

    print(
        f"[PASS] cross_camera_agreement.json — "
        f"{len(per_frame)} frames, overall_rms={orms:.3f} mm, "
        f"n_corners_total={overall['n_corners_total']}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate cross_camera_agreement.json artifact (MET-03)."
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=DEFAULT_ARTIFACT,
        help=f"Path to JSON artifact (default: {DEFAULT_ARTIFACT})",
    )
    args = parser.parse_args()
    main(args.artifact)
