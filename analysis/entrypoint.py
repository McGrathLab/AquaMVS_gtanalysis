"""
AquaMVS ChArUco Ground-Truth Validation — dataset loader smoke-test and entrypoint.

Prints a structured summary of the dataset: calibration, board spec, frame table,
validation set, depth map availability, and fused cloud paths. Used to confirm
the data environment is correctly set up before running downstream analyses.

Run:
    conda run -n AquaMVS python analysis/entrypoint.py
    conda run -n AquaMVS python analysis/entrypoint.py --data-root /path/to/data
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from the repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import aquamvs
from analysis.loader import (
    GroundTruthDataset,
    DatasetConfig,
    NO_DEPTH_CAMERAS,
)


def _mb(path: Path) -> str:
    """Return file size in MB as a formatted string, or '(not found)' if missing."""
    try:
        size = path.stat().st_size / (1024 ** 2)
        return f"{size:.1f} MB"
    except FileNotFoundError:
        return "(not found)"


def main(data_root: str) -> None:
    """Load the dataset and print a structured summary."""
    config = DatasetConfig(data_root=Path(data_root))
    ds = GroundTruthDataset(config)

    print("=== AquaMVS Ground-Truth Dataset ===")
    print()

    # --- Data root ---
    root = config.data_root
    exists_flag = "EXISTS" if root.exists() else "MISSING"
    print(f"Data root  : {root.resolve()}  [{exists_flag}]")
    print(f"aquamvs    : v{aquamvs.__version__}")
    print()

    # --- Calibration ---
    calib = ds.calibration()
    print("--- Calibration ---")
    print(f"  Cameras ({len(calib.cameras)}):")
    for name, cam in calib.cameras.items():
        role = "auxiliary" if cam.is_auxiliary else "ring"
        fisheye = " fisheye" if cam.is_fisheye else ""
        print(f"    {name:<12}  [{role}{fisheye}]")
    print(f"  n_air    : {calib.n_air}")
    print(f"  n_water  : {calib.n_water}")
    print(f"  water_z  : {calib.water_z:.6f} m")
    print()

    # --- Board spec ---
    spec = ds.board_spec()
    print("--- Board Spec ---")
    print(f"  Squares  : {spec.squares_x} x {spec.squares_y}")
    print(f"  square_size : {spec.square_size * 1000:.1f} mm")
    print(f"  marker_size : {spec.marker_size * 1000:.1f} mm")
    print(f"  Dictionary  : {spec.dict_name}")
    print()

    # --- Frame table ---
    all_frames = ds.all_frames()
    print("--- Frame Summary ---")
    print(f"  {'Idx':>3}  {'Raw':>6}  {'Role':<22}  {'Depth maps':>10}")
    print(f"  {'-'*3}  {'-'*6}  {'-'*22}  {'-'*10}")
    for frame in all_frames:
        role = "calibration-overlap" if frame.is_calibration_overlap else "validation"
        # Count available depth maps (excludes NO_DEPTH_CAMERAS)
        ring_cams = [c for c in calib.cameras if c not in NO_DEPTH_CAMERAS]
        n_depth = sum(
            1 for c in ring_cams if ds.depth_map_path(frame, c) is not None
        )
        print(f"  {frame.output_idx:>3}  {frame.raw_frame_idx:>6}  {role:<22}  {n_depth:>10}")
    print()

    # --- Validation set ---
    val_frames = ds.validation_frames()
    val_indices = [f.output_idx for f in val_frames]
    print("--- Validation Set ---")
    print(f"  Count   : {len(val_frames)}")
    print(f"  Indices : {val_indices}")
    print()

    # --- No-depth cameras ---
    print("--- Cameras with No Depth Map ---")
    print(f"  {sorted(NO_DEPTH_CAMERAS)}")
    print()

    # --- Sample cloud paths ---
    print("--- Sample Fused Cloud Paths ---")
    for frame in [val_frames[0], val_frames[-1]]:
        cloud = ds.fused_cloud_path(frame)
        print(f"  frame {frame.output_idx:02d} (raw {frame.raw_frame_idx}): {cloud}  [{_mb(cloud)}]")
    print()

    # --- Final checks ---
    errors: list[str] = []

    if not root.exists():
        errors.append(f"Data root missing: {root}")
    if len(calib.cameras) != 13:
        errors.append(f"Expected 13 cameras, got {len(calib.cameras)}")
    if len(val_frames) != 8:
        errors.append(f"Expected 8 validation frames, got {len(val_frames)}")
    if spec.squares_x != 12 or spec.squares_y != 9:
        errors.append(f"Unexpected board dimensions: {spec.squares_x}x{spec.squares_y}")
    for frame in [val_frames[0], val_frames[-1]]:
        cloud = ds.fused_cloud_path(frame)
        if not cloud.exists():
            errors.append(f"Missing fused cloud: {cloud}")
    depth_test = ds.load_depth_map(all_frames[0], "e3v8250")
    if depth_test is not None:
        errors.append("e3v8250 load_depth_map should return None, got array")

    if errors:
        print("=== SMOKE TEST FAILED ===")
        for err in errors:
            print(f"  ERROR: {err}")
        sys.exit(1)
    else:
        print("=== SMOKE TEST PASSED ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AquaMVS Ground-Truth Dataset — loader smoke-test and summary"
    )
    parser.add_argument(
        "--data-root",
        default="data/aquamvs_ground_truth_analysis",
        help="Path to extracted dataset root (default: data/aquamvs_ground_truth_analysis)",
    )
    args = parser.parse_args()
    main(args.data_root)
