"""
Read-only loaders for the 5 persisted analysis artifacts.

All paths are anchored to the repository root (this file's parent.parent.parent)
so scripts run correctly from any working directory.

These functions read ONLY the small JSON files.
They do NOT import or load corners.npz or fused point clouds.
"""

import json
from pathlib import Path

from analysis._paths import analysis_output_root, results_root

# Default data/analysis_output and results/; overridable via AQUAMVS_GT_OUT /
# AQUAMVS_GT_RESULTS (see analysis/_paths.py). Resolved once, at first import.
ANALYSIS_OUTPUT = analysis_output_root()
RESULTS_DIR = results_root()
FIGURES_DIR = ANALYSIS_OUTPUT / "figures"


def _root(root: Path | str | None = None) -> Path:
    """Resolve an artifact root: explicit argument, else the module default."""
    return Path(root) if root is not None else ANALYSIS_OUTPUT


def _load_json(path: Path) -> dict:
    """Load a JSON file, raising a descriptive error if it is absent."""
    if not path.exists():
        raise FileNotFoundError(
            f"Required artifact not found: {path}\n"
            "Run the earlier pipeline stages to generate it."
        )
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_flatness(root: Path | str | None = None) -> dict:
    """Load scale_independent_metrics/flatness_consistency.json from *root*."""
    return _load_json(
        _root(root) / "scale_independent_metrics" / "flatness_consistency.json"
    )


def load_cross_camera(root: Path | str | None = None) -> dict:
    """Load scale_independent_metrics/cross_camera_agreement.json from *root*."""
    return _load_json(
        _root(root) / "scale_independent_metrics" / "cross_camera_agreement.json"
    )


def load_scale_alignment(root: Path | str | None = None) -> dict:
    """Load scale_alignment.json from *root*."""
    return _load_json(_root(root) / "scale_alignment.json")


def load_error_decomp(root: Path | str | None = None) -> dict:
    """Load error_decomposition.json from *root*."""
    return _load_json(_root(root) / "error_decomposition.json")


def load_dropout(root: Path | str | None = None) -> dict:
    """Load corner_transfer/dropout_report.json from *root*."""
    return _load_json(_root(root) / "corner_transfer" / "dropout_report.json")
