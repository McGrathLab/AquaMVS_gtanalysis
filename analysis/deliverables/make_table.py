"""
OUT-01: Results table generator.

Reads the on-disk JSON artifacts (never recomputes values) and emits:
  results/table.md   — GitHub Markdown table for review
  results/table.tex  — LaTeX booktabs table for the manuscript
  results/table.csv  — CSV source-of-truth

Single-column mode (default) emits the original 6-row metric table from one
analysis-output root. Multi-column mode compares several reconstruction runs
side by side (R2.1/R2.2/R1.4): one column per named output root, one scalar
per cell.

Run as a module:
  python -m analysis.deliverables.make_table
  python -m analysis.deliverables.make_table \
      --column "RoMa-refractive=data/analysis_output" \
      --column "LightGlue-refractive=data/analysis_output.lightglue" \
      --column "RoMa-pinhole=data/analysis_output.pinhole_B"
or import and call main() / main(columns=[(name, root), ...]).
"""

import argparse
import csv
from pathlib import Path

from analysis.deliverables._artifacts import (
    RESULTS_DIR,
    load_cross_camera,
    load_dropout,
    load_error_decomp,
    load_flatness,
    load_scale_alignment,
)

# Strings that must never appear in any deliverable (pre-fix / misread values)
_BANNED = ("58.5", "173.7", "0.5 %")

# Column headers
_HEADERS = ["Metric", "Value", "Units", "Category"]


def _build_rows() -> list[list[str]]:
    """Read artifacts and build the 6 metric rows. Never hardcodes numeric values."""
    flat = load_flatness()
    cc = load_cross_camera()
    sa = load_scale_alignment()
    ed = load_error_decomp()
    # dropout loaded to confirm artifact access but not used in main table rows
    _do = load_dropout()

    # MET-01: Flatness
    flatness_rms = flat["pooled"]["flatness_rms_mm_pooled"]

    # MET-02: Spatial/angular consistency
    board_size_cv = flat["variation"]["board_size_cv"]
    tilt_min = flat["variation"]["tilt_deg_min"]
    tilt_max = flat["variation"]["tilt_deg_max"]

    # MET-03: Cross-camera agreement
    cc_rms = cc["overall"]["overall_rms_mm"]

    # MET-05: Rigid inlier RMSE (scale-independent)
    rigid_rms = sa["pooled"]["rigid_rms_mm_pooled"]

    # MET-06: Range-vs-lateral dominance (refraction signature)
    rl = ed["pooled"]["range_lateral"]
    range_dominance = rl["range_dominance"]
    range_rms = rl["range_rms_mm"]
    lateral_rms = rl["lateral_rms_mm"]

    # MET-04: Absolute scale (partly circular)
    scale_err_pct = sa["pooled"]["scale_error_pct_mean"]
    board_size_mm = sa["pooled"]["board_size_mm_mean"]

    rows = [
        # MET-01
        [
            "Flatness (MET-01)",
            f"{flatness_rms:.2f}",
            "mm",
            "scale-independent (non-circular)",
        ],
        # MET-02
        [
            "Spatial/angular consistency (MET-02)",
            f"board-size CV {board_size_cv:.4f}; tilt {tilt_min:.1f}-{tilt_max:.1f}",
            "deg / dimensionless",
            "scale-independent (non-circular)",
        ],
        # MET-03
        [
            "Cross-camera agreement (MET-03)",
            f"{cc_rms:.2f}",
            "mm",
            "scale-independent (non-circular)",
        ],
        # MET-05
        [
            "Rigid inlier RMSE (MET-05)",
            f"{rigid_rms:.2f}",
            "mm",
            "scale-independent (non-circular)",
        ],
        # MET-06
        [
            "Range-vs-lateral dominance (MET-06)",
            f"{range_dominance:.2f} (range {range_rms:.2f} mm vs lateral {lateral_rms:.2f} mm)",
            "ratio",
            "scale-independent (non-circular, refraction signature)",
        ],
        # MET-04
        [
            "Absolute scale (MET-04)",
            f"{scale_err_pct:+.2f}% / {board_size_mm:.3f} mm",
            "% / mm",
            "bounds dense-stage scale bias (weakly circular; scale traces to board via calibration)",
        ],
    ]
    return rows


# ---------------------------------------------------------------------------
# Multi-column mode (R2.1 / R2.2 / R1.4 comparison)
# ---------------------------------------------------------------------------
# Each entry: (label, units, category, extractor). The extractor takes the five
# loaded artifacts for one column and returns the formatted cell string.
_COMPARISON_ROWS = [
    ("Flatness RMS (MET-01)", "mm", "scale-independent (non-circular)",
     lambda f, c, s_, e, d: f"{f['pooled']['flatness_rms_mm_pooled']:.2f}"),
    ("Cross-camera agreement (MET-03)", "mm", "scale-independent (non-circular)",
     lambda f, c, s_, e, d: f"{c['overall']['overall_rms_mm']:.2f}"),
    ("Rigid inlier RMSE (MET-05)", "mm", "scale-independent (non-circular)",
     lambda f, c, s_, e, d: f"{s_['pooled']['rigid_rms_mm_pooled']:.2f}"),
    ("Board-size CV (MET-02)", "dimensionless", "scale-independent (non-circular)",
     lambda f, c, s_, e, d: f"{f['variation']['board_size_cv']:.4f}"),
    ("Corners with direct depth", "%", "coverage (depth present at detected corner)",
     lambda f, c, s_, e, d: f"{100 * d['headline']['total_direct'] / d['headline']['total_detected']:.1f}"),
    ("Recovered board tilt range (MET-02)", "deg",
     "diagnostic (recovered from each reconstruction, not a fixed pose property)",
     lambda f, c, s_, e, d: f"{f['variation']['tilt_deg_min']:.1f}-{f['variation']['tilt_deg_max']:.1f}"),
    ("Range RMS (MET-06)", "mm", "scale-independent (refraction signature)",
     lambda f, c, s_, e, d: f"{e['pooled']['range_lateral']['range_rms_mm']:.2f}"),
    ("Lateral RMS (MET-06)", "mm", "scale-independent (refraction signature)",
     lambda f, c, s_, e, d: f"{e['pooled']['range_lateral']['lateral_rms_mm']:.2f}"),
    ("Range-vs-lateral dominance (MET-06)", "ratio", "scale-independent (refraction signature)",
     lambda f, c, s_, e, d: f"{e['pooled']['range_lateral']['range_dominance']:.2f}"),
    ("Absolute scale error (MET-04)", "%", "weakly circular (scale traces to board via calibration)",
     lambda f, c, s_, e, d: f"{s_['pooled']['scale_error_pct_mean']:+.3f}"),
    ("Recovered square pitch (MET-04)", "mm", "weakly circular (scale traces to board via calibration)",
     lambda f, c, s_, e, d: f"{s_['pooled']['board_size_mm_mean']:.3f}"),
]


