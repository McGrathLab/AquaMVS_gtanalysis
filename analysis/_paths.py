"""
Output-root resolution shared by every stage, deliverable and artifact check.

By default all artifacts land in data/analysis_output/ and all deliverables in
results/. Two environment variables redirect them, so an alternative
reconstruction (e.g. a pinhole ablation) can be analyzed without overwriting
the baseline artifacts, and the figures read the run being analyzed:

    AQUAMVS_GT_OUT      analysis-output root   (default: data/analysis_output)
    AQUAMVS_GT_RESULTS  deliverables root      (default: results)
    AQUAMVS_GT_DATA     dataset / run root     (default: data/aquamvs_ground_truth_analysis)

Relative values are resolved against the repository root, not the cwd.
Resolved at call time, so run_all.py can set them after parsing its CLI and
subprocess stages inherit them.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

OUT_ENV = "AQUAMVS_GT_OUT"
RESULTS_ENV = "AQUAMVS_GT_RESULTS"
DATA_ENV = "AQUAMVS_GT_DATA"


def _resolve(env_var: str, default: Path) -> Path:
    value = os.environ.get(env_var)
    if not value:
        return default
    path = Path(value).expanduser()
    return path if path.is_absolute() else REPO_ROOT / path


def analysis_output_root() -> Path:
    """Root for metric artifacts (corner_transfer/, scale_independent_metrics/, ...)."""
    return _resolve(OUT_ENV, REPO_ROOT / "data" / "analysis_output")


def results_root() -> Path:
    """Root for table / per-camera / methods deliverables."""
    return _resolve(RESULTS_ENV, REPO_ROOT / "results")


def data_root() -> Path:
    """Dataset / run root (calibration.json + output/) that the figures read."""
    return _resolve(DATA_ENV, REPO_ROOT / "data" / "aquamvs_ground_truth_analysis")
