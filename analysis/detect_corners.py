"""
AquaMVS ChArUco Corner Detection — XFER-01 Evidence CLI
=========================================================
Detects ChArUco corners in each depth-bearing camera's undistorted image
across all 8 validation frames and prints a per-(frame, camera) corner-count
table with per-frame totals and a grand total.

This script is read-only; it writes no files. Its purpose is to demonstrate
XFER-01 on real data: subpixel corners detected on the SAME pixel grid as the
depth maps, ready for back-projection in Plan 02-02.

Run:
    conda run -n AquaMVS python analysis/detect_corners.py
    conda run -n AquaMVS python analysis/detect_corners.py --data-root /path/to/data
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from the repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.loader import GroundTruthDataset, DatasetConfig
from analysis.charuco_detect import (
    build_board_geometry,
    depth_bearing_cameras,
    detect_validation_set,
)


def main(data_root: str) -> None:
    """Run detection over the validation set and print a corner-count table."""
    config = DatasetConfig(data_root=Path(data_root))
    ds = GroundTruthDataset(config)

    spec = ds.board_spec()
    board = build_board_geometry(spec)
    cameras = depth_bearing_cameras(ds)
    frames = ds.validation_frames()

    # --- Board spec (traceability) ---
    print("=== AquaMVS ChArUco Corner Detection (XFER-01) ===")
    print()
    print("Board spec:")
    print(f"  Squares     : {spec.squares_x} x {spec.squares_y}")
    print(f"  square_size : {spec.square_size * 1000:.1f} mm")
    print(f"  Dictionary  : {spec.dict_name}")
    print(f"  Max corners : {board.num_corners}")
    print()

    # --- Run detection ---
    print("Running detection over 8 frames x 12 cameras …")
    detections = detect_validation_set(ds, board=board)
    print()

    # --- Build corner-count table ---
    # Helper: corner count for a (frame_idx, camera) pair
    def count(frame_idx: int, cam: str) -> int:
        det = detections.get((frame_idx, cam))
        return det.num_corners if det is not None else 0

    # Column widths
    cam_col_w = max(len(c) for c in cameras)
    idx_col_w = 6  # "Fr.Idx"

    # Header row
    header = f"  {'Fr.Idx':>{idx_col_w}}  " + "  ".join(
        f"{c:>{cam_col_w}}" for c in cameras
    ) + f"  {'Total':>7}"
    separator = "  " + "-" * (len(header) - 2)

    print("Corner counts per (frame, camera):")
    print(header)
    print(separator)

    grand_total = 0
    for frame in frames:
        row_counts = [count(frame.output_idx, cam) for cam in cameras]
        row_total = sum(row_counts)
        grand_total += row_total
        row_str = f"  {frame.output_idx:>{idx_col_w}}  " + "  ".join(
            f"{n:>{cam_col_w}}" for n in row_counts
        ) + f"  {row_total:>7}"
        print(row_str)

    print(separator)
    # Grand total row (blank frame index, sum of all cells)
    total_row = f"  {'TOTAL':>{idx_col_w}}  " + " " * (
        (cam_col_w + 2) * len(cameras) - 2
    ) + f"  {grand_total:>7}"
    print(total_row)
    print()

    # --- Summary ---
    n_pairs = len(frames) * len(cameras)
    n_detected = len(detections)
    print(
        f"Detections: {n_detected}/{n_pairs} (frame,camera) pairs  |  "
        f"Grand total corners: {grand_total}"
    )
    print()

    if grand_total == 0:
        print("ERROR: ZERO corners detected across the entire validation set.")
        print("       Check that undistorted images are present and AquaCal is installed.")
        sys.exit(1)

    print("=== XFER-01 PASSED ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "AquaMVS ChArUco corner detection — XFER-01 evidence. "
            "Prints a per-(frame,camera) corner-count table over 8 validation frames "
            "x 12 depth-bearing cameras."
        )
    )
    parser.add_argument(
        "--data-root",
        default="data/aquamvs_ground_truth_analysis",
        help="Path to extracted dataset root (default: data/aquamvs_ground_truth_analysis)",
    )
    args = parser.parse_args()
    main(args.data_root)