def _build_comparison_rows(columns: list[tuple[str, str]]) -> tuple[list[str], list[list[str]]]:
    """Build headers + rows for a multi-column comparison. Never hardcodes values."""
    loaded = [
        (
            load_flatness(root),
            load_cross_camera(root),
            load_scale_alignment(root),
            load_error_decomp(root),
            load_dropout(root),
        )
        for _name, root in columns
    ]
    headers = ["Metric"] + [name for name, _root in columns] + ["Units", "Category"]
    rows = [
        [label] + [extract(*arts) for arts in loaded] + [units, category]
        for label, units, category, extract in _COMPARISON_ROWS
    ]
    return headers, rows


def _check_banned(text: str) -> None:
    """Raise ValueError if any banned string appears in text."""
    for banned in _BANNED:
        if banned in text:
            raise ValueError(
                f"Banned string {banned!r} found in output. "
                "Check that artifact values are read correctly and not hardcoded."
            )


def _write_markdown(rows: list[list[str]], path: Path, headers: list[str] | None = None) -> None:
    """Write a GitHub Markdown table."""
    headers = headers or _HEADERS
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append(sep)
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    text = "\n".join(lines) + "\n"
    _check_banned(text)
    path.write_text(text, encoding="utf-8")
    print(f"  Written: {path}")


def _write_latex(rows: list[list[str]], path: Path, headers: list[str] | None = None) -> None:
    """Write a LaTeX booktabs table."""
    headers = headers or _HEADERS

    def esc(s: str) -> str:
        """Escape LaTeX special characters in a cell value."""
        s = s.replace("%", r"\%")
        s = s.replace("_", r"\_")
        return s

    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{AquaMVS accuracy metrics}",
        r"  \label{tab:aquamvs-metrics}",
        r"  \begin{tabular}{" + "l" * len(headers) + "}",
        r"    \toprule",
        "    " + " & ".join(esc(h) for h in headers) + r" \\",
        r"    \midrule",
    ]
    for row in rows:
        lines.append("    " + " & ".join(esc(c) for c in row) + r" \\")
    lines += [
        r"    \bottomrule",
        r"  \end{tabular}",
        r"\end{table}",
        "",
    ]
    text = "\n".join(lines)
    _check_banned(text)
    path.write_text(text, encoding="utf-8")
    print(f"  Written: {path}")


def _write_csv(rows: list[list[str]], path: Path, headers: list[str] | None = None) -> None:
    """Write a CSV file (header + data rows)."""
    import io

    headers = headers or _HEADERS
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    text = buf.getvalue()
    _check_banned(text)
    path.write_text(text, encoding="utf-8")
    print(f"  Written: {path}")


def main(columns: list[tuple[str, str]] | None = None) -> None:
    """Generate results/table.{md,tex,csv} from on-disk artifacts.

    columns: None for the original single-column table; otherwise a list of
    (column name, analysis-output root) pairs, emitted left to right.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if columns:
        print(f"Building {len(columns)}-column comparison table from artifacts...")
        for name, root in columns:
            print(f"  {name}: {root}")
        headers, rows = _build_comparison_rows(columns)
    else:
        print("Building results table from artifacts...")
        headers, rows = None, _build_rows()

    _write_markdown(rows, RESULTS_DIR / "table.md", headers)
    _write_latex(rows, RESULTS_DIR / "table.tex", headers)
    _write_csv(rows, RESULTS_DIR / "table.csv", headers)

    print("OUT-01 complete: results/table.{md,tex,csv} written.")


def _parse_column(value: str) -> tuple[str, str]:
    # rpartition, not partition: column names may themselves contain "="
    # (e.g. "RoMa-pinhole (n_water=1 only)=data/analysis_output.pinhole_A").
    name, sep, root = value.rpartition("=")
    if not sep or not name or not root:
        raise argparse.ArgumentTypeError(
            f"--column expects NAME=OUTPUT_ROOT, got {value!r}"
        )
    return name, root


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "--column",
        action="append",
        type=_parse_column,
        default=None,
        metavar="NAME=OUTPUT_ROOT",
        help=(
            "Add a comparison column reading artifacts from OUTPUT_ROOT. "
            "Repeatable; columns appear in the order given. Omit for the "
            "single-column table."
        ),
    )
    main(parser.parse_args().column)
