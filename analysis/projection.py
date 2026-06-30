"""
AquaMVS Analysis — Projection Primitives
==========================================
Replicates the aquamvs fusion back-projection path exactly:

    origins, directions = model.cast_ray(pixels)
    points_3d = origins + depths.unsqueeze(-1) * directions

Source reference: aquamvs/fusion.py lines 133-134, 289-290;
                  aquamvs/pipeline/builder.py lines 76-90.

Key functions
-------------
build_projection_models(calib, cameras) -> dict[str, RefractiveProjectionModel]
    Build one refractive projection model per depth-bearing camera using K_new
    (post-undistortion intrinsics), mirroring aquamvs/pipeline/builder.py.

sample_map_bilinear(map2d, pixels_uv) -> np.ndarray
    Bilinearly sample a (H, W) float32 depth/confidence map at (N, 2) pixel
    coordinates, returning NaN for out-of-bounds or NaN-contaminated regions.

back_project(model, pixels_uv, depths) -> np.ndarray
    Back-project (N, 2) pixel coordinates + (N,) depths to (N, 3) world-frame
    3-D points via RefractiveProjectionModel.cast_ray.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Allow running from the repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import torch
import torch.nn.functional as F

from aquamvs.calibration import compute_undistortion_maps
from aquamvs.projection.refractive import RefractiveProjectionModel

if TYPE_CHECKING:
    from aquamvs.calibration import CalibrationData

logger = logging.getLogger(__name__)


# ── Model construction ─────────────────────────────────────────────────────────

def build_projection_models(
    calib: "CalibrationData",
    cameras: list[str],
) -> dict[str, RefractiveProjectionModel]:
    """
    Build one RefractiveProjectionModel per camera, replicating
    aquamvs/pipeline/builder.py lines 76-90.

    Parameters
    ----------
    calib:    CalibrationData (from ds.calibration()).
    cameras:  List of camera name strings (depth-bearing cameras only).

    Returns
    -------
    dict mapping camera name -> RefractiveProjectionModel (CPU, eval mode).

    Notes
    -----
    Uses K_new (post-undistortion intrinsics), NOT cam.K — because detected
    corners and depth maps both live on the undistorted pixel grid, exactly as
    in the aquamvs fusion pipeline.
    """
    models: dict[str, RefractiveProjectionModel] = {}
    for name in cameras:
        cam = calib.cameras[name]
        # compute_undistortion_maps returns an object whose .K_new attribute
        # is the post-undistortion intrinsic matrix.
        K_new = compute_undistortion_maps(cam).K_new
        model = RefractiveProjectionModel(
            K=K_new,
            R=cam.R,
            t=cam.t,
            water_z=calib.water_z,
            normal=calib.interface_normal,
            n_air=calib.n_air,
            n_water=calib.n_water,
        ).to("cpu")
        models[name] = model
        logger.debug("Built projection model for camera %s", name)

    logger.debug("build_projection_models: %d models built", len(models))
    return models


# ── Bilinear sampling ──────────────────────────────────────────────────────────

def sample_map_bilinear(
    map2d: np.ndarray,
    pixels_uv: np.ndarray,
) -> np.ndarray:
    """
    Bilinearly sample a (H, W) float32 map at float (N, 2) pixel coordinates,
    replicating the aquamvs fusion depth-sampling approach (fusion.py:14).

    NaN propagation rules (conservative):
    - Pixels outside [0, W-1] x [0, H-1] -> NaN.
    - Any bilinear neighbour that was NaN in the source -> NaN (detected via a
      separate NaN-mask sampled with padding_mode="border" so border bleed is
      captured; threshold > 0.01).

    Parameters
    ----------
    map2d:     (H, W) float32 numpy array (depth or confidence map).
    pixels_uv: (N, 2) float array of pixel coordinates; column (u) first, row (v) second.

    Returns
    -------
    (N,) float32 numpy array; NaN at invalid / out-of-bounds positions.
    """
    map2d = np.asarray(map2d, dtype=np.float32)
    pixels_uv = np.asarray(pixels_uv, dtype=np.float32)
    H, W = map2d.shape
    N = pixels_uv.shape[0]

    if N == 0:
        return np.empty(0, dtype=np.float32)

    u = pixels_uv[:, 0]  # column
    v = pixels_uv[:, 1]  # row

    # Out-of-bounds mask — computed in numpy before converting to torch
    oob = (u < 0) | (u > W - 1) | (v < 0) | (v > H - 1)

    # Normalise pixel coords to [-1, 1] as aquamvs fusion does:
    #   gx = 2*u/(W-1) - 1,  gy = 2*v/(H-1) - 1
    gx = torch.tensor(2.0 * u / (W - 1) - 1.0, dtype=torch.float32)
    gy = torch.tensor(2.0 * v / (H - 1) - 1.0, dtype=torch.float32)
    # F.grid_sample expects grid shape (N_batch, H_out, W_out, 2)
    grid = torch.stack([gx, gy], dim=-1).view(1, N, 1, 2)

    # NaN mask: 1.0 where the source map is NaN, 0.0 elsewhere
    nan_mask_np = np.isnan(map2d).astype(np.float32)        # (H, W)

    # Replace NaN with 0.0 for value sampling
    map_no_nan = np.where(nan_mask_np.astype(bool), 0.0, map2d).astype(np.float32)

    map_t = torch.as_tensor(map_no_nan).view(1, 1, H, W)    # (1, 1, H, W)
    nan_t = torch.as_tensor(nan_mask_np).view(1, 1, H, W)   # (1, 1, H, W)

    # Sample the value map — out-of-bounds pads with zeros
    sampled = F.grid_sample(
        map_t, grid, mode="bilinear", padding_mode="zeros", align_corners=True
    )  # (1, 1, N, 1)
    sampled_np = sampled.view(N).numpy()

    # Sample the NaN mask with border padding to detect nearby NaN contamination
    nan_sampled = F.grid_sample(
        nan_t, grid, mode="bilinear", padding_mode="border", align_corners=True
    )  # (1, 1, N, 1)
    nan_sampled_np = nan_sampled.view(N).numpy()

    # Compose result: mark as NaN where a NaN neighbour bled in, or out-of-bounds
    result = sampled_np.astype(np.float32)
    result[nan_sampled_np > 0.01] = np.nan
    result[oob] = np.nan

    return result


# ── Back-projection ────────────────────────────────────────────────────────────

def back_project(
    model: RefractiveProjectionModel,
    pixels_uv: np.ndarray,
    depths: np.ndarray,
) -> np.ndarray:
    """
    Back-project (N, 2) pixel coordinates and (N,) depths to (N, 3) world-frame
    3-D points, exactly replicating the aquamvs fusion construction:

        origins, directions = model.cast_ray(pixels)   # pixels: torch (N,2) (u,v)
        points_3d = origins + depths.unsqueeze(-1) * directions

    Parameters
    ----------
    model:     RefractiveProjectionModel (CPU, built with K_new via build_projection_models).
    pixels_uv: (N, 2) float array of pixel coordinates, column (u) first.
    depths:    (N,) float array of depths (positive and finite for valid corners).

    Returns
    -------
    (N, 3) float32 numpy array of 3-D points in the MVS world frame.
    """
    pixels = torch.as_tensor(pixels_uv, dtype=torch.float32)  # (N, 2)
    depths_t = torch.as_tensor(depths, dtype=torch.float32).unsqueeze(-1)  # (N, 1)

    with torch.no_grad():
        origins, directions = model.cast_ray(pixels)   # each (N, 3)

    pts = origins + depths_t * directions              # (N, 3)
    return pts.detach().cpu().numpy().astype(np.float32)
