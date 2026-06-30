"""
AquaMVS Analysis — Closed-Form Alignment Numerics (Phase 4)
===========================================================
Pure-numeric, dataset-free functions for the Phase 4 scale/alignment
consistency check (MET-04 absolute scale, MET-05 rigid inlier RMSE).

All correspondences here are KNOWN one-to-one (matched by ChArUco corner_id),
so the alignment is solved in closed form via Kabsch/Umeyama — there is no need
for ICP or any correspondence search.

ORDERING INVARIANT
------------------
These functions run AFTER the Phase 3 scale-independent headline numbers
(flatness, cross-camera agreement) have already been computed and locked.
They WRITE NOTHING to disk and must NEVER feed back into the Phase 3 metrics.
The numbers produced here are reported as an honest *consistency check*: the
60 mm ChArUco square is the calibration scale anchor (a system input), so a
near-zero scale error is partly true by construction and is contextualised
against the Maas (2015) factor-of-two refractive precision penalty.

Exports
-------
umeyama_fit            - Closed-form Kabsch/Umeyama fit (with or without scale).
rigid_inlier_fit       - Rigid (no-scale) fit with gross-outlier rejection + refit (MET-05).
build_consensus_corners- Per-frame, per-corner_id averaged consensus point.
ideal_board_corners    - (88,3) ideal board-local corner accessor (metres, z=0).
matched_arrays         - Build matched (src=ideal, dst=consensus) arrays by corner_id.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Tuple

# Allow running from the repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np


# ── Closed-form Umeyama / Kabsch fit ───────────────────────────────────────────

def umeyama_fit(src: np.ndarray, dst: np.ndarray, with_scale: bool) -> dict:
    """
    Closed-form Kabsch/Umeyama similarity fit for KNOWN one-to-one correspondence.

    Solves for (s, R, t) minimising || dst - (s * R @ src + t) ||^2 between the
    matched (N, 3) point sets `src` and `dst`.  With `with_scale=False` the scale
    is fixed to 1.0 (a pure rigid fit — rotation + translation only).

    Algorithm (Umeyama 1991)
    ------------------------
        mu_s = src.mean(0); mu_d = dst.mean(0)
        Xs = src - mu_s;    Xd = dst - mu_d
        Sigma = (Xd.T @ Xs) / N
        U, D, Vt = svd(Sigma)
        S = I; if det(U)*det(Vt) < 0: S[2,2] = -1     # reflection guard
        R = U @ S @ Vt
        if with_scale: s = (D * diag(S)).sum() / (mean ||Xs||^2)
        else:          s = 1.0
        t = mu_d - s * (R @ mu_s)

    Convention
    ----------
    `src` is the IDEAL board (board-local metres) and `dst` is the consensus MVS
    reconstruction (metres).  Then `s` is the reconstructed/ideal scale RATIO, so
    scale_error = s - 1  (>0 means the reconstruction is LARGER than the ideal).

    Parameters
    ----------
    src : (N, 3) float — source points (ideal board, metres).
    dst : (N, 3) float — destination points (consensus MVS corners, metres).
    with_scale : bool — fit an isotropic scale factor if True, else force s = 1.

    Returns
    -------
    dict with keys:
        s                    : float — fitted scale ratio (1.0 if not with_scale); nan if N < 3.
        R                    : (3, 3) float — rotation matrix (identity-ish if degenerate).
        t                    : (3,) float — translation vector.
        rms_mm               : float — sqrt(mean(sum(res**2, axis=1))) * 1000; nan if N < 3.
        per_corner_residual_mm : (N,) float — per-corner residual norm in mm.
        n                    : int — number of matched points.
    """
    src = np.asarray(src, dtype=np.float64).reshape(-1, 3)
    dst = np.asarray(dst, dtype=np.float64).reshape(-1, 3)
    n = len(src)

    if n != len(dst):
        raise ValueError(f"src/dst length mismatch: {n} vs {len(dst)}")

    if n < 3:
        return {
            "s": float("nan"),
            "R": np.eye(3),
            "t": np.zeros(3),
            "rms_mm": float("nan"),
            "per_corner_residual_mm": np.full(n, float("nan")),
            "n": n,
        }

    mu_s = src.mean(axis=0)
    mu_d = dst.mean(axis=0)
    Xs = src - mu_s
    Xd = dst - mu_d

    sigma = (Xd.T @ Xs) / n
    U, D, Vt = np.linalg.svd(sigma)

    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[2, 2] = -1.0  # reflection guard

    R = U @ S @ Vt

    if with_scale:
        var_s = float((Xs ** 2).sum() / n)
        if var_s > 1e-18:
            s = float((D * np.diag(S)).sum() / var_s)
        else:
            s = 1.0
    else:
        s = 1.0

    t = mu_d - s * (R @ mu_s)

    res = dst - (s * (R @ src.T).T + t)              # (N, 3) residual vectors
    per_corner_residual_mm = np.linalg.norm(res, axis=1) * 1000.0
    rms_mm = float(np.sqrt(np.mean(np.sum(res ** 2, axis=1))) * 1000.0)

    return {
        "s": s,
        "R": R,
        "t": t,
        "rms_mm": rms_mm,
        "per_corner_residual_mm": per_corner_residual_mm,
        "n": n,
    }


# ── Rigid (no-scale) fit with gross-outlier rejection (MET-05) ─────────────────

def rigid_inlier_fit(
    src: np.ndarray,
    dst: np.ndarray,
    abs_thresh_mm: float = 5.0,
    mad_k: float = 3.0,
    min_inliers: int = 3,
) -> dict:
    """
    MET-05 driver: rigid (NO-scale) alignment with gross-outlier rejection + refit.

    Procedure
    ---------
    1. Fit `umeyama_fit(src, dst, with_scale=False)` on ALL matched corners.
    2. Take the per-corner residual norms (mm) and reject gross outliers, keeping
       corners with residual <= max(abs_thresh_mm, median + mad_k * MAD), where
       MAD = median(|r - median(r)|).  This combines an absolute floor (so a tight
       cluster is not over-pruned) with a robust statistical cutoff.
    3. REFIT `umeyama_fit(with_scale=False)` on the inlier subset and report the
       inlier RMSE in mm.

    Outlier-rule defaults are Claude's discretion (see module/plan docstring):
        abs_thresh_mm = 5.0 mm  — absolute residual floor below which corners are
                                  always kept (board reconstruction noise is ~mm).
        mad_k         = 3.0     — robust (median + 3*MAD) statistical cutoff.
        min_inliers   = 3       — minimum corners required for a non-degenerate fit.

    If fewer than `min_inliers` survive, the all-corner fit is returned with
    `degenerate: True`.

    Parameters
    ----------
    src : (N, 3) float — ideal board corners (metres).
    dst : (N, 3) float — consensus MVS corners (metres).
    abs_thresh_mm : float — absolute residual floor (mm) for inlier keep.
    mad_k : float — MAD multiplier for the robust statistical cutoff.
    min_inliers : int — minimum inliers for a valid refit.

    Returns
    -------
    dict with keys:
        rms_mm      : float — inlier RMSE (mm) after refit; all-corner RMSE if degenerate.
        n_inliers   : int   — number of inliers used in the refit.
        n_total     : int   — total matched corners.
        inlier_mask : (N,) bool — True for corners kept as inliers.
        s           : float — scale (1.0 for the rigid fit).
        R           : (3, 3) float — refit rotation.
        t           : (3,) float — refit translation.
        abs_thresh_mm, mad_k, min_inliers : the parameters used.
        degenerate  : bool  — True if inliers < min_inliers (all-corner fit returned).
    """
    src = np.asarray(src, dtype=np.float64).reshape(-1, 3)
    dst = np.asarray(dst, dtype=np.float64).reshape(-1, 3)
    n_total = len(src)

    base = umeyama_fit(src, dst, with_scale=False)

    if n_total < min_inliers or not np.isfinite(base["rms_mm"]):
        return {
            "rms_mm": base["rms_mm"],
            "n_inliers": n_total,
            "n_total": n_total,
            "inlier_mask": np.ones(n_total, dtype=bool),
            "s": base["s"],
            "R": base["R"],
            "t": base["t"],
            "abs_thresh_mm": abs_thresh_mm,
            "mad_k": mad_k,
            "min_inliers": min_inliers,
            "degenerate": True,
        }

    r = base["per_corner_residual_mm"]
    med = float(np.median(r))
    mad = float(np.median(np.abs(r - med)))
    cutoff = max(abs_thresh_mm, med + mad_k * mad)
    inlier_mask = r <= cutoff

    if int(inlier_mask.sum()) < min_inliers:
        return {
            "rms_mm": base["rms_mm"],
            "n_inliers": n_total,
            "n_total": n_total,
            "inlier_mask": np.ones(n_total, dtype=bool),
            "s": base["s"],
            "R": base["R"],
            "t": base["t"],
            "abs_thresh_mm": abs_thresh_mm,
            "mad_k": mad_k,
            "min_inliers": min_inliers,
            "degenerate": True,
        }

    refit = umeyama_fit(src[inlier_mask], dst[inlier_mask], with_scale=False)

    return {
        "rms_mm": refit["rms_mm"],
        "n_inliers": int(inlier_mask.sum()),
        "n_total": n_total,
        "inlier_mask": inlier_mask,
        "s": refit["s"],
        "R": refit["R"],
        "t": refit["t"],
        "abs_thresh_mm": abs_thresh_mm,
        "mad_k": mad_k,
        "min_inliers": min_inliers,
        "degenerate": False,
    }


# ── Per-frame consensus corner builder ─────────────────────────────────────────

def build_consensus_corners(
    frame_idx: np.ndarray,
    camera_id: np.ndarray,
    corner_id: np.ndarray,
    points_xyz_m: np.ndarray,
    frame: int,
) -> Dict[int, np.ndarray]:
    """
    Build ONE consensus 3-D point per ChArUco corner_id for a single frame.

    For the requested `frame`, defensively keeps only finite & Z>0 rows, groups
    the surviving rows by corner_id across all co-observing cameras, and averages
    their (X, Y, Z) into a single consensus point (metres) per corner_id.

    Parameters
    ----------
    frame_idx    : (N,) int — output frame index per corner row.
    camera_id    : (N,) str/object — camera id per row (unused for averaging, kept
                   for signature symmetry with the corners arrays).
    corner_id    : (N,) int — ChArUco corner id per row.
    points_xyz_m : (N, 3) float — corner positions in MVS world metres.
    frame        : int — the frame to build consensus corners for.

    Returns
    -------
    dict[int corner_id -> (3,) float64 consensus point in metres].
    """
    frame_idx = np.asarray(frame_idx).ravel()
    corner_id = np.asarray(corner_id).ravel()
    points_xyz_m = np.asarray(points_xyz_m, dtype=np.float64).reshape(-1, 3)

    sel = frame_idx == frame
    fin = np.isfinite(points_xyz_m).all(axis=1) & (points_xyz_m[:, 2] > 0.0)
    keep = sel & fin

    cids = corner_id[keep]
    pts = points_xyz_m[keep]

    pos_sum: Dict[int, np.ndarray] = {}
    pos_cnt: Dict[int, int] = {}
    for cid_raw, pt in zip(cids, pts):
        cid = int(cid_raw)
        if cid in pos_sum:
            pos_sum[cid] += pt
            pos_cnt[cid] += 1
        else:
            pos_sum[cid] = pt.copy()
            pos_cnt[cid] = 1

    return {cid: pos_sum[cid] / pos_cnt[cid] for cid in pos_sum}


# ── Ideal board corner accessor ────────────────────────────────────────────────

def ideal_board_corners(board) -> np.ndarray:
    """
    Return the ideal ChArUco internal-corner positions in board-local metres.

    Thin wrapper over the OpenCV board geometry: returns the (88, 3) float64
    chessboard corners (board-local, z = 0) indexed by corner_id 0..87.

    Parameters
    ----------
    board : BoardGeometry from analysis.charuco_detect.build_board_geometry.

    Returns
    -------
    (88, 3) float64 array of board-local corner positions in metres.
    """
    obj_all = board.get_opencv_board().getChessboardCorners()
    return np.asarray(obj_all, dtype=np.float64).reshape(-1, 3)


# ── Matched-array builder ──────────────────────────────────────────────────────

def matched_arrays(
    consensus: Dict[int, np.ndarray],
    ideal_all: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Build matched (src=ideal, dst=consensus) arrays for the corner_ids present.

    For the sorted corner_ids in `consensus`, returns:
        ids           : (N,) int     — sorted corner ids.
        src_ideal     : (N, 3) float — ideal_all[ids] (board-local metres).
        dst_consensus : (N, 3) float — stacked consensus points (metres).

    Parameters
    ----------
    consensus : dict[int -> (3,) array] from build_consensus_corners.
    ideal_all : (88, 3) array from ideal_board_corners.

    Returns
    -------
    (ids, src_ideal, dst_consensus) tuple.
    """
    ideal_all = np.asarray(ideal_all, dtype=np.float64).reshape(-1, 3)
    ids = np.array(sorted(consensus.keys()), dtype=np.int32)

    if len(ids) == 0:
        return ids, np.zeros((0, 3)), np.zeros((0, 3))

    src_ideal = ideal_all[ids]
    dst_consensus = np.stack([consensus[int(cid)] for cid in ids], axis=0)
    return ids, src_ideal, dst_consensus
