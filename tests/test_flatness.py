"""
Synthetic unit tests for analysis/flatness.py.

No pytest dependency — run directly:
    python tests/test_flatness.py

Checks:
  1. robust_plane_fit recovers noise RMS from a near-planar synthetic cloud.
  2. Gross outliers are excluded by RANSAC inlier mask and do not inflate rms_mm.
  3. plane_tilt_deg returns 0 for aligned normals, 90 for perpendicular.
  4. board_size_from_corners returns ~60 mm for a 0.06-m grid on a tilted plane.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from analysis.flatness import robust_plane_fit, plane_tilt_deg, board_size_from_corners
from analysis.corner_transfer import intersect_ray_plane


# ── Minimal board_spec stand-in ────────────────────────────────────────────────

class _BoardSpec:
    squares_x: int = 12
    squares_y: int = 9
    square_size: float = 0.06


# ── Test 1: plane fit recovers noise RMS from near-planar cloud ────────────────

def test_plane_fit_clean_noise() -> None:
    """
    Build z = a*x + b*y + c with small Gaussian noise (known sigma).
    robust_plane_fit should recover rms_mm within ~30% of sigma * 1000
    and classify nearly all points as inliers.
    """
    rng = np.random.default_rng(42)
    n = 2000
    sigma = 0.0005  # 0.5 mm in metres

    x = rng.uniform(-0.3, 0.3, n)
    y = rng.uniform(-0.2, 0.2, n)
    a, b, c = 0.1, -0.07, 0.5   # arbitrary tilted plane
    z = a * x + b * y + c + rng.normal(0, sigma, n)
    points = np.stack([x, y, z], axis=1)

    result = robust_plane_fit(points, dist_threshold=0.002, n_iters=200, seed=0)

    assert result["normal"] is not None, "normal must not be None for clean cloud"
    assert not np.isnan(result["rms_mm"]), "rms_mm must not be NaN for clean cloud"

    # rms_mm should be within 30% of the true noise sigma*1000
    expected_rms = sigma * 1000.0
    tolerance = 0.30 * expected_rms
    assert abs(result["rms_mm"] - expected_rms) < tolerance, (
        f"rms_mm={result['rms_mm']:.4f} not within 30% of expected {expected_rms:.4f}"
    )

    # Nearly all points should be inliers (threshold 2 mm >> noise 0.5 mm)
    inlier_frac = result["n_inliers"] / n
    assert inlier_frac > 0.95, (
        f"inlier fraction {inlier_frac:.3f} < 0.95 for clean near-planar cloud"
    )


# ── Test 2: gross outliers are excluded; rms_mm stays near clean noise ─────────

def test_plane_fit_with_outliers() -> None:
    """
    Add ~10% gross outliers far off the plane.
    RANSAC inlier_mask must exclude them; rms_mm must remain near the clean-noise value.
    """
    rng = np.random.default_rng(7)
    n_clean = 1000
    n_outlier = 100
    sigma = 0.0005  # 0.5 mm

    x = rng.uniform(-0.3, 0.3, n_clean)
    y = rng.uniform(-0.2, 0.2, n_clean)
    z = 0.05 * x - 0.03 * y + 0.8 + rng.normal(0, sigma, n_clean)
    clean = np.stack([x, y, z], axis=1)

    # Outliers: random positions far from the plane
    outliers = rng.uniform(-5, 5, (n_outlier, 3))
    outliers[:, 2] += 5.0  # push them far above
    points = np.vstack([clean, outliers])

    result = robust_plane_fit(points, dist_threshold=0.002, n_iters=300, seed=0)

    assert result["normal"] is not None, "normal must not be None even with outliers"
    assert not np.isnan(result["rms_mm"]), "rms_mm must not be NaN"

    # Inlier set should contain few/no outliers
    inlier_indices = np.where(result["inlier_mask"])[0]
    outlier_indices = set(range(n_clean, n_clean + n_outlier))
    inlier_outlier_count = sum(1 for i in inlier_indices if i in outlier_indices)
    assert inlier_outlier_count < 5, (
        f"{inlier_outlier_count} gross outliers included in inlier set (expected < 5)"
    )

    # rms_mm should still be near clean-noise level
    expected_rms = sigma * 1000.0
    tolerance = 0.40 * expected_rms
    assert abs(result["rms_mm"] - expected_rms) < tolerance, (
        f"rms_mm={result['rms_mm']:.4f} inflated by outliers vs expected ~{expected_rms:.4f}"
    )


# ── Test 3: plane_tilt_deg edge cases ─────────────────────────────────────────

def test_plane_tilt_deg() -> None:
    """
    plane_tilt_deg([0,0,1], [0,0,1]) must be ~0 degrees.
    plane_tilt_deg([1,0,0], [0,0,1]) must be ~90 degrees.
    """
    tilt_parallel = plane_tilt_deg([0, 0, 1], [0, 0, 1])
    assert abs(tilt_parallel) < 0.01, (
        f"Parallel normals should give ~0 deg, got {tilt_parallel:.4f}"
    )

    tilt_perp = plane_tilt_deg([1, 0, 0], [0, 0, 1])
    assert abs(tilt_perp - 90.0) < 0.01, (
        f"Perpendicular normals should give ~90 deg, got {tilt_perp:.4f}"
    )

    # Sign-agnostic: flipped normal gives same result
    tilt_flipped = plane_tilt_deg([0, 0, -1], [0, 0, 1])
    assert abs(tilt_flipped) < 0.01, (
        f"Flipped parallel normal should still give ~0 deg, got {tilt_flipped:.4f}"
    )

    # 45-degree case
    tilt_45 = plane_tilt_deg([1, 0, 1], [0, 0, 1])
    assert abs(tilt_45 - 45.0) < 0.1, (
        f"45-degree normal should give ~45 deg, got {tilt_45:.4f}"
    )


# ── Test 4: board_size_from_corners on a tilted 11×8 grid ─────────────────────

def test_board_size_from_corners() -> None:
    """
    Build a synthetic 11×8 internal-corner grid spaced exactly 0.06 m,
    placed on a tilted plane (30-degree rotation around X axis).
    board_size_from_corners should return size_mm ~= 60 within 1 mm.
    """
    n_cols = 11
    n_rows = 8
    spacing = 0.06  # metres

    # Build grid on XY plane, then tilt 30 degrees around X axis
    angle = np.radians(30.0)
    R = np.array([
        [1,           0,            0],
        [0,  np.cos(angle), -np.sin(angle)],
        [0,  np.sin(angle),  np.cos(angle)],
    ])

    corner_ids_list = []
    points_list = []
    for row in range(n_rows):
        for col in range(n_cols):
            cid = row * n_cols + col
            pt_flat = np.array([col * spacing, row * spacing, 0.0])
            pt_tilted = R @ pt_flat
            corner_ids_list.append(cid)
            points_list.append(pt_tilted)

    corner_ids = np.array(corner_ids_list, dtype=np.int32)
    points_xyz = np.array(points_list, dtype=np.float64)

    spec = _BoardSpec()
    result = board_size_from_corners(corner_ids, points_xyz, spec)

    assert not np.isnan(result["size_mm"]), "size_mm must not be NaN for complete grid"
    assert result["n_pairs"] > 0, "n_pairs must be positive"
    assert abs(result["size_mm"] - 60.0) < 1.0, (
        f"size_mm={result['size_mm']:.4f} not within 1 mm of 60.0"
    )


# ── Test 5: degenerate guards ──────────────────────────────────────────────────

def test_degenerate_inputs() -> None:
    """robust_plane_fit handles < 3 points gracefully."""
    result_0 = robust_plane_fit(np.zeros((0, 3)))
    assert result_0["normal"] is None
    assert np.isnan(result_0["rms_mm"])
    assert result_0["n_inliers"] == 0

    result_2 = robust_plane_fit(np.array([[0, 0, 0], [1, 0, 0]], dtype=float))
    assert result_2["normal"] is None
    assert np.isnan(result_2["rms_mm"])


# ── Test 6: board_size with too few corners ────────────────────────────────────

def test_board_size_no_pairs() -> None:
    """board_size_from_corners returns NaN size when no adjacent pairs exist."""
    # Only one corner — no neighbours possible
    spec = _BoardSpec()
    result = board_size_from_corners(
        np.array([0], dtype=np.int32),
        np.array([[0.0, 0.0, 0.0]]),
        spec,
    )
    assert np.isnan(result["size_mm"]), "size_mm should be NaN with zero adjacent pairs"
    assert result["n_pairs"] == 0


# ── Test: ray-plane intersection rejects non-physical (behind-camera) hits ──────

def test_intersect_ray_plane_rejects_behind_camera() -> None:
    """intersect_ray_plane returns None when the hit is behind the ray origin.

    Guards the Phase-2 hardening: a degenerate seed plane must not emit a
    negative-depth corner (the real frame-2 / e3v83e9 failure mode).
    """
    origin = np.array([0.0, 0.0, 0.0])
    direction = np.array([0.0, 0.0, 1.0])  # ray points +Z

    # Plane in front (z = +1.3): valid hit at t = +1.3
    hit = intersect_ray_plane(origin, direction, np.array([0.0, 0.0, 1.3]),
                              np.array([0.0, 0.0, 1.0]))
    assert hit is not None and abs(hit[2] - 1.3) < 1e-9

    # Plane behind (z = -0.4): t < 0 -> non-physical -> None
    behind = intersect_ray_plane(origin, direction, np.array([0.0, 0.0, -0.4]),
                                 np.array([0.0, 0.0, 1.0]))
    assert behind is None, "behind-camera intersection must be rejected"

    # Ray parallel to plane -> None
    parallel = intersect_ray_plane(origin, np.array([1.0, 0.0, 0.0]),
                                   np.array([0.0, 0.0, 1.3]), np.array([0.0, 0.0, 1.0]))
    assert parallel is None, "parallel ray must be rejected"


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running test_flatness ...")

    test_plane_fit_clean_noise()
    print("  [PASS] test_plane_fit_clean_noise")

    test_plane_fit_with_outliers()
    print("  [PASS] test_plane_fit_with_outliers")

    test_plane_tilt_deg()
    print("  [PASS] test_plane_tilt_deg")

    test_board_size_from_corners()
    print("  [PASS] test_board_size_from_corners")

    test_degenerate_inputs()
    print("  [PASS] test_degenerate_inputs")

    test_board_size_no_pairs()
    print("  [PASS] test_board_size_no_pairs")

    test_intersect_ray_plane_rejects_behind_camera()
    print("  [PASS] test_intersect_ray_plane_rejects_behind_camera")

    print("test_flatness OK")
