"""
AquaMVS Ground-Truth Validation — Single Reproducible Entrypoint (OUT-05)
=========================================================================
Regenerates ALL artifacts and deliverables in dependency order from one command.

Stages (run in order by default):
  1. transfer_corners     — image corner detection + refractive ray cast (XFER-02/03/04)
  2. compute_flatness_consistency — MET-01/02 flatness + spatial/angular consistency
  3. compute_cross_camera         — MET-03 cross-camera board-localization agreement
  4. compute_scale_alignment      — MET-04/05 scale + rigid inlier RMSE (after Phase 3)
  5. compute_error_decomposition  — MET-06 range-vs-lateral decomposition (refraction sig.)

Deliverable generators (always run after metric stages):
  make_table, make_per_camera, make_methods, fig_spatial_consistency, fig_range_lateral

Run:
    conda run -n AquaMVS python analysis/run_all.py
    conda run -n AquaMVS python analysis/run_all.py --data-root data/aquamvs_ground_truth_analysis
    conda run -n AquaMVS python analysis/run_all.py --skip-metrics  # regenerate deliverables only

The script is deterministic and safe to re-run: each stage overwrites its artifacts
in place; no timestamps or randomness are introduced into output filenames.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Ensure repo root is on sys.path (mirror entrypoint.py's pattern so that
# `analysis.*` and `aquamvs` resolve correctly regardless of cwd).
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Path constants (relative to repo root; kept here for single-source clarity)
# ---------------------------------------------------------------------------
_DATA_ROOT_DEFAULT = "data/aquamvs_ground_truth_analysis"
_CORNERS = "data/analysis_output/corner_transfer/corners.npz"
_CORNER_TRANSFER_OUT = "data/analysis_output/corner_transfer"
_SI_METRICS_OUT = "data/analysis_output/scale_independent_metrics"
_SCALE_ALIGNMENT_OUT = "data/analysis_output/scale_alignment.json"
_ERROR_DECOMP_OUT = "data/analysis_output"


# ---------------------------------------------------------------------------
# Stage runner
# ---------------------------------------------------------------------------

def _run(cmd: list[str], label: str) -> None:
    """Run *cmd* as a subprocess; raise RuntimeError on non-zero exit."""
    print(f"\n{'=' * 64}")
    print(f"STAGE: {label}")
    print(f"CMD  : {' '.join(cmd)}")
    print(f"{'=' * 64}")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"Stage {label!r} failed with exit code {result.returncode}.\n"
            "Aborting — fix the error above and re-run."
        )


# ---------------------------------------------------------------------------
# Metric stages (1-5) in dependency order
# ---------------------------------------------------------------------------

def run_metrics(data_root: str) -> None:
    """Run the 5 compute stages in the correct dependency order.

    compute_scale_alignment (stage 4) guards itself and will refuse to run
    unless Phase-3 artifacts exist, so stages 2 and 3 MUST complete first.
    """
    corners = _CORNERS
    corner_out = _CORNER_TRANSFER_OUT
    si_out = _SI_METRICS_OUT

    # Stage 1 — corner transfer (XFER-02/03/04)
    _run(
        [
            sys.executable, "-m", "analysis.transfer_corners",
            "--data-root", data_root,
            "--out-dir", corner_out,
        ],
        "1/5  transfer_corners  (XFER-02/03/04)",
    )

    # Stage 2 — flatness & spatial/angular consistency (MET-01/02)
    _run(
        [
            sys.executable, "-m", "analysis.compute_flatness_consistency",
            "--data-root", data_root,
            "--corners", corners,
            "--out-dir", si_out,
        ],
        "2/5  compute_flatness_consistency  (MET-01/02)",
    )

    # Stage 3 — cross-camera agreement (MET-03)
    _run(
        [
            sys.executable, "-m", "analysis.compute_cross_camera",
            "--corners", corners,
            "--out-dir", si_out,
        ],
        "3/5  compute_cross_camera  (MET-03)",
    )

    # Stage 4 — scale + rigid alignment (MET-04/05); MUST follow stages 2+3
    _run(
        [
            sys.executable, "-m", "analysis.compute_scale_alignment",
            "--corners", corners,
            "--data-root", data_root,
            "--out", _SCALE_ALIGNMENT_OUT,
        ],
        "4/5  compute_scale_alignment  (MET-04/05)",
    )

    # Stage 5 — error-direction decomposition (MET-06)
    _run(
        [
            sys.executable, "-m", "analysis.compute_error_decomposition",
            "--corners", corners,
            "--data-root", data_root,
            "--out", _ERROR_DECOMP_OUT,
        ],
        "5/5  compute_error_decomposition  (MET-06)",
    )


# ---------------------------------------------------------------------------
# Deliverable generators
# ---------------------------------------------------------------------------

def run_deliverables() -> None:
    """Import and call each deliverable generator's main() in order."""
    # Late imports so that the metric-stage artifacts are on disk before
    # the generators try to read them.
    from analysis.deliverables.make_table import main as make_table
    from analysis.deliverables.make_per_camera import main as make_per_camera
    from analysis.deliverables.make_methods import main as make_methods
    from analysis.deliverables.fig_spatial_consistency import main as fig_spatial
    from analysis.deliverables.fig_range_lateral import main as fig_range
    from analysis.deliverables.fig_anisotropy import main as fig_anisotropy
    from analysis.deliverables.fig_boards_volume import main as fig_boards_volume
    from analysis.deliverables.fig_board_heatmap import main as fig_board_heatmap

    print(f"\n{'=' * 64}")
    print("DELIVERABLES: table, per-camera, methods, figures")
    print(f"{'=' * 64}")

    print("\n--- make_table ---")
    make_table()

    print("\n--- make_per_camera ---")
    make_per_camera()

    print("\n--- make_methods ---")
    make_methods()

    print("\n--- fig_spatial_consistency ---")
    fig_spatial()

    print("\n--- fig_range_lateral ---")
    fig_range()

    print("\n--- fig_anisotropy ---")
    fig_anisotropy()

    print("\n--- fig_boards_volume ---")
    fig_boards_volume()

    print("\n--- fig_board_heatmap ---")
    fig_board_heatmap()


