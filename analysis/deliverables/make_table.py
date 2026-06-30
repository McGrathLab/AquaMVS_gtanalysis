"""
OUT-01: Results table generator.

Reads the on-disk JSON artifacts (never recomputes values) and emits:
  results/table.md   — GitHub Markdown table for review
  results/table.tex  — LaTeX booktabs table for the manuscript
  results/table.csv  — CSV source-of-truth (header + 6 rows)

Run as a module:
  python -m analysis.deliverables.make_table
or import and call main().
"""

import csv
import textwrap
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
            f"+{scale_err_pct:+.2f}% / {board_size_mm:.3f} mm",
            "% / mm",
            "consistency check (partly circular)",
        ],
    ]
    return rows


def _check_banned(text: str) -> None:
    """Raise ValueError if any banned string appears in text."""
    for banned in _BANNED:
        if banned in text:
            raise ValueError(
                f"Banned string {banned!r} found in output. "
                "Check that artifact values are read correctly and not hardcoded."
            )


def _write_markdown(rows: list[list[str]], path: Path) -> None:
    """Write a GitHub Markdown table."""
    sep = "| " + " | ".join(["---"] * len(_HEADERS)) + " |"
    lines = []
    lines.append("| " + " | ".join(_HEADERS) + " |")
    lines.append(sep)
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    text = "\n".join(lines) + "\n"
    _check_banned(text)
    path.write_text(text, encoding="utf-8")
    print(f"  Written: {path}")


def _write_latex(rows: list[list[str]], path: Path) -> None:
    """Write a LaTeX booktabs table."""

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
        r"  \begin{tabular}{llll}",
        r"    \toprule",
        "    " + " & ".join(esc(h) for h in _HEADERS) + r" \\",
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


def _write_csv(rows: list[list[str]], path: Path) -> None:
    """Write a CSV file (header + 6 data rows)."""
    lines_buf: list[str] = []
    import io

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_HEADERS)
    writer.writerows(rows)
    text = buf.getvalue()
    _check_banned(text)
    path.write_text(text, encoding="utf-8")
    print(f"  Written: {path}")


def main() -> None:
    """Generate results/table.{md,tex,csv} from on-disk artifacts."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Building results table from artifacts...")
    rows = _build_rows()

    _write_markdown(rows, RESULTS_DIR / "table.md")
    _write_latex(rows, RESULTS_DIR / "table.tex")
    _write_csv(rows, RESULTS_DIR / "table.csv")

    print("OUT-01 complete: results/table.{md,tex,csv} written.")


if __name__ == "__main__":
    main()
