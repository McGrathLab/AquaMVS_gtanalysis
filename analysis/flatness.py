"""
AquaMVS Analysis — Flatness & Geometry Numerics
=================================================
Pure-numeric, dataset-free functions for MET-01 and MET-02 computations.

ORDERING INVARIANT: all inputs here must come from the raw MVS reconstruction
as-is (no Umeyama/ICP/scaling to the ideal board). Phase 4 may align afterward;
these functions are called before that step.

Exports
-------
robust_plane_fit          - RANSAC + SVD refit; residual RMS in mm.
plane_tilt_deg            - Angle between a fitted normal and a reference direction.
board_size_from_corners   - Median inter-corner spacing from ChArUco corner 3-D positions.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

# Allow running from the repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from analysis.corner_transfer import fit_board_plane


# ── Robust plane fit (MET-01 core primitive) ───────────────────────────────────

def robust_plane_fit(
    points3d: np.ndarray,
    dist_threshold: float = 0.002,   # 2 mm in metres
    n_iters: int = 200,
    min_inlier_frac: float = 0.5,
    seed: int = 0,
) -> dict:
    """
    RANSAC + SVD robust plane fit on a (M, 3) dense point cloud.

    Algorithm
    ---------
    1. RANSAC: for each iteration sample 3 non-collinear points, build a
       candidate plane, count inliers within dist_threshold metres (point-to-plane
       |signed distance|). Track the best (max inlier count) candidate.
    2. REFIT: take the best inlier set and refit the plane via
       analysis.corner_transfer.fit_board_plane (SVD / total-least-squares).
    3. Report RMS: rms_mm = sqrt(mean(residuals_inliers**2)) * 1000.

    ORDERING INVARIANT: points3d must be in the raw MVS frame — no scaling or
    rigid alignment to the ideal board may have run before calling this function.

    Parameters
    ----------
    points3d :       (M, 3) float array of 3-D points in metres.
    dist_threshold : Inlier distance threshold in metres (default 2 mm).
    n_iters :        RANSAC iteration count (default 200).
    min_inlier_frac: Minimum inlier fraction (informational; used as soft floor).
    seed :           Random seed for reproducibility.

    Returns
    -------
    dict with keys:
        point       : (3,) float64 — a point on the fitted plane; None if degenerate.
        normal      : (3,) float64 — unit normal of the fitted plane; None if degenerate.
        inlier_mask : (M,) bool — True for inlier points (from RANSAC, pre-refit).
        rms_mm      : float — RMS of inlier point-to-plane residuals in mm; nan if degenerate.
        n_inliers   : int — number of inlier points.
        n_points    : int — total input point count.
    """
    points3d = np.asarray(points3d, dtype=np.float64)
    n = len(points3d)

    _degen = {
        "point": None,
        "normal": None,
        "inlier_mask": np.zeros(n, dtype=bool),
        "rms_mm": float("nan"),
        "n_inliers": 0,
        "n_points": n,
    }

    if n < 3:
        return _degen

    rng = np.random.default_rng(seed)
    best_inliers = np.zeros(n, dtype=bool)
    best_count = 0

    for _ in range(n_iters):
        idx = rng.choice(n, size=3, replace=False)
        p0, p1, p2 = points3d[idx[0]], points3d[idx[1]], points3d[idx[2]]

        v1 = p1 - p0
        v2 = p2 - p0
        normal_cand = np.cross(v1, v2)
        norm_cand = np.linalg.norm(normal_cand)
        if norm_cand < 1e-12:
            continue  # collinear sample; skip

        normal_cand /= norm_cand
        signed_dist = (points3d - p0) @ normal_cand
        inliers = np.abs(signed_dist) <= dist_threshold
        count = int(inliers.sum())

        if count > best_count:
            best_count = count
            best_inliers = inliers.copy()

    if best_count < 3:
        return _degen

    # Refit the plane on the RANSAC inlier set using SVD / total-least-squares
    result = fit_board_plane(points3d[best_inliers])
    if result is None:
        return {**_degen, "inlier_mask": best_inliers, "n_inliers": best_count}

    point, normal = result

    # RMS of inlier residuals against the REFIT plane
    signed_dist_inliers = (points3d[best_inliers] - point) @ normal
    rms_mm = float(np.sqrt(np.mean(signed_dist_inliers ** 2)) * 1000.0)

    return {
        "point": point,
        "normal": normal,
        "inlier_mask": best_inliers,
        "rms_mm": rms_mm,
        "n_inliers": best_count,
        "n_points": n,
    }


# ── Tilt angle ─────────────────────────────────────────────────────────────────

def plane_tilt_deg(normal: np.ndarray, reference: np.ndarray) -> float:
    """
    Angle in degrees between a fitted plane normal and a reference direction.

    Sign-agnostic: abs(dot(normal, reference)) is used so that flipping the
    normal (which is ambiguous for plane fits) does not change the reported angle.
    The result is in [0, 90] degrees.

    Parameters
    ----------
    normal    : (3,) unit vector — fitted plane normal.
    reference : (3,) unit vector — reference direction (e.g. calib.interface_normal).

    Returns
    -------
    Angle in degrees in [0, 90].
    """
    n = np.asarray(normal, dtype=np.float64).ravel()
    r = np.asarray(reference, dtype=np.float64).ravel()

    n_norm = np.linalg.norm(n)
    r_norm = np.linalg.norm(r)
    if n_norm < 1e-12 or r_norm < 1e-12:
        return float("nan")

    n = n / n_norm
    r = r / r_norm

    cos_angle = float(np.dot(n, r))
    cos_angle = float(np.clip(abs(cos_angle), 0.0, 1.0))
    return float(np.degrees(np.arccos(cos_angle)))


# ── Board size from corners (MET-02 size/consistency primitive) ────────────────

def board_size_from_corners(
    corner_ids: np.ndarray,
    points_xyz: np.ndarray,
    board_spec,
) -> dict:
    """
    Estimate the reconstructed ChArUco square edge length from 3-D corner positions.

    Maps each corner_id to its grid position (row, col) on the
    (squares_x-1) x (squares_y-1) internal-corner grid:
        n_cols     = board_spec.squares_x - 1   (= 11 for the AquaMVS board)
        n_rows     = board_spec.squares_y - 1   (= 8)
        corner_id  = row * n_cols + col

    Measures the median 3-D distance between all horizontally- and vertically-
    adjacent corner pairs and converts to mm.  This estimates the reconstructed
    square edge length in mm.

    NOTE — MET-02 consistency framing: this function is used to measure how the
    reconstructed square size VARIES across the working volume (depth, lateral
    position, tilt), NOT to check absolute accuracy.  Absolute size correctness
    is the partly-circular MET-04 (Phase 4).  The variation reported here is
    non-circular even when global scale is locked.

    Parameters
    ----------
    corner_ids : (N,) int array — ChArUco corner IDs (0–87 for an 11×8 grid).
    points_xyz : (N, 3) float array — 3-D positions in metres (may contain
                 multiple observations per corner_id; they are averaged).
    board_spec : Object with squares_x (int) and squares_y (int) attributes.

    Returns
    -------
    dict with keys:
        size_mm (float) : Median inter-corner spacing in mm; NaN if < 1 pair.
        n_pairs (int)   : Number of adjacent corner pairs used for the median.
    """
    corner_ids = np.asarray(corner_ids, dtype=np.int32).ravel()
    points_xyz = np.asarray(points_xyz, dtype=np.float64).reshape(-1, 3)

    n_cols = int(board_spec.squares_x) - 1  # 11

    # Average multiple observations for the same corner_id
    pos_sum: dict[int, np.ndarray] = {}
    pos_cnt: dict[int, int] = {}
    for cid_raw, pt in zip(corner_ids, points_xyz):
        cid = int(cid_raw)
        if cid in pos_sum:
            pos_sum[cid] += pt
            pos_cnt[cid] += 1
        else:
            pos_sum[cid] = pt.copy()
            pos_cnt[cid] = 1

    pos_map = {cid: pos_sum[cid] / pos_cnt[cid] for cid in pos_sum}

    # Collect adjacent-pair 3-D distances (each pair counted once)
    distances: list[float] = []
    for cid, pt in pos_map.items():
        row = cid // n_cols
        col = cid % n_cols

        # Horizontal right neighbour: (row, col+1)
        h_id = row * n_cols + (col + 1)
        if h_id in pos_map:
            distances.append(float(np.linalg.norm(pos_map[h_id] - pt)))

        # Vertical lower neighbour: (row+1, col)
        v_id = (row + 1) * n_cols + col
        if v_id in pos_map:
            distances.append(float(np.linalg.norm(pos_map[v_id] - pt)))

    if len(distances) < 1:
        return {"size_mm": float("nan"), "n_pairs": 0}

    size_mm = float(np.median(distances) * 1000.0)
    return {"size_mm": size_mm, "n_pairs": len(distances)}
