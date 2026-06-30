"""
Synthetic unit tests for analysis/cross_camera.py

Tests (no pytest required — plain assert + if __name__ == "__main__"):
  1. per_corner_dispersion on two cameras 10 mm apart
     -> rms_mm ~= 5.0, max_pairwise_mm ~= 10.0
  2. per_corner_dispersion on three cameras at a known spread
     -> matches closed-form RMS
  3. included_cameras with {A:52, B:12, C:2}, min_corners=6
     -> included {A,B}, excluded {C:2}
  4. frame_agreement: camera C (2-corner glimpse) excluded; its distant points do NOT
     inflate frame_rms_mm
  5. frame_agreement: corner seen by only ONE included camera is skipped (not an error)
  6. Board-blind camera (0 rows) never appears -> no error contribution

Run:
    python tests/test_cross_camera.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.cross_camera import (
    frame_agreement,
    included_cameras,
    per_camera_coverage,
    per_corner_dispersion,
)


# ---------------------------------------------------------------------------
# Test 1: Two cameras 10 mm apart
# ---------------------------------------------------------------------------

def test_per_corner_dispersion_two_cameras() -> None:
    """Two cameras 10 mm apart: rms_mm == 5.0, max_pairwise_mm == 10.0."""
    # A at origin; B at +10 mm along Z
    pts = {
        "camA": np.array([0.0, 0.0, 0.000]),
        "camB": np.array([0.0, 0.0, 0.010]),
    }
    result = per_corner_dispersion(pts)
    # Centroid = (0, 0, 0.005); each point is 5 mm away -> rms = 5 mm
    assert abs(result["rms_mm"] - 5.0) < 1e-6, (
        f"rms_mm expected 5.0, got {result['rms_mm']}"
    )
    assert abs(result["max_pairwise_mm"] - 10.0) < 1e-6, (
        f"max_pairwise_mm expected 10.0, got {result['max_pairwise_mm']}"
    )
    assert result["n_cameras"] == 2


# ---------------------------------------------------------------------------
# Test 2: Three cameras — closed-form RMS
# ---------------------------------------------------------------------------

def test_per_corner_dispersion_three_cameras() -> None:
    """Three cameras at known positions match the closed-form RMS."""
    # Points (metres): 0.000, 0.006, 0.003 along X
    # Centroid = 0.003
    # Distances: 0.003, 0.003, 0.000 (metres)
    # RMS = sqrt((0.003^2 + 0.003^2 + 0.000^2) / 3) * 1000 mm
    pts = {
        "camA": np.array([0.000, 0.0, 0.0]),
        "camB": np.array([0.006, 0.0, 0.0]),
        "camC": np.array([0.003, 0.0, 0.0]),
    }
    dists_sq = np.array([0.003**2, 0.003**2, 0.0**2])
    expected_rms = float(np.sqrt(np.mean(dists_sq)) * 1000.0)

    result = per_corner_dispersion(pts)
    assert abs(result["rms_mm"] - expected_rms) < 1e-6, (
        f"rms_mm expected {expected_rms:.6f}, got {result['rms_mm']:.6f}"
    )
    assert result["n_cameras"] == 3


# ---------------------------------------------------------------------------
# Test 3: Coverage threshold
# ---------------------------------------------------------------------------

def test_included_cameras_threshold() -> None:
    """Coverage {A:52, B:12, C:2} with min_corners=6 -> included {A,B}, excluded {C:2}."""
    coverage = {"A": 52, "B": 12, "C": 2}
    inc, exc = included_cameras(coverage, min_corners=6)
    assert inc == {"A", "B"}, f"Expected {{A,B}}, got {inc}"
    assert exc == {"C": 2}, f"Expected {{C:2}}, got {exc}"


# ---------------------------------------------------------------------------
# Test 4: Glimpse camera excluded from frame_agreement
# ---------------------------------------------------------------------------

def test_frame_agreement_glimpse_excluded() -> None:
    """Camera C (excluded glimpse) with very distant points must NOT inflate rms_mm."""
    # Cameras A and B are included; C is excluded (2-corner glimpse not in coverage threshold).
    # A and B agree well (~0.5 mm); C is 1 m away and excluded.
    included = {"A", "B"}

    cam_arr = np.array(["A", "B", "C", "A", "B", "C"])
    cid_arr = np.array([0,   0,   0,   1,   1,   1], dtype=np.int32)
    pts_arr = np.array(
        [
            [0.0, 0.0, 0.000],  # A corner 0
            [0.0, 0.0, 0.001],  # B corner 0  (1 mm from A)
            [0.0, 0.0, 1.000],  # C corner 0  (1 m away — excluded)
            [1.0, 0.0, 0.000],  # A corner 1
            [1.0, 0.0, 0.001],  # B corner 1  (1 mm from A)
            [1.0, 0.0, 1.000],  # C corner 1  (1 m away — excluded)
        ],
        dtype=np.float32,
    )
    corners = {"camera_id": cam_arr, "corner_id": cid_arr, "points": pts_arr}

    result = frame_agreement(corners, included_cams=included, min_cameras=2)

    assert result["n_corners_compared"] == 2, (
        f"Expected 2 corners compared, got {result['n_corners_compared']}"
    )
    assert result["n_cameras_included"] == 2
    # Without C: centroid of each corner is the midpoint between A and B (0.5 mm apart each)
    # -> each per-corner rms ~= 0.5 mm -> frame_rms ~= 0.5 mm
    assert result["frame_rms_mm"] < 1.0, (
        f"frame_rms_mm should be < 1 mm without C, got {result['frame_rms_mm']:.3f}"
    )


# ---------------------------------------------------------------------------
# Test 5: Corner with only one included camera is skipped
# ---------------------------------------------------------------------------

def test_frame_agreement_one_included_camera_skipped() -> None:
    """Corner seen by only ONE included camera must be skipped, not counted as error."""
    included = {"A", "B"}

    # Corner 0: A and B both see it (co-observed, counted)
    # Corner 1: only A sees it from included cameras; C (excluded) also sees it
    cam_arr = np.array(["A", "B", "A", "C"])
    cid_arr = np.array([0,   0,   1,   1], dtype=np.int32)
    pts_arr = np.array(
        [
            [0.0, 0.0, 0.000],  # A corner 0
            [0.0, 0.0, 0.002],  # B corner 0  (2 mm from A)
            [1.0, 0.0, 0.000],  # A corner 1  (only included cam -> skip)
            [1.0, 0.0, 1.000],  # C corner 1  (excluded)
        ],
        dtype=np.float32,
    )
    corners = {"camera_id": cam_arr, "corner_id": cid_arr, "points": pts_arr}

    result = frame_agreement(corners, included_cams=included, min_cameras=2)

    assert result["n_corners_compared"] == 1, (
        f"Expected 1 corner compared, got {result['n_corners_compared']}"
    )
    # Corner 0: centroid = (0,0,0.001), each point 1 mm from centroid -> rms_mm = 1.0
    assert abs(result["frame_rms_mm"] - 1.0) < 0.001, (
        f"Expected frame_rms_mm ~1.0, got {result['frame_rms_mm']:.4f}"
    )


# ---------------------------------------------------------------------------
# Test 6: Board-blind camera never appears, contributes no error
# ---------------------------------------------------------------------------

def test_board_blind_camera_no_error() -> None:
    """Board-blind camera (0 rows) never appears in coverage and contributes nothing."""
    # D is board-blind: it produced zero corner rows, so it never enters coverage
    coverage = {"A": 52, "B": 12}  # D is absent
    inc, exc = included_cameras(coverage, min_corners=6)
    assert "D" not in inc
    assert "D" not in exc

    # frame_agreement with A and B only — D's absence is a non-event
    included = {"A", "B"}
    cam_arr = np.array(["A", "B"])
    cid_arr = np.array([0,   0], dtype=np.int32)
    pts_arr = np.array(
        [
            [0.0, 0.0, 0.000],
            [0.0, 0.0, 0.002],
        ],
        dtype=np.float32,
    )
    corners = {"camera_id": cam_arr, "corner_id": cid_arr, "points": pts_arr}
    result = frame_agreement(corners, included_cams=included, min_cameras=2)

    assert result["n_corners_compared"] == 1
    assert not (result["frame_rms_mm"] != result["frame_rms_mm"])  # not NaN


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_per_corner_dispersion_two_cameras()
    print("  [OK] per_corner_dispersion: two cameras 10 mm apart (rms=5 mm, max_pw=10 mm)")

    test_per_corner_dispersion_three_cameras()
    print("  [OK] per_corner_dispersion: three cameras match closed-form RMS")

    test_included_cameras_threshold()
    print("  [OK] included_cameras: {A:52,B:12,C:2} min=6 -> included={A,B}, excluded={C:2}")

    test_frame_agreement_glimpse_excluded()
    print("  [OK] frame_agreement: excluded glimpse camera does not inflate rms_mm")

    test_frame_agreement_one_included_camera_skipped()
    print("  [OK] frame_agreement: corner with 1 included camera is skipped (not error)")

    test_board_blind_camera_no_error()
    print("  [OK] board-blind camera: 0 rows -> absent from coverage -> no error")

    print("test_cross_camera OK")
