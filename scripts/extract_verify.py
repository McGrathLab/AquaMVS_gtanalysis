"""
extract_verify.py — Extract and verify the AquaMVS ground-truth dataset.

Usage:
    python scripts/extract_verify.py [--data-root ./data] [--zip-path C:/Users/tucke/Downloads/aquamvs_ground_truth_analysis.zip]

Stdlib only — no AquaMVS env imports required.
"""
import argparse
import logging
import sys
import zipfile
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DEFAULT_ZIP = "C:/Users/tucke/Downloads/aquamvs_ground_truth_analysis.zip"
DEFAULT_DATA_ROOT = "./data"
DATASET_NAME = "aquamvs_ground_truth_analysis"

NUM_OUTPUT_FRAMES = 10
NUM_DEPTH_NPZ = 12


def parse_args():
    p = argparse.ArgumentParser(description="Extract and verify AquaMVS ground-truth dataset")
    p.add_argument("--data-root", default=DEFAULT_DATA_ROOT, help="Directory into which the zip is extracted")
    p.add_argument("--zip-path", default=DEFAULT_ZIP, help="Path to the source zip file")
    return p.parse_args()


def extract(zip_path: Path, data_root: Path):
    log.info(f"Extracting {zip_path} -> {data_root} (this may take 15-30 min)...")
    data_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(data_root)
    log.info("Extraction complete.")


def manifest_check(root: Path) -> list[str]:
    """Return a list of failure strings; empty list means PASSED."""
    failures = []
    items_checked = 0

    def check_file(path: Path, label: str):
        nonlocal items_checked
        items_checked += 1
        if not path.exists():
            failures.append(f"MISSING: {label} ({path})")
        elif path.stat().st_size == 0:
            failures.append(f"EMPTY: {label} ({path})")

    # Top-level files
    check_file(root / "calibration.json", "calibration.json")
    check_file(root / "config.yaml", "config.yaml")

    # Output frame dirs
    output_dir = root / "output"
    if not output_dir.exists():
        failures.append(f"MISSING: output/ directory ({output_dir})")
        return failures  # can't check further

    frame_dirs = []
    for i in range(NUM_OUTPUT_FRAMES):
        fd = output_dir / f"frame_{i:06d}"
        items_checked += 1
        if not fd.exists():
            failures.append(f"MISSING: output dir frame_{i:06d} ({fd})")
        else:
            frame_dirs.append(fd)

    for fd in frame_dirs:
        label_base = fd.name

        # depth_maps subdir
        dm_dir = fd / "depth_maps"
        items_checked += 1
        if not dm_dir.exists():
            failures.append(f"MISSING: {label_base}/depth_maps/ ({dm_dir})")
        else:
            npz_files = list(dm_dir.glob("*.npz"))
            items_checked += 1
            if len(npz_files) != NUM_DEPTH_NPZ:
                failures.append(
                    f"WRONG COUNT: {label_base}/depth_maps/ has {len(npz_files)} .npz files, expected {NUM_DEPTH_NPZ}"
                )
            else:
                for npz in npz_files:
                    items_checked += 1
                    if npz.stat().st_size == 0:
                        failures.append(f"EMPTY: {label_base}/depth_maps/{npz.name}")

        # point_cloud/fused.ply
        check_file(fd / "point_cloud" / "fused.ply", f"{label_base}/point_cloud/fused.ply")

        # mesh/surface.ply
        check_file(fd / "mesh" / "surface.ply", f"{label_base}/mesh/surface.ply")

    return failures, items_checked


def main():
    args = parse_args()
    zip_path = Path(args.zip_path)
    data_root = Path(args.data_root)
    dataset_root = data_root / DATASET_NAME
    sentinel = dataset_root / "calibration.json"

    # Step 1: Extract if needed
    if sentinel.exists():
        log.info(f"Dataset root already exists at {dataset_root} — skipping extraction.")
    else:
        if not zip_path.exists():
            log.error(f"Source zip not found: {zip_path}")
            sys.exit(1)
        extract(zip_path, data_root)

    # Step 2: Manifest check
    log.info("Running manifest check...")
    result = manifest_check(dataset_root)
    if isinstance(result, tuple):
        failures, items_checked = result
    else:
        failures = result
        items_checked = 0

    if not failures:
        print(f"MANIFEST CHECK PASSED — {items_checked} items verified")
        # Delete zip only after passing check
        if zip_path.exists():
            zip_path.unlink()
            print(f"Source zip deleted: {zip_path}")
        else:
            print(f"Source zip already absent: {zip_path}")
    else:
        print(f"MANIFEST CHECK FAILED — {len(failures)} items missing or empty:")
        for f in failures:
            print(f"  {f}")
        print("Source zip NOT deleted — resolve issues and re-run")
        sys.exit(1)


if __name__ == "__main__":
    main()
