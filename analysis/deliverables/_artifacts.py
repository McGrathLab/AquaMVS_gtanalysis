"""
Read-only loaders for the 5 persisted analysis artifacts.

All paths are anchored to the repository root (this file's parent.parent.parent)
so scripts run correctly from any working directory via `conda run`.

These functions read ONLY the small JSON files.
They do NOT import or load corners.npz or fused point clouds.
"""

import json
from pathlib import Path

# Resolve repository root relative to this file's location
# analysis/deliverables/_artifacts.py  ->  analysis/deliverables  ->  analysis  ->  repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

ANALYSIS_OUTPUT = _REPO_ROOT / "data" / "analysis_output"
RESULTS_DIR = _REPO_ROOT / "results"
FIGURES_DIR = ANALYSIS_OUTPUT / "figures"


def _load_json(path: Path) -> dict:
    """Load a JSON file, raising a descriptive error if it is absent."""
    if not path.exists():
        raise FileNotFoundError(
            f"Required artifact not found: {path}\n"
            "Run the earlier pipeline stages to generate it."
        )
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_flatness() -> dict:
    """Load scale_independent_metrics/flatness_consistency.json."""
    return _load_json(
        ANALYSIS_OUTPUT / "scale_independent_metrics" / "flatness_consistency.json"
    )


def load_cross_camera() -> dict:
    """Load scale_independent_metrics/cross_camera_agreement.json."""
    return _load_json(
        ANALYSIS_OUTPUT / "scale_independent_metrics" / "cross_camera_agreement.json"
    )


def load_scale_alignment() -> dict:
    """Load scale_alignment.json."""
    return _load_json(ANALYSIS_OUTPUT / "scale_alignment.json")


def load_error_decomp() -> dict:
    """Load error_decomposition.json."""
    return _load_json(ANALYSIS_OUTPUT / "error_decomposition.json")


def load_dropout() -> dict:
    """Load corner_transfer/dropout_report.json."""
    return _load_json(ANALYSIS_OUTPUT / "corner_transfer" / "dropout_report.json")
