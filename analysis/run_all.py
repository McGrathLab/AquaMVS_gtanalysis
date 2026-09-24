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
    python analysis/run_all.py
    python analysis/run_all.py --data-root data/aquamvs_ground_truth_analysis
    python analysis/run_all.py --skip-metrics  # regenerate deliverables only

    # Analyze an alternative reconstruction without touching the baseline artifacts:
    python analysis/run_all.py --data-root <alt dataset root> \
        --output-root data/analysis_output.pinhole --results-dir results.pinhole

The script is deterministic and safe to re-run: each stage overwrites its artifacts
in place; no timestamps or randomness are introduced into output filenames.
Output roots default to data/analysis_output and results/; --output-root /
--results-dir (or the AQUAMVS_GT_OUT / AQUAMVS_GT_RESULTS env vars) redirect them.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Ensure repo root is on sys.path (mirror entrypoint.py's pattern so that
# `analysis.*` and `aquamvs` resolve correctly regardless of cwd).
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from analysis._paths import OUT_ENV, RESULTS_ENV, analysis_output_root, results_root  # noqa: E402

# ---------------------------------------------------------------------------
# Path constants (single-source clarity). Output paths are derived from the
# analysis-output root at run time so --output-root / AQUAMVS_GT_OUT apply.
# ---------------------------------------------------------------------------
_DATA_ROOT_DEFAULT = "data/aquamvs_ground_truth_analysis"


def _output_paths() -> dict[str, str]:
    out = analysis_output_root()
    return {
        "corners": str(out / "corner_transfer" / "corners.npz"),
        "corner_transfer_out": str(out / "corner_transfer"),
        "si_metrics_out": str(out / "scale_independent_metrics"),
        "scale_alignment_out": str(out / "scale_alignment.json"),
        "error_decomp_out": str(out),
    }


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
    paths = _output_paths()
    corners = paths["corners"]
    corner_out = paths["corner_transfer_out"]
    si_out = paths["si_metrics_out"]

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
            "--out", paths["scale_alignment_out"],
        ],
        "4/5  compute_scale_alignment  (MET-04/05)",
    )

    # Stage 5 — error-direction decomposition (MET-06)
    _run(
        [
            sys.executable, "-m", "analysis.compute_error_decomposition",
            "--corners", corners,
            "--data-root", data_root,
            "--out", paths["error_decomp_out"],
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
    rel = path.relative_to(repo_root) if path.is_relative_to(repo_root) else path
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
    out = analysis_output_root()
    res = results_root()
    fig_dir = out / "figures"

    output_files: list[Path] = [
        # Metric artifacts
        out / "corner_transfer/corners.npz",
        out / "corner_transfer/dropout_report.json",
        out / "scale_independent_metrics/flatness_consistency.json",
        out / "scale_independent_metrics/cross_camera_agreement.json",
        out / "scale_alignment.json",
        out / "error_decomposition.json",
        # Table deliverables
        res / "table.md",
        res / "table.tex",
        res / "table.csv",
        # Per-camera deliverable
        res / "per_camera_agreement.md",
        res / "per_camera_agreement.csv",
        # Methods deliverable
        res / "methods.md",
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
    parser.add_argument(
        "--output-root",
        default=None,
        help=(
            f"Analysis-output root (default: ${OUT_ENV} or data/analysis_output). "
            "Relative paths resolve against the repo root."
        ),
    )
    parser.add_argument(
        "--results-dir",
        default=None,
        help=(
            f"Deliverables root (default: ${RESULTS_ENV} or results). "
            "Relative paths resolve against the repo root."
        ),
    )
    parser.add_argument(
        "--strict-fonts",
        action="store_true",
        help="Fail if LaTeX is unavailable instead of falling back to DejaVu Serif "
             "(use for manuscript figures).",
    )
    args = parser.parse_args()

    if args.strict_fonts:
        os.environ["AQUAMVS_GT_STRICT_FONTS"] = "1"
    # Set before any stage subprocess or deliverable import resolves its paths.
    if args.output_root:
        os.environ[OUT_ENV] = args.output_root
    if args.results_dir:
        os.environ[RESULTS_ENV] = args.results_dir
    print(f"Analysis output root : {analysis_output_root()}")
    print(f"Results root         : {results_root()}")

    if not args.skip_metrics:
        run_metrics(args.data_root)

    run_deliverables()
    print_summary()


if __name__ == "__main__":
    main()
