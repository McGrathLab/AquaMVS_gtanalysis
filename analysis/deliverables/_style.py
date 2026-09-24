"""
Figure styling for the deliverables — self-contained.

Vendored from DissertationFigures (src/dissertationfigures/core/{style,export}.py,
commit 55479f6) so this repository reproduces its figures without that (private)
package. Only the pieces the deliverables use are kept: the qualitative palette,
the rcParams context manager, and the multi-format save helper. Styling only —
nothing here affects any computed value.

Font note: if a LaTeX installation is found, text renders with usetex + Computer
Modern (Type 1 in PDFs, matching the manuscript); otherwise with DejaVu Serif.
Figures therefore differ in typeface (not content) between machines with and
without LaTeX. The fallback embeds TrueType (Type 42), never Type 3, which
Elsevier artwork guidelines reject. For manuscript figures set
AQUAMVS_GT_STRICT_FONTS=1 (or pass --strict-fonts to run_all.py / make_figures.py)
to fail instead of falling back.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import sys
from pathlib import Path
from typing import Generator

import matplotlib as mpl
import matplotlib.colors as mcolors
import matplotlib.figure

__all__ = ["dissertation_style", "COLORS", "PALETTE", "TINTS", "CMAP_SEQ", "CMAP_DIV",
           "SINGLE_COL", "DOUBLE_COL", "save_figure", "require_latex"]

STRICT_FONTS_ENV = "AQUAMVS_GT_STRICT_FONTS"

# ---------------------------------------------------------------------------
# Qualitative palette — 12 colors, colorblind-safe
# ---------------------------------------------------------------------------
# First two sampled from cividis (t≈0.08, t≈0.92) to tie qualitative plots
# to the sequential colormap.  Remaining 10 from Paul Tol muted/bright.
COLORS = {
    "blue":      "#003070",  # cividis dark
    "gold":      "#EAD34C",  # cividis bright
    "teal":      "#44AA99",
    "cyan":      "#66CCEE",
    "green":     "#228833",
    "olive":     "#999933",
    "coral":     "#EE6677",
    "rose":      "#EE99AA",
    "purple":    "#AA3377",
    "indigo":    "#332288",
    "gray":      "#BBBBBB",
    "dark gray": "#777777",
}

PALETTE = list(COLORS.values())

# Light tints (15 % opacity on white) of the palette, for Graphviz fills.
TINTS = {
    "blue":      "#D8DFE9",
    "gold":      "#FBF8E4",
    "teal":      "#E2F2EF",
    "cyan":      "#E8F7FC",
    "green":     "#DDEDE0",
    "olive":     "#EFEFE0",
    "coral":     "#FCE8EA",
    "rose":      "#FCEFF2",
    "purple":    "#F2E0EA",
    "indigo":    "#E0DDED",
    "gray":      "#F4F4F4",
    "dark gray": "#EAEAEA",
}

# Sequential: cividis. Diverging "ocean": brand blue <-> coral through white.
CMAP_SEQ = mpl.colormaps["cividis"]
CMAP_DIV = mcolors.LinearSegmentedColormap.from_list(
    "ocean_div", ["#4477AA", "#92C5DE", "#F7F7F7", "#F4A582", "#EE6677"], N=256,
)

SINGLE_COL = 3.5   # single-column figure width (in)
DOUBLE_COL = 7.0   # double-column / full-width figure width (in)


# ---------------------------------------------------------------------------
# Detect whether a LaTeX installation is available
# ---------------------------------------------------------------------------
def _find_latex() -> bool:
    """Check PATH first, then probe common install locations."""
    if shutil.which("latex") is not None:
        return True
    # MiKTeX default install path on Windows
    if sys.platform == "win32":
        miktex = Path.home() / "AppData/Local/Programs/MiKTeX/miktex/bin/x64"
        if (miktex / "latex.exe").is_file():
            os.environ["PATH"] = f"{miktex}{os.pathsep}{os.environ.get('PATH', '')}"
            return True
    return False


_HAS_LATEX = _find_latex()


def require_latex() -> None:
    """Raise unless LaTeX is available (manuscript figures must be Computer Modern)."""
    if not _HAS_LATEX:
        raise RuntimeError(
            "No LaTeX found: figures would fall back to DejaVu Serif, which does not match "
            "the manuscript. Install LaTeX (texlive-latex-extra, cm-super, dvipng) or unset "
            f"{STRICT_FONTS_ENV}."
        )

# ---------------------------------------------------------------------------
# Matplotlib rcParams for LaTeX-quality output
# ---------------------------------------------------------------------------
_FONT_RC: dict = (
    {
        "text.usetex": True,
        "font.family": "serif",
        "font.serif": ["Computer Modern Roman"],
        "text.latex.preamble": r"\usepackage{amsmath}",
    }
    if _HAS_LATEX
    else {
        "text.usetex": False,
        "font.family": "serif",
        "font.serif": ["DejaVu Serif"],
        "mathtext.fontset": "dejavuserif",
    }
)

RCPARAMS: dict = {
    **_FONT_RC,

    # --- never emit Type 3 fonts (only reached on the non-usetex fallback) ---
    "pdf.fonttype": 42,
    "ps.fonttype": 42,

    # --- figure defaults ---
    "figure.figsize": (SINGLE_COL, SINGLE_COL * 0.75),
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,

    # --- axes ---
    "axes.linewidth": 0.6,
    "axes.labelsize": 9,
    "axes.titlesize": 10,
    "axes.prop_cycle": mpl.cycler(color=PALETTE),
    "axes.grid": False,
    "axes.spines.top": False,
    "axes.spines.right": False,

    # --- ticks ---
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "xtick.minor.width": 0.4,
    "ytick.minor.width": 0.4,
    "xtick.direction": "in",
    "ytick.direction": "in",

    # --- legend ---
    "legend.fontsize": 8,
    "legend.frameon": False,

    # --- lines ---
    "lines.linewidth": 1.2,
    "lines.markersize": 4,
}


@contextlib.contextmanager
def dissertation_style() -> Generator[None, None, None]:
    """Context manager that temporarily activates the dissertation rcParams."""
    if os.environ.get(STRICT_FONTS_ENV):
        require_latex()
    with mpl.rc_context(rc=RCPARAMS):
        yield


def save_figure(
    fig: matplotlib.figure.Figure,
    name: str,
    *,
    formats: tuple[str, ...] = ("svg", "pdf", "png"),
    output_dir: Path | str,
    extra_artists: list | None = None,
    **savefig_kwargs,
) -> list[Path]:
    """Save *fig* to *output_dir*/*name*.{svg,pdf,...} and return the paths.

    Parameters
    ----------
    extra_artists:
        Additional matplotlib artists to include when computing the tight
        bounding box.  Pass ``[ax.yaxis.label]`` when a long ylabel is being
        clipped despite ``bbox_inches='tight'`` (a known font-metrics issue
        with certain characters in DejaVu Serif).
    **savefig_kwargs:
        Forwarded directly to ``fig.savefig``, e.g. ``pad_inches=0.1``.
    """
    dest = Path(output_dir)
    dest.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for fmt in formats:
        p = dest / f"{name}.{fmt}"
        fig.savefig(p, format=fmt, bbox_extra_artists=extra_artists or [],
                    **savefig_kwargs)
        paths.append(p)
    return paths
