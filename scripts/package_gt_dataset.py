"""
Stage and zip the ground-truth dataset's Zenodo version 2.0.0 (concept 10.5281/zenodo.21134748).

Each zip extracts at the repository root into the paths this repository already uses, so
the published archive and a local re-run are laid out identically:

  aquamvs-gt-core.zip               inputs, analysis outputs, result tables, fish readouts
  aquamvs-gt-run-refractive.zip     data/runs/modern_refractive
  aquamvs-gt-run-pinhole_B.zip      data/runs/modern_pinhole_B
  aquamvs-gt-run-lightglue.zip      data/runs/modern_lightglue
  aquamvs-gt-run-matchfilt.zip      data/runs/modern_{refractive,lightglue}_matchfilt

Run directories carry, per frame, what the analysis and figures read: depth_maps/,
point_cloud/, undistorted/ and mesh/. The matched-filter runs own only their filtered
depth maps; their other per-frame folders are relative symlinks into the source run, as in
a local run (extract the source run's zip too). Pinhole A ships as its calibration, config
and analysis outputs only: its reconstruction is reproducible from those (README section 2).

Files are hard-linked into the staging tree (same filesystem), not copied.

Usage:
    python scripts/package_gt_dataset.py <staging dir>
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
FRAME_SUBDIRS = ("depth_maps", "point_cloud", "undistorted", "mesh")
FULL_RUNS = {"refractive": "modern_refractive", "pinhole_B": "modern_pinhole_B",
             "lightglue": "modern_lightglue"}
MATCHFILT_RUNS = {"modern_refractive_matchfilt": "modern_refractive",
                  "modern_lightglue_matchfilt": "modern_lightglue"}
ANALYSIS_RUNS = ("modern_refractive", "modern_pinhole_A", "modern_pinhole_B",
                 "modern_refractive_matchfilt", "modern_lightglue_matchfilt")
RESULTS = ANALYSIS_RUNS + ("modern_comparison",)
FISH_RUNS = ("modern_run5_filtered", "modern_run3_raw", "modern_lg_full", "modern_lg_sparse")


def link(src: Path, dst: Path) -> None:
    """Hard-link one file, or every file under a directory, into the staging tree."""
    src = src.resolve()
    if src.is_dir():
        for f in src.rglob("*"):
            if f.is_file():
                link(f, dst / f.relative_to(src))
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.link(src, dst)


def stage_run_meta(run: str, root: Path, extra: tuple[str, ...] = ()) -> None:
    for name in ("calibration.json", "config.yaml", "run.log") + extra:
        if (DATA / "runs" / run / name).exists():
            link(DATA / "runs" / run / name, root / "data" / "runs" / run / name)


def ply_vertex_count(path: Path) -> int:
    with path.open("rb") as fh:
        for raw in fh:
            line = raw.decode("ascii", errors="replace").strip()
            if line.startswith("element vertex"):
                return int(line.split()[-1])
            if line == "end_header":
                break
    raise ValueError(f"no vertex count in {path}")


def stage(staging: Path) -> dict[str, Path]:
    roots = {}

    # Core: inputs, per-run metadata, analysis outputs, result tables, fish readouts
    core = roots["core"] = staging / "core"
    gt = DATA / "aquamvs_ground_truth_analysis"
    link(gt / "frames", core / "data/aquamvs_ground_truth_analysis/frames")
    link(gt / "config.yaml", core / "data/aquamvs_ground_truth_analysis/config.yaml")
    stage_run_meta("modern_pinhole_A", core)
    for run in ANALYSIS_RUNS:
        link(DATA / f"analysis_output.{run}", core / f"data/analysis_output.{run}")
    for run in RESULTS:
        link(DATA / f"results.{run}", core / f"data/results.{run}")
    counts = {}
    for run in FISH_RUNS:
        src = DATA / "runs_fish" / run
        for f in sorted(src.iterdir()):
            if f.is_file() and f.suffix in (".yaml", ".json", ".log") and f.name != "calibration.json":
                link(f, core / "data/runs_fish" / run / f.name)
        for frame_dir in sorted((src / "output").glob("frame_*")):
            for ply in ("fused.ply", "sparse.ply"):
                p = frame_dir / "point_cloud" / ply
                if p.exists():
                    counts.setdefault(run, {})[f"{frame_dir.name}/point_cloud/{ply}"] = ply_vertex_count(p)
    out = core / "data/runs_fish/point_counts.json"
    out.write_text(json.dumps(counts, indent=2) + "\n")

    # Full runs: per-frame analysis subset
    for label, run in FULL_RUNS.items():
        root = roots[f"run-{label}"] = staging / f"run-{label}"
        stage_run_meta(run, root)
        link(DATA / "runs" / run / "output" / "config.yaml", root / "data/runs" / run / "output/config.yaml")
        for frame_dir in sorted((DATA / "runs" / run / "output").glob("frame_*")):
            for sub in FRAME_SUBDIRS:
                link(frame_dir / sub, root / "data/runs" / run / "output" / frame_dir.name / sub)

    # Matched-filter runs: own depth maps; everything else links into the source run
    root = roots["run-matchfilt"] = staging / "run-matchfilt"
    for run, source in MATCHFILT_RUNS.items():
        stage_run_meta(run, root, extra=("FILTER_README.md", "filter_summary.json"))
        for frame_dir in sorted((DATA / "runs" / run / "output").glob("frame_*")):
            dst = root / "data/runs" / run / "output" / frame_dir.name
            link(frame_dir / "depth_maps", dst / "depth_maps")
            for sub in FRAME_SUBDIRS[1:]:
                (dst / sub).symlink_to(Path("../../..") / source / "output" / frame_dir.name / sub)
    return roots


def main(staging: Path) -> None:
    if staging.exists() and any(staging.iterdir()):
        sys.exit(f"{staging} is not empty")
    roots = stage(staging)
    for name, root in roots.items():
        zip_path = staging / f"aquamvs-gt-{name}.zip"
        # -y stores the matched-filter runs' relative symlinks as links
        subprocess.run(["zip", "-q", "-r", "-y", "-X", str(zip_path), "data"], cwd=root, check=True)
        subprocess.run(["unzip", "-tq", str(zip_path)], check=True)
        print(f"{zip_path.name}: {zip_path.stat().st_size / 1e9:.2f} GB")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]).expanduser().resolve())
