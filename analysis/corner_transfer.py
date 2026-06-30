"""
AquaMVS Analysis — Corner Transfer
====================================
Per-(frame, camera) transfer of detected 2-D ChArUco corners to 3-D world
points, using the MVS depth maps + refractive back-projection, with a
fused-cloud-slab plane-fit fallback for corners whose depth is missing or weak.

Transfer order (§3.2 then §3.3):
  1. Direct:    bilinearly sample depth + confidence; back-project valid corners
                via model.cast_ray (replicating the fusion path exactly).
  2. Fallback:  corners with missing/weak depth -> intersect their back-projected
                ray with the board plane fit from a thin-slab crop of the fused
                dense cloud around the ChArUco->PnP board pose (PRIMARY source).

Key exports
-----------
CornerRecord          - dataclass holding one transferred corner.
DEFAULT_MIN_CONFIDENCE - 0.1, matching aquamvs config default.
fit_board_plane       - SVD plane fit from a (M,3) point cloud.
intersect_ray_plane   - standard ray-plane intersection.
board_pose_seed       - coarse ChArUco->PnP seed for the slab centre/normal.
crop_cloud_to_slab    - thin-slab crop of the fused point cloud.
transfer_frame_camera - full per-(frame,camera) transfer.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Allow running from the repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np
import open3d as o3d
import torch

from analysis.projection import sample_map_bilinear, back_project

logger = logging.getLogger(__name__)


# ── Constants ──────────────────────────────────────────────────────────────────

DEFAULT_MIN_CONFIDENCE: float = 0.1    # matches aquamvs config default (fusion.py:114)
DEFAULT_SLAB_THICKNESS: float = 0.012  # 12 mm thin slab around board for plane fit


# ── Corner record ──────────────────────────────────────────────────────────────

@dataclass
class CornerRecord:
    """One transferred ChArUco corner in the MVS world frame."""
    frame_idx: int                         # output frame index
    camera_id: str                         # camera name
    corner_id: int                         # ChArUco corner id (0-87)
    point_3d: tuple[float, float, float]   # (X, Y, Z) in MVS world frame
    method: str                            # "direct" or "plane_fit"
    confidence: float                      # bilinearly-sampled depth confidence; NaN if unavailable
    pixel: tuple[float, float]             # source 2-D pixel (u, v) on undistorted image


# ── Plane geometry ─────────────────────────────────────────────────────────────

def fit_board_plane(
    points3d: np.ndarray,
) -> Optional[tuple[np.ndarray, np.ndarray]]:
    """
    Fit a plane to (M, 3) 3-D points via SVD (total-least-squares).

    Returns
    -------
    (point_on_plane, unit_normal) if M >= 3, else None.
    The unit normal corresponds to the smallest singular value (thickness direction).
    """
    points3d = np.asarray(points3d, dtype=np.float64)
    if points3d.shape[0] < 3:
        return None
    centroid = points3d.mean(axis=0)
    centred = points3d - centroid
    _, _, Vt = np.linalg.svd(centred, full_matrices=False)
    normal = Vt[-1]  # smallest singular vector = plane normal
    norm = np.linalg.norm(normal)
    if norm < 1e-12:
        return None
    normal = normal / norm
    return centroid.copy(), normal.copy()


def intersect_ray_plane(
    origin: np.ndarray,
    direction: np.ndarray,
    plane_point: np.ndarray,
    plane_normal: np.ndarray,
) -> Optional[np.ndarray]:
    """
    Standard ray-plane intersection.

    Returns
    -------
    The 3-D intersection point (float64), or None if the ray is nearly parallel
    to the plane (|dot(direction, normal)| < 1e-9) OR the intersection lies
    behind the ray origin (t <= 0, i.e. behind the camera / interface). A
    non-physical (behind-camera) intersection is rejected here so a degenerate
    seed plane cannot emit garbage corners (e.g. negative-depth points).
    """
    origin = np.asarray(origin, dtype=np.float64)
    direction = np.asarray(direction, dtype=np.float64)
    plane_point = np.asarray(plane_point, dtype=np.float64)
    plane_normal = np.asarray(plane_normal, dtype=np.float64)

    denom = float(np.dot(direction, plane_normal))
    if abs(denom) < 1e-9:
        return None
    t = float(np.dot(plane_point - origin, plane_normal)) / denom
    if t <= 0.0:
        # Intersection behind the camera along the ray — non-physical.
        return None
    return origin + t * direction


# ── Board-pose seed ────────────────────────────────────────────────────────────

def board_pose_seed(
    detection,
    model,
    board,
    calib,
    camera: str,
    direct_pts: Optional[np.ndarray] = None,
) -> Optional[tuple[np.ndarray, np.ndarray]]:
    """
    Produce a COARSE seed plane (point_world, normal_world) used ONLY to
    locate the board in the fused cloud for slab cropping.

    Strategy (preferred -> fallback):
    1. ChArUco->PnP: solve board pose (board-local -> camera -> world).
       Requires >= 4 detected corners. PnP through the refractive interface is
       approximate but sufficient for a crop seed.
    2. Direct-corner SVD: if PnP fails or < 4 corners, fit the plane from
       direct_pts (already in world frame), if >= 3 points are available.
    3. None: neither strategy yields a result.

    Parameters
    ----------
    detection:  aquacal Detection (.corner_ids int32 (N,), .corners_2d float64 (N,2) (u,v)).
    model:      RefractiveProjectionModel for this camera.
    board:      BoardGeometry (aquacal).
    calib:      CalibrationData.
    camera:     Camera name string.
    direct_pts: (M, 3) float64 world-frame points from direct depth transfer
                (used as SVD fallback seed).

    Returns
    -------
    (point_world, unit_normal_world) or None.
    """
    from aquamvs.calibration import compute_undistortion_maps

    cam = calib.cameras[camera]
    K_new = compute_undistortion_maps(cam).K_new

    # Convert K_new to (3,3) float64 numpy array regardless of torch/numpy origin
    K_np = K_new.detach().cpu().numpy() if hasattr(K_new, "detach") else np.asarray(K_new)
    K_np = K_np.astype(np.float64).reshape(3, 3)

    # cam.R and cam.t: rotation/translation FROM world TO camera
    #   X_cam = R @ X_world + t  =>  X_world = R.T @ (X_cam - t)
    R_cam = cam.R.detach().cpu().numpy() if hasattr(cam.R, "detach") else np.asarray(cam.R)
    t_cam = cam.t.detach().cpu().numpy() if hasattr(cam.t, "detach") else np.asarray(cam.t)
    R_cam = R_cam.astype(np.float64).reshape(3, 3)
    t_cam = t_cam.astype(np.float64).ravel()

    ids = np.asarray(detection.corner_ids, dtype=np.int32)           # (N,)
    corners_2d = np.asarray(detection.corners_2d, dtype=np.float64)  # (N,2) (u,v)

    # ── Strategy 1: ChArUco->PnP ──────────────────────────────────────────────
    if len(ids) >= 4:
        # board.get_opencv_board().getChessboardCorners() returns (88,3) float32
        # in board-local metres; index by corner_ids to get matched 3D points.
        obj_all = board.get_opencv_board().getChessboardCorners()
        obj_pts = obj_all[ids].astype(np.float64)  # (N,3) board-local metres

        ok, rvec, tvec = cv2.solvePnP(
            obj_pts, corners_2d, K_np, None,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if ok:
            R_board_cam, _ = cv2.Rodrigues(rvec)     # (3,3) board->camera rotation
            t_board_cam = tvec.ravel()                # (3,) board origin in camera frame

            # Board z=0 plane: origin=(0,0,0) board-local, normal=(0,0,1) board-local
            origin_cam = t_board_cam                                           # (3,)
            normal_cam = (R_board_cam @ np.array([0.0, 0.0, 1.0])).ravel()   # (3,)

            # Camera frame -> world frame:  X_world = R_cam.T @ (X_cam - t_cam)
            origin_world = R_cam.T @ (origin_cam - t_cam)
            normal_world = R_cam.T @ normal_cam
            norm = np.linalg.norm(normal_world)
            if norm > 1e-12:
                normal_world /= norm
                logger.debug(
                    "board_pose_seed [%s]: PnP OK; origin_world=[%.3f, %.3f, %.3f]",
                    camera, *origin_world,
                )
                return origin_world, normal_world

    # ── Strategy 2: SVD on direct world-frame points ──────────────────────────
    if direct_pts is not None and len(direct_pts) >= 3:
        result = fit_board_plane(np.asarray(direct_pts, dtype=np.float64))
        if result is not None:
            logger.debug(
                "board_pose_seed [%s]: using direct-corner SVD fallback (%d pts)",
                camera, len(direct_pts),
            )
            return result

    logger.debug("board_pose_seed [%s]: no seed available (N=%d corners)", camera, len(ids))
    return None


# ── Slab cropping ──────────────────────────────────────────────────────────────

def crop_cloud_to_slab(
    cloud_xyz: np.ndarray,
    plane_point: np.ndarray,
    plane_normal: np.ndarray,
    thickness: float,
) -> np.ndarray:
    """
    Crop the fused point cloud to a thin slab around the seed plane.

    Parameters
    ----------
    cloud_xyz:    (M, 3) world-frame fused point cloud.
    plane_point:  A point on the seed plane.
    plane_normal: Unit normal of the seed plane.
    thickness:    Total slab thickness in metres (half = thickness/2 per side).

    Returns
    -------
    (K, 3) float64 array of cloud points within |signed_dist| <= thickness/2.
    """
    cloud_xyz = np.asarray(cloud_xyz, dtype=np.float64)
    plane_point = np.asarray(plane_point, dtype=np.float64)
    plane_normal = np.asarray(plane_normal, dtype=np.float64)
    norm = np.linalg.norm(plane_normal)
    if norm < 1e-12:
        return cloud_xyz[:0]  # empty
    plane_normal = plane_normal / norm

    signed_dist = (cloud_xyz - plane_point) @ plane_normal
    mask = np.abs(signed_dist) <= (thickness / 2.0)
    return cloud_xyz[mask]


# ── Per-(frame, camera) transfer ───────────────────────────────────────────────

def transfer_frame_camera(
    ds,
    model,
    frame,
    camera: str,
    detection,
    board,
    calib,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    fused_cloud_points: Optional[np.ndarray] = None,
    slab_thickness: float = DEFAULT_SLAB_THICKNESS,
) -> tuple[list[CornerRecord], dict]:
    """
    Transfer all detected ChArUco corners for one (frame, camera) pair to
    3-D MVS-world points.

    Order: direct depth first (§3.2), then fused-cloud-slab plane-fit fallback
    for any dropped corners (§3.3).

    Parameters
    ----------
    ds:                 GroundTruthDataset.
    model:              RefractiveProjectionModel for this camera (CPU).
    frame:              FrameInfo.
    camera:             Camera name string.
    detection:          aquacal Detection (.corner_ids, .corners_2d).
    board:              BoardGeometry.
    calib:              CalibrationData.
    min_confidence:     Minimum depth-confidence threshold (default 0.1).
    fused_cloud_points: (M, 3) float64 fused cloud for this frame, pre-loaded
                        by the caller (loaded at most ONCE per frame). If None,
                        loaded lazily here from ds.fused_cloud_path(frame).
    slab_thickness:     Thin-slab crop total thickness in metres (default 12 mm).

    Returns
    -------
    (records, counts) where counts = {
        n_detected, n_direct, n_plane_fit, n_unrecovered
    }.
    """
    pixels = np.asarray(detection.corners_2d, dtype=np.float32)   # (N,2) (u,v)
    ids = np.asarray(detection.corner_ids, dtype=np.int32)         # (N,)
    N = len(ids)

    # ── 1. Load depth + confidence from .npz ──────────────────────────────────
    depth_path = ds.depth_map_path(frame, camera)
    if depth_path is None:
        logger.warning(
            "transfer_frame_camera: no depth map for camera=%s frame=%d",
            camera, frame.output_idx,
        )
        return [], {"n_detected": N, "n_direct": 0, "n_plane_fit": 0, "n_unrecovered": N}

    npz = np.load(str(depth_path))
    depth_map = npz["depth"]       # (1200, 1600) float32
    conf_map  = npz["confidence"]  # (1200, 1600) float32

    # ── 2. Bilinear-sample depth + confidence at corner pixels ────────────────
    d = sample_map_bilinear(depth_map, pixels)   # (N,)
    c = sample_map_bilinear(conf_map, pixels)    # (N,)

    # ── 3. Direct validity gate (matches fusion.py:114) ───────────────────────
    valid_direct = (
        np.isfinite(d) & (d > 0) &
        np.isfinite(c) & (c >= min_confidence)
    )
    invalid_mask = ~valid_direct

    # ── 4. Back-project valid (direct) corners ────────────────────────────────
    records: list[CornerRecord] = []
    direct_world_pts: list[np.ndarray] = []

    if valid_direct.any():
        valid_idx = np.where(valid_direct)[0]
        pts_direct = back_project(
            model, pixels[valid_direct], d[valid_direct]
        ).astype(np.float64)  # (K,3)

        for k, idx in enumerate(valid_idx):
            pt = tuple(float(x) for x in pts_direct[k])
            records.append(CornerRecord(
                frame_idx=int(frame.output_idx),
                camera_id=camera,
                corner_id=int(ids[idx]),
                point_3d=pt,
                method="direct",
                confidence=float(c[idx]),
                pixel=(float(pixels[idx, 0]), float(pixels[idx, 1])),
            ))
            direct_world_pts.append(pts_direct[k])

    n_direct = int(valid_direct.sum())
    n_invalid = int(invalid_mask.sum())

    # ── 5. Plane-fit fallback (only when at least one corner is invalid) ──────
    n_plane_fit = 0
    n_unrecovered = 0

    if n_invalid > 0:
        direct_pts_arr = (
            np.array(direct_world_pts, dtype=np.float64)
            if direct_world_pts else None
        )

        # --- Coarse seed plane (board pose; only for locating the slab) ---
        seed = board_pose_seed(
            detection, model, board, calib, camera, direct_pts=direct_pts_arr
        )

        # --- Obtain fused cloud (lazy load if not supplied by caller) ---
        cloud_xyz: Optional[np.ndarray] = fused_cloud_points
        if cloud_xyz is None:
            cloud_path = ds.fused_cloud_path(frame)
            if cloud_path.exists():
                logger.info(
                    "transfer_frame_camera: lazily loading fused cloud %s", cloud_path
                )
                cloud_xyz = np.asarray(
                    o3d.io.read_point_cloud(str(cloud_path)).points,
                    dtype=np.float64,
                )
                logger.info(
                    "Loaded fused cloud: %d points (frame %d)",
                    len(cloud_xyz), frame.output_idx,
                )
            else:
                logger.warning(
                    "transfer_frame_camera: fused cloud not found at %s", cloud_path
                )

        # --- PRIMARY: fit plane from fused-cloud thin-slab ---
        plane: Optional[tuple[np.ndarray, np.ndarray]] = None

        if seed is not None and cloud_xyz is not None and len(cloud_xyz) > 0:
            slab = crop_cloud_to_slab(cloud_xyz, seed[0], seed[1], slab_thickness)
            logger.debug(
                "transfer_frame_camera [%s frame=%d]: slab_pts=%d",
                camera, frame.output_idx, len(slab),
            )
            if len(slab) >= 3:
                plane = fit_board_plane(slab)
                if plane is not None:
                    logger.debug(
                        "transfer_frame_camera [%s frame=%d]: plane fit from %d slab pts",
                        camera, frame.output_idx, len(slab),
                    )

        # --- DEGRADED fallback: SVD on direct corners ---
        if plane is None:
            if direct_pts_arr is not None and len(direct_pts_arr) >= 3:
                logger.debug(
                    "transfer_frame_camera [%s frame=%d]: degraded fallback -> direct SVD",
                    camera, frame.output_idx,
                )
                plane = fit_board_plane(direct_pts_arr)

        # --- Physical depth band: plane-fit points must land in a plausible
        #     world-Z range. Prefer this camera's own direct corners (tight,
        #     pose-specific); else a generous absolute band for the rig volume.
        #     This rejects non-physical solutions (e.g. behind-interface Z<0)
        #     from a degenerate seed plane. ---
        if direct_world_pts:
            direct_z = np.array([p[2] for p in direct_world_pts], dtype=np.float64)
            z_lo = float(direct_z.min()) - 0.10   # 10 cm margin around observed board
            z_hi = float(direct_z.max()) + 0.10
        else:
            z_lo, z_hi = 0.10, 3.0                # generous physical band (metres)

        # --- Back-project rays for all invalid corners; intersect with plane ---
        invalid_idx = np.where(invalid_mask)[0]
        if len(invalid_idx) > 0:
            # Batch ray cast for all invalid corners at once
            pix_invalid = torch.tensor(pixels[invalid_idx], dtype=torch.float32)
            with torch.no_grad():
                origins_t, directions_t = model.cast_ray(pix_invalid)
            origins_np = origins_t.detach().cpu().numpy().astype(np.float64)      # (K,3)
            directions_np = directions_t.detach().cpu().numpy().astype(np.float64) # (K,3)

            for k, idx in enumerate(invalid_idx):
                if plane is None:
                    n_unrecovered += 1
                    continue

                pt3d = intersect_ray_plane(
                    origins_np[k], directions_np[k], plane[0], plane[1]
                )
                if pt3d is None:
                    n_unrecovered += 1
                    continue

                # Physical-validity gate: reject non-physical plane-fit points
                # (outside the plausible board-depth band — e.g. behind the
                # water interface). These come from degenerate seed planes and
                # would otherwise inject ~metre-scale blunders into the metrics.
                if not (z_lo <= float(pt3d[2]) <= z_hi):
                    logger.debug(
                        "transfer_frame_camera [%s frame=%d]: rejected non-physical "
                        "plane_fit corner id=%d Z=%.3f (band [%.2f, %.2f])",
                        camera, frame.output_idx, int(ids[idx]), float(pt3d[2]), z_lo, z_hi,
                    )
                    n_unrecovered += 1
                    continue

                conf_val = float(c[idx]) if np.isfinite(c[idx]) else float("nan")
                records.append(CornerRecord(
                    frame_idx=int(frame.output_idx),
                    camera_id=camera,
                    corner_id=int(ids[idx]),
                    point_3d=tuple(float(x) for x in pt3d),
                    method="plane_fit",
                    confidence=conf_val,
                    pixel=(float(pixels[idx, 0]), float(pixels[idx, 1])),
                ))
                n_plane_fit += 1

    counts = {
        "n_detected": N,
        "n_direct": n_direct,
        "n_plane_fit": n_plane_fit,
        "n_unrecovered": n_unrecovered,
    }
    logger.debug(
        "transfer_frame_camera [%s frame=%d]: %s", camera, frame.output_idx, counts
    )
    return records, counts
