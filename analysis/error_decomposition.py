"""
AquaMVS Analysis — Error-Direction Decomposition (MET-06)
=========================================================
Decompose reconstruction residuals into physically meaningful directions, so the
*direction* of the error — not just its magnitude — can be reported. Two splits:

  A. In-plane vs out-of-plane (BOARD frame)
     From the MET-05 rigid (no-scale) alignment of consensus corners to the ideal
     board: each residual vector is split into the board-plane span vs the board
     normal. Out-of-plane ~ flatness-type error; in-plane ~ lateral grid distortion.

  B. Range vs lateral (CAMERA / REFRACTION frame)  -- the refraction-relevant test
     Each per-camera corner's offset from the cross-camera consensus is split into
     the component ALONG that camera's in-water viewing ray (range/depth) vs
     PERPENDICULAR to it (lateral). Refraction biases range, so a range-dominated
     residual is the refractive signature; a balanced one is generic noise.

Both reuse Phase 3/4 machinery (consensus corners, the rigid fit, cast_ray) and
are computed in the RAW MVS frame — no new alignment of the Phase 3 numbers.

Key exports
-----------
board_frame_residuals   - residual vectors of inliers in world frame + board normal.
decompose_board_frame   - in-plane vs out-of-plane RMS from residual vectors + normal.
decompose_range_lateral - range vs lateral RMS from residual vectors + ray directions.
"""

from __future__ import annotations

import logging
from typing import Dict, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ── Local-frame components (for the anisotropy figure) ──────────────────────────

def local_frame_components(
    residuals: np.ndarray,
    ray_dirs: np.ndarray,
) -> Dict[str, np.ndarray]:
    """
    Express each residual in its own (range, lat_u, lat_v) orthonormal frame.

    For each observation the range axis is the unit viewing ray; the two lateral
    axes (lat_u, lat_v) are an arbitrary orthonormal basis of the perpendicular
    plane. Returns SIGNED components in mm. Used to build the pooled
    range-vs-lateral scatter / covariance ellipse: stacking (lat_u, range) and
    (lat_v, range) gives a lateral-symmetric cloud whose elongation along range
    is the refraction signature.

    Returns
    -------
    dict with range_mm (N,), lat_u_mm (N,), lat_v_mm (N,) — all signed, mm.
    """
    residuals = np.asarray(residuals, dtype=np.float64).reshape(-1, 3)
    ray_dirs = np.asarray(ray_dirs, dtype=np.float64).reshape(-1, 3)
    n = len(residuals)
    if n == 0:
        return {"range_mm": np.zeros(0), "lat_u_mm": np.zeros(0), "lat_v_mm": np.zeros(0)}

    norms = np.linalg.norm(ray_dirs, axis=1, keepdims=True)
    norms = np.where(norms > 1e-12, norms, 1.0)
    w = ray_dirs / norms                                   # (N,3) unit range axis

    # Build a perpendicular basis per row: u = normalize(ref x w), v = w x u.
    # Choose ref = world-up unless near-parallel to w, then ref = world-x.
    up = np.tile(np.array([0.0, 0.0, 1.0]), (n, 1))
    alt = np.tile(np.array([1.0, 0.0, 0.0]), (n, 1))
    near_parallel = np.abs(np.sum(w * up, axis=1)) > 0.95
    ref = np.where(near_parallel[:, None], alt, up)

    u = np.cross(ref, w)
    u /= np.maximum(np.linalg.norm(u, axis=1, keepdims=True), 1e-12)
    v = np.cross(w, u)                                      # already unit

    range_mm = np.sum(residuals * w, axis=1) * 1000.0
    lat_u_mm = np.sum(residuals * u, axis=1) * 1000.0
    lat_v_mm = np.sum(residuals * v, axis=1) * 1000.0
    return {"range_mm": range_mm, "lat_u_mm": lat_u_mm, "lat_v_mm": lat_v_mm}


# ── Geometry helpers ────────────────────────────────────────────────────────────

