"""
Styling wrapper for DissertationFigures.

Adds the DissertationFigures src directory to sys.path as a robust fallback
so this module is self-contained for OUT-05 reproducibility, even if the
editable install is absent.  The editable install (preferred) is performed
once via:
    pip install -e C:\\Users\\tucke\\PycharmProjects\\DissertationFigures

We import the submodules directly (NOT the top-level package, which pulls
heavy diagram dependencies).
"""

import sys as _sys

# Robust fallback: insert the DissertationFigures src dir before any import
_DF_SRC = r"C:\Users\tucke\PycharmProjects\DissertationFigures\src"
if _DF_SRC not in _sys.path:
    _sys.path.insert(0, _DF_SRC)

from dissertationfigures.core.style import dissertation_style, COLORS, PALETTE
from dissertationfigures.core.export import save_figure

__all__ = ["dissertation_style", "COLORS", "PALETTE", "save_figure"]