# ---------------------------------------------------------------------------
# Final summary
# ---------------------------------------------------------------------------

def _fmt_file(path: Path, repo_root: Path) -> str:
    rel = path.relative_to(repo_root)
    if path.exists():
        size = path.stat().st_size
        return f"  EXISTS  {size:>12,} B   {rel}"
    return f"  MISSING             -   {rel}"


def print_summary() -> None:
    """Print a file-by-file exists/size summary and headline metric recap."""
    from analysis.deliverables._artifacts import (
        load_flatness,
        load_cross_camera,
        load_scale_alignment,
        load_error_decomp,
    )

    repo = _REPO_ROOT
    fig_dir = repo / "data" / "analysis_output" / "figures"

    output_files: list[Path] = [
        # Metric artifacts
        repo / "data/analysis_output/corner_transfer/corners.npz",
        repo / "data/analysis_output/corner_transfer/dropout_report.json",
        repo / "data/analysis_output/scale_independent_metrics/flatness_consistency.json",
        repo / "data/analysis_output/scale_independent_metrics/cross_camera_agreement.json",
        repo / "data/analysis_output/scale_alignment.json",
        repo / "data/analysis_output/error_decomposition.json",
        # Table deliverables
        repo / "results/table.md",
        repo / "results/table.tex",
        repo / "results/table.csv",
        # Per-camera deliverable
        repo / "results/per_camera_agreement.md",
        repo / "results/per_camera_agreement.csv",
        # Methods deliverable
        repo / "results/methods.md",
        # Figures (6 files: 2 names x 3 formats)
        fig_dir / "spatial_consistency.svg",
        fig_dir / "spatial_consistency.pdf",
        fig_dir / "spatial_consistency.png",
        fig_dir / "range_vs_lateral.svg",
        fig_dir / "range_vs_lateral.pdf",
        fig_dir / "range_vs_lateral.png",
    ]

    print(f"\n{'=' * 64}")
    print("SUMMARY — ALL OUTPUT FILES")
    print(f"{'=' * 64}")

    all_present = True
    for f in output_files:
        line = _fmt_file(f, repo)
        print(line)
        if "MISSING" in line:
            all_present = False

    # Headline metrics (read from artifacts; no banned strings)
    print(f"\n{'=' * 64}")
    print("HEADLINE METRICS (from artifacts, scale-independent led)")
    print(f"{'=' * 64}")
    try:
        fl = load_flatness()
        cc = load_cross_camera()
        sa = load_scale_alignment()
        ed = load_error_decomp()

        flatness = fl["pooled"]["flatness_rms_mm_pooled"]
        cross_cam = cc["overall"]["overall_rms_mm"]
        rigid = sa["pooled"]["rigid_rms_mm_pooled"]
        scale_pct = sa["pooled"]["scale_error_pct_mean"]
        dominance = ed["pooled"]["range_lateral"]["range_dominance"]
        range_rms = ed["pooled"]["range_lateral"]["range_rms_mm"]
        lateral_rms = ed["pooled"]["range_lateral"]["lateral_rms_mm"]

        print(f"  flatness RMS        {flatness:.2f} mm    (MET-01, scale-independent)")
        print(f"  cross-camera RMS    {cross_cam:.2f} mm    (MET-03, scale-independent)")
        print(f"  rigid inlier RMSE   {rigid:.2f} mm    (MET-05, scale alignment)")
        print(f"  scale error         {scale_pct:+.3f}%    (MET-04, bounds dense-stage scale bias; weakly circular)")
        print(f"  range dominance     {dominance:.2f}x       (MET-06, range {range_rms:.2f} mm vs lateral {lateral_rms:.2f} mm)")
        print("  Maas (2015) benchmark: factor of two refractive precision penalty")
    except Exception as exc:
        print(f"  WARNING: could not read headline metrics: {exc}")

    print(f"{'=' * 64}")
    if all_present:
        print("ALL FILES PRESENT  —  run_all.py complete.")
    else:
        print("WARNING: one or more output files are MISSING (see above).")
    print(f"{'=' * 64}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "AquaMVS Ground-Truth Validation — single reproducible entrypoint (OUT-05). "
            "Regenerates all metric artifacts and manuscript deliverables in dependency order. "
            "Safe to re-run: stages overwrite existing artifacts in place."
        )
    )
    parser.add_argument(
        "--data-root",
        default=_DATA_ROOT_DEFAULT,
        help=(
            f"Path to extracted dataset root "
            f"(default: {_DATA_ROOT_DEFAULT})"
        ),
    )
    parser.add_argument(
        "--skip-metrics",
        action="store_true",
        help=(
            "Skip compute stages 1-5 and regenerate deliverables from existing "
            "artifacts only.  Useful for fast figure/table iteration when metric "
            "artifacts are already present on disk."
        ),
    )
    args = parser.parse_args()

    if not args.skip_metrics:
        run_metrics(args.data_root)

    run_deliverables()
    print_summary()


if __name__ == "__main__":
    main()
