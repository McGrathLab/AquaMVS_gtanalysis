"""
AquaMVS Cross-Camera Board-Localization Agreement (MET-03)
==========================================================
Pure-numeric, dataset-free functions for computing cross-camera dispersion
of independently transferred ChArUco corners.

ORDERING INVARIANT: All computations are performed in the RAW MVS reconstruction
frame, BEFORE any rigid alignment, scale calibration, Umeyama, or ICP step
(Phase 4). Output distances are in millimetres (input points are in metres).

Functions
---------
load_corners          -- Load corners.npz into a dict of arrays.
per_camera_coverage   -- Count corners contributed per camera for a frame.
included_cameras      -- Apply a coverage threshold to select reliable cameras.
per_corner_dispersion -- RMS dispersion (mm) of per-camera 3-D placements.
frame_agreement       -- Per-frame agreement aggregated over co-observed corners.
"""

from __future__ import annotations

from typing import Any, Dict, Set, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Corner loading
# ---------------------------------------------------------------------------

def load_corners(npz_path: str) -> Dict[str, np.ndarray]:
    """
    Load corners.npz produced by Phase 2 corner transfer.

    Uses allow_pickle=True because camera_id and method are stored as object
    arrays.  camera_id is cast to plain str for reliable dict keying.

    Parameters
    ----------
    npz_path : str | Path
        Path to corners.npz.

    Returns
    -------
    dict with keys:
        frame_idx  : (N,) int32
        camera_id  : (N,) object (str)
        corner_id  : (N,) int32
        points     : (N, 3) float32 — MVS world frame, metres
        method     : (N,) object (str)
        confidence : (N,) float32
        pixels     : (N, 2) float32
    """
    npz = np.load(str(npz_path), allow_pickle=True)
    camera_id = np.array([str(c) for c in npz["camera_id"]], dtype=object)
    method = np.array([str(m) for m in npz["method"]], dtype=object)
    return {
        "frame_idx":  npz["frame_idx"].astype(np.int32),
        "camera_id":  camera_id,
        "corner_id":  npz["corner_id"].astype(np.int32),
        "points":     npz["points"].astype(np.float32),
        "method":     method,
        "confidence": npz["confidence"].astype(np.float32),
        "pixels":     npz["pixels"].astype(np.float32),
    }


# ---------------------------------------------------------------------------
# Coverage filtering
# ---------------------------------------------------------------------------

def per_camera_coverage(
    frame_idx_arr: np.ndarray,
    camera_id_arr: np.ndarray,
    frame: int,
) -> Dict[str, int]:
    """
    Count corners contributed by each camera in a given frame.

    Board-blind cameras (0 observations for this frame) do not appear in the
    return value; they are never treated as errors.

    Parameters
    ----------
    frame_idx_arr : (N,) int32
    camera_id_arr : (N,) str / object
    frame         : int — output_idx of the frame

    Returns
    -------
    dict[camera_id -> corner_count]
    """
    mask = frame_idx_arr == frame
    cams = camera_id_arr[mask]
    coverage: Dict[str, int] = {}
    for cam in cams:
        cam_str = str(cam)
        coverage[cam_str] = coverage.get(cam_str, 0) + 1
    return coverage


def included_cameras(
    coverage: Dict[str, int],
    min_corners: int,
) -> Tuple[Set[str], Dict[str, int]]:
    """
    Apply a coverage threshold to select cameras with sufficient observations.

    Cameras with corner count >= min_corners are included.
    Cameras below the threshold are excluded and recorded with their counts.
    Board-blind cameras (0 corners) simply do not appear in `coverage` and are
    therefore never included, excluded, or counted as errors.

    Parameters
    ----------
    coverage    : dict[camera_id -> corner_count] from per_camera_coverage
    min_corners : int — minimum corners required to include a camera

    Returns
    -------
    included : set[str] — camera ids that meet the threshold
    excluded : dict[str, int] — camera ids that do not, with their counts
    """
    included: Set[str] = set()
    excluded: Dict[str, int] = {}
    for cam, count in coverage.items():
        if count >= min_corners:
            included.add(cam)
        else:
            excluded[cam] = count
    return included, excluded


# ---------------------------------------------------------------------------
# Dispersion computation
# ---------------------------------------------------------------------------