def board_frame_residuals(
    R: np.ndarray,
    t: np.ndarray,
    src_ideal: np.ndarray,
    dst_consensus: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Reconstruct the rigid (no-scale) residual vectors and the board normal.

    The MET-05 fit maps ideal board corners (board-local, z=0) -> consensus MVS
    corners via  x_world = R @ x_local + t  (scale = 1). The board's local axes in
    world are therefore the columns of R; the board normal is R[:, 2].

    Parameters
    ----------
    R : (3,3) rotation from the rigid fit.
    t : (3,) translation from the rigid fit.
    src_ideal : (N,3) ideal board-local corners (the fit's source).
    dst_consensus : (N,3) consensus MVS corners (the fit's target), world metres.

    Returns
    -------
    (residual_vectors (N,3) world-frame metres, board_normal (3,) unit).
    """
    R = np.asarray(R, dtype=np.float64).reshape(3, 3)
    t = np.asarray(t, dtype=np.float64).ravel()
    src_ideal = np.asarray(src_ideal, dtype=np.float64).reshape(-1, 3)
    dst_consensus = np.asarray(dst_consensus, dtype=np.float64).reshape(-1, 3)

    aligned = (R @ src_ideal.T).T + t          # (N,3) ideal mapped into world
    residuals = dst_consensus - aligned        # (N,3) world-frame residual vectors

    normal = R[:, 2]
    nrm = np.linalg.norm(normal)
    normal = normal / nrm if nrm > 1e-12 else np.array([0.0, 0.0, 1.0])
    return residuals, normal


def decompose_board_frame(
    residuals: np.ndarray,
    normal: np.ndarray,
) -> Dict[str, float]:
    """
    Split residual vectors into out-of-board-plane (along `normal`) and in-plane
    (perpendicular to `normal`) components, and report RMS magnitudes in mm.

    Returns
    -------
    dict with out_of_plane_rms_mm, in_plane_rms_mm, total_rms_mm, n, and the
    per-corner component arrays (mm).
    """
    residuals = np.asarray(residuals, dtype=np.float64).reshape(-1, 3)
    normal = np.asarray(normal, dtype=np.float64).ravel()
    n = len(residuals)
    if n == 0:
        return {
            "out_of_plane_rms_mm": float("nan"),
            "in_plane_rms_mm": float("nan"),
            "total_rms_mm": float("nan"),
            "n": 0,
            "out_of_plane_mm": np.zeros(0),
            "in_plane_mm": np.zeros(0),
        }

    oop_signed = residuals @ normal                     # (N,) signed along normal
    in_plane_vec = residuals - np.outer(oop_signed, normal)
    in_plane_mag = np.linalg.norm(in_plane_vec, axis=1)

    oop_mm = np.abs(oop_signed) * 1000.0
    ip_mm = in_plane_mag * 1000.0
    return {
        "out_of_plane_rms_mm": float(np.sqrt(np.mean(oop_mm ** 2))),
        "in_plane_rms_mm": float(np.sqrt(np.mean(ip_mm ** 2))),
        "total_rms_mm": float(np.sqrt(np.mean(np.sum(residuals ** 2, axis=1))) * 1000.0),
        "n": int(n),
        "out_of_plane_mm": oop_mm,
        "in_plane_mm": ip_mm,
    }


def decompose_range_lateral(
    residuals: np.ndarray,
    ray_dirs: np.ndarray,
) -> Dict[str, float]:
    """
    Split residual vectors into RANGE (component along each ray) and LATERAL
    (perpendicular) components, and report RMS magnitudes in mm.

    Parameters
    ----------
    residuals : (N,3) residual vectors in world metres (per-camera corner minus
                cross-camera consensus).
    ray_dirs  : (N,3) viewing-ray directions (need not be unit; normalised here).

    Returns
    -------
    dict with range_rms_mm, lateral_rms_mm, total_rms_mm, range_dominance
    (= range_rms / lateral_rms), n, and per-observation component arrays (mm).
    """
    residuals = np.asarray(residuals, dtype=np.float64).reshape(-1, 3)
    ray_dirs = np.asarray(ray_dirs, dtype=np.float64).reshape(-1, 3)
    n = len(residuals)
    if n == 0:
        return {
            "range_rms_mm": float("nan"),
            "lateral_rms_mm": float("nan"),
            "total_rms_mm": float("nan"),
            "range_dominance": float("nan"),
            "n": 0,
            "range_mm": np.zeros(0),
            "lateral_mm": np.zeros(0),
        }

    norms = np.linalg.norm(ray_dirs, axis=1, keepdims=True)
    norms = np.where(norms > 1e-12, norms, 1.0)
    units = ray_dirs / norms

    range_signed = np.sum(residuals * units, axis=1)         # (N,) along ray
    lateral_vec = residuals - units * range_signed[:, None]
    lateral_mag = np.linalg.norm(lateral_vec, axis=1)

    range_mm = np.abs(range_signed) * 1000.0
    lateral_mm = lateral_mag * 1000.0
    range_rms = float(np.sqrt(np.mean(range_mm ** 2)))
    lateral_rms = float(np.sqrt(np.mean(lateral_mm ** 2)))
    return {
        "range_rms_mm": range_rms,
        "lateral_rms_mm": lateral_rms,
        "total_rms_mm": float(np.sqrt(np.mean(np.sum(residuals ** 2, axis=1))) * 1000.0),
        "range_dominance": float(range_rms / lateral_rms) if lateral_rms > 1e-9 else float("inf"),
        "n": int(n),
        "range_mm": range_mm,
        "lateral_mm": lateral_mm,
    }
