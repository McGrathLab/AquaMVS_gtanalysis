"""
Synthetic unit tests for analysis/error_decomposition.py (MET-06).

Tests (plain assert; pytest-discoverable):
  1. Pure board-normal residual -> out_of_plane_rms == |r|, in_plane_rms == 0.
  2. Pure in-plane residual     -> out_of_plane_rms == 0, in_plane_rms == |r|.
  3. Pure along-ray residual    -> range_rms == |r|, lateral_rms == 0.
  4. Pure perpendicular residual-> range_rms == 0, lateral_rms == |r|.
  5. 45-degree mix vs a unit ray -> range == lateral == |r|/sqrt(2).
  6. board_frame_residuals reconstructs residuals + normal from a known fit.

Run: python tests/test_error_decomposition.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.error_decomposition import (
    board_frame_residuals,
    decompose_board_frame,
    decompose_range_lateral,
)


def test_board_pure_normal() -> None:
    normal = np.array([0.0, 0.0, 1.0])
    res = np.array([[0.0, 0.0, 0.003]])  # 3 mm along normal
    d = decompose_board_frame(res, normal)
    assert abs(d["out_of_plane_rms_mm"] - 3.0) < 1e-6
    assert d["in_plane_rms_mm"] < 1e-6


def test_board_pure_in_plane() -> None:
    normal = np.array([0.0, 0.0, 1.0])
    res = np.array([[0.004, 0.0, 0.0]])  # 4 mm in-plane
    d = decompose_board_frame(res, normal)
    assert d["out_of_plane_rms_mm"] < 1e-6
    assert abs(d["in_plane_rms_mm"] - 4.0) < 1e-6


def test_range_pure_along_ray() -> None:
    ray = np.array([[0.0, 0.0, 2.0]])  # non-unit ray; normalised internally
    res = np.array([[0.0, 0.0, 0.005]])  # 5 mm along ray
    d = decompose_range_lateral(res, ray)
    assert abs(d["range_rms_mm"] - 5.0) < 1e-6
    assert d["lateral_rms_mm"] < 1e-6


def test_range_pure_perpendicular() -> None:
    ray = np.array([[0.0, 0.0, 1.0]])
    res = np.array([[0.006, 0.0, 0.0]])  # 6 mm perpendicular to ray
    d = decompose_range_lateral(res, ray)
    assert d["range_rms_mm"] < 1e-6
    assert abs(d["lateral_rms_mm"] - 6.0) < 1e-6


def test_range_45_degree_mix() -> None:
    ray = np.array([[0.0, 0.0, 1.0]])
    mag = 0.010  # 10 mm at 45 deg in x-z plane
    res = np.array([[mag / np.sqrt(2), 0.0, mag / np.sqrt(2)]])
    d = decompose_range_lateral(res, ray)
    expect = 10.0 / np.sqrt(2)
    assert abs(d["range_rms_mm"] - expect) < 1e-6
    assert abs(d["lateral_rms_mm"] - expect) < 1e-6
    assert abs(d["range_dominance"] - 1.0) < 1e-6


def test_board_frame_residuals_reconstruction() -> None:
    # Identity rotation, translation; residual = dst - src.
    R = np.eye(3)
    t = np.array([1.0, 2.0, 3.0])
    src = np.array([[0.0, 0.0, 0.0], [0.06, 0.0, 0.0]])
    dst = (R @ src.T).T + t + np.array([[0.0, 0.0, 0.002], [0.001, 0.0, 0.0]])
    res, normal = board_frame_residuals(R, t, src, dst)
    assert np.allclose(res[0], [0.0, 0.0, 0.002])
    assert np.allclose(res[1], [0.001, 0.0, 0.0])
    assert np.allclose(normal, [0.0, 0.0, 1.0])  # R[:,2] for identity


if __name__ == "__main__":
    test_board_pure_normal();                  print("  [OK] board: pure normal -> out-of-plane only")
    test_board_pure_in_plane();                print("  [OK] board: pure in-plane -> in-plane only")
    test_range_pure_along_ray();               print("  [OK] range: pure along-ray -> range only")
    test_range_pure_perpendicular();           print("  [OK] range: pure perpendicular -> lateral only")
    test_range_45_degree_mix();                print("  [OK] range: 45deg mix -> range==lateral, dom==1")
    test_board_frame_residuals_reconstruction(); print("  [OK] board_frame_residuals reconstructs res + normal")
    print("test_error_decomposition OK")