def per_corner_dispersion(
    points_by_camera: Dict[str, np.ndarray],
) -> Dict[str, Any]:
    """
    Compute cross-camera 3-D dispersion for ONE (frame_idx, corner_id).

    Given the independent 3-D placements from each co-observing camera, computes:
      - centroid = mean of per-camera points
      - rms_mm   = sqrt(mean(||p_i - centroid||^2)) * 1000  [mm]
      - max_pairwise_mm = max Euclidean distance between any two camera points [mm]

    ORDERING INVARIANT: points are in the raw MVS world frame, no alignment applied.

    Parameters
    ----------
    points_by_camera : dict[camera_id -> (3,) array in metres]
        Must have at least 2 entries.

    Returns
    -------
    dict with keys:
        rms_mm          : float — RMS distance to centroid (mm)
        n_cameras       : int   — number of cameras
        max_pairwise_mm : float — max pairwise Euclidean distance (mm)
    """
    pts = np.array(list(points_by_camera.values()), dtype=np.float64)  # (K, 3)
    centroid = pts.mean(axis=0)                                          # (3,)
    sq_dists = np.sum((pts - centroid) ** 2, axis=1)                    # (K,)
    rms_mm = float(np.sqrt(np.mean(sq_dists)) * 1000.0)

    # Max pairwise distance
    n = len(pts)
    max_pw = 0.0
    for i in range(n):
        for j in range(i + 1, n):
            d = float(np.linalg.norm(pts[i] - pts[j]) * 1000.0)
            if d > max_pw:
                max_pw = d

    return {
        "rms_mm": rms_mm,
        "n_cameras": n,
        "max_pairwise_mm": max_pw,
    }


# ---------------------------------------------------------------------------
# Per-frame aggregation
# ---------------------------------------------------------------------------

def frame_agreement(
    corners_for_frame: Dict[str, np.ndarray],
    included_cams: Set[str],
    min_cameras: int = 2,
) -> Dict[str, Any]:
    """
    Compute per-frame cross-camera board-localization agreement (MET-03).

    Algorithm
    ---------
    1. Restrict all rows to included cameras only.
    2. Group by corner_id.
    3. Keep only corner_ids co-observed by >= min_cameras INCLUDED cameras.
    4. Compute per_corner_dispersion for each kept corner.
    5. Aggregate: frame_rms_mm = sqrt(mean(per_corner rms_mm**2)).

    A corner seen by fewer than min_cameras included cameras is silently skipped
    (not an error). Board-blind cameras never appear and contribute nothing.

    ORDERING INVARIANT: computed in RAW MVS frame, BEFORE any alignment/scaling.

    Parameters
    ----------
    corners_for_frame : dict with keys:
        camera_id : (M,) str/object
        corner_id : (M,) int32
        points    : (M, 3) float32 (metres, MVS world frame)
    included_cams : set[str] — cameras that passed the coverage threshold
    min_cameras   : int — minimum included cameras for a corner to be compared

    Returns
    -------
    dict with keys:
        frame_rms_mm         : float or NaN
        n_corners_compared   : int
        n_cameras_included   : int
        mean_per_corner_mm   : float or NaN
        median_per_corner_mm : float or NaN
        per_corner_rms_mm    : list[float]
    """
    cam_arr = np.array([str(c) for c in corners_for_frame["camera_id"]])
    cid_arr = corners_for_frame["corner_id"]
    pts_arr = corners_for_frame["points"]

    # Restrict to included cameras
    mask = np.array([c in included_cams for c in cam_arr])
    cam_arr = cam_arr[mask]
    cid_arr = cid_arr[mask]
    pts_arr = pts_arr[mask]

    # Group by corner_id, keep co-observed ones
    unique_corners = np.unique(cid_arr)
    per_corner_results: list[float] = []
    for cid in unique_corners:
        cm = cid_arr == cid
        cams_here = cam_arr[cm]
        pts_here = pts_arr[cm]
        if len(cams_here) < min_cameras:
            continue  # only one included camera sees this corner — not an error
        pts_by_cam = {
            str(cams_here[i]): pts_here[i].astype(np.float64)
            for i in range(len(cams_here))
        }
        disp = per_corner_dispersion(pts_by_cam)
        per_corner_results.append(disp["rms_mm"])

    n_corners = len(per_corner_results)
    n_included = len(included_cams)

    if n_corners == 0:
        return {
            "frame_rms_mm":          float("nan"),
            "n_corners_compared":    0,
            "n_cameras_included":    n_included,
            "mean_per_corner_mm":    float("nan"),
            "median_per_corner_mm":  float("nan"),
            "per_corner_rms_mm":     [],
        }

    arr = np.array(per_corner_results)
    return {
        "frame_rms_mm":          float(np.sqrt(np.mean(arr ** 2))),
        "n_corners_compared":    n_corners,
        "n_cameras_included":    n_included,
        "mean_per_corner_mm":    float(np.mean(arr)),
        "median_per_corner_mm":  float(np.median(arr)),
        "per_corner_rms_mm":     [float(v) for v in arr],
    }
