---
phase: 02-corner-transfer
plan: "02"
subsystem: analysis
tags: [corner-transfer, depth-backprojection, refractive-model, plane-fit, fused-cloud, open3d, charuco, aquamvs]

# Dependency graph
requires:
  - phase: 02-corner-transfer/02-01
    provides: detect_corners, detect_validation_set, build_board_geometry, depth_bearing_cameras
  - phase: 01-data-environment
    provides: GroundTruthDataset with depth_map_path, fused_cloud_path, validation_frames
provides:
  - build_projection_models(calib, cameras) -> dict[str, RefractiveProjectionModel] using K_new
  - sample_map_bilinear(map2d, pixels_uv) -> np.ndarray with NaN propagation
  - back_project(model, pixels_uv, depths) -> (N,3) world points via origins+depth*directions
  - CornerRecord dataclass keyed by (frame_idx, camera_id, corner_id) with point_3d/method/confidence/pixel
  - transfer_frame_camera(..., fused_cloud_points) -> (list[CornerRecord], counts)
  - transfer_corners.py CLI — 8x12 sweep, corners.npz + dropout_report.json
  - HEADLINE dropout: 0.4% (10/2611 corners required plane-fit fallback; 2 unrecovered)
affects:
  - 02-03 (plane-fit fallback analysis)
  - 03-flatness-metric (consumes corners.npz directly)
  - 04-scale-check (consumes corners.npz directly)

# Tech tracking
tech-stack:
  added: [open3d (read_point_cloud), torch.nn.functional.grid_sample]
  patterns:
    - "Exact replication of aquamvs fusion path: origins + depth*directions via model.cast_ray"
    - "Fused cloud loaded at most once per frame (~650 MB); passed as fused_cloud_points to avoid per-camera reloads"
    - "NaN-mask channel sampled with padding_mode='border' to catch bilinear-neighbour NaN bleed"
    - "Board plane seeded from ChArUco->PnP; SVD refit on thin-slab crop of fused cloud (12 mm)"

key-files:
  created:
    - analysis/projection.py
    - analysis/corner_transfer.py
    - analysis/transfer_corners.py
    - data/analysis_output/corner_transfer/corners.npz
    - data/analysis_output/corner_transfer/corners_schema.json
    - data/analysis_output/corner_transfer/dropout_report.json
  modified: []

key-decisions:
  - "K_new (post-undistortion) used for projection models, NOT cam.K — corners and depth maps share the undistorted grid"
  - "sample_map_bilinear: NaN-mask channel with padding_mode='border' catches bilinear bleed from NaN neighbours"
  - "Fused cloud (~12M pts per frame) loaded once per frame; passed as argument to transfer_frame_camera to avoid repeated 650 MB loads"
  - "Board plane seeded by ChArUco->PnP (approximate, through refractive interface); SVD refit on 12 mm slab crop of fused cloud is the PRIMARY fallback plane"
  - "Degraded fallback: if cloud/slab unavailable, SVD on direct corners; if <3 direct pts, corner is unrecovered"
  - "corners.npz schema: parallel arrays frame_idx/camera_id/corner_id/points(N,3)/method/confidence/pixels(N,2)"

patterns-established:
  - "Refractive model built with build_projection_models; always pass cameras list from depth_bearing_cameras(ds)"
  - "transfer_frame_camera accepts pre-loaded fused_cloud_points to avoid per-camera cloud reload"
  - "Dropout report: per-(frame,camera) rows + headline rate in [0,1]; consumed by XFER-04 check"

requirements-completed: [XFER-02, XFER-03, XFER-04]

# Metrics
duration: 35min
completed: 2026-06-30
---

# Phase 2 Plan 02: Depth Back-Projection + Corner Transfer Summary

**Refractive depth back-projection of 2611 ChArUco corners to MVS world-frame 3D points (99.6% direct, 0.4% plane-fit fallback from fused-cloud slab); corners.npz ready for Phases 3-4**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-06-30T11:42:53Z
- **Completed:** 2026-06-30T11:48:36Z
- **Tasks:** 3
- **Files modified:** 3 created

## Accomplishments
- `analysis/projection.py` replicates the aquamvs fusion back-projection path exactly (origins + depth*directions via cast_ray, K_new from compute_undistortion_maps), with bilinear depth/confidence sampling including NaN propagation
- `analysis/corner_transfer.py` implements direct depth gating (confidence >= 0.1), fused-cloud thin-slab plane fit (12 mm slab, ChArUco->PnP seed -> SVD refit), and ray-plane intersection fallback for dropped corners
- `analysis/transfer_corners.py` CLI sweeps 8 validation frames x 12 cameras, loads fused cloud once per frame (~12M points), persists `corners.npz` + `dropout_report.json`; headline dropout rate 0.4% (10/2611 plane_fit, 2 unrecovered)

## Task Commits

Each task was committed atomically:

1. **Task 1: Projection-model builder + sampling + back-projection primitives** - `b5f0d3e` (feat)
2. **Task 2: Corner transfer with confidence gating and plane-fit fallback** - `8e9a09a` (feat)
3. **Task 3: Full-validation transfer CLI — persist corners + dropout report** - `9b60a94` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `analysis/projection.py` — build_projection_models (K_new), sample_map_bilinear (F.grid_sample + NaN-mask), back_project (exact fusion path)
- `analysis/corner_transfer.py` — CornerRecord, fit_board_plane, intersect_ray_plane, board_pose_seed (PnP+SVD), crop_cloud_to_slab, transfer_frame_camera
- `analysis/transfer_corners.py` — CLI with argparse; fused cloud loaded once per frame; corners.npz + dropout_report.json output
- `data/analysis_output/corner_transfer/corners.npz` — 2609 corners (parallel arrays: frame_idx, camera_id, corner_id, points (N,3), method, confidence, pixels (N,2))
- `data/analysis_output/corner_transfer/corners_schema.json` — column descriptions + min_confidence used
- `data/analysis_output/corner_transfer/dropout_report.json` — per-(frame,camera) + headline rate 0.4%

## Decisions Made
- Used K_new (post-undistortion intrinsics) from compute_undistortion_maps, NOT cam.K — corners were detected on undistorted images; depth maps share the same undistorted pixel grid
- NaN-mask channel sampled separately with padding_mode="border" to detect bilinear bleed from NaN source pixels (corners near depth holes treated as missing)
- Fused cloud argument pattern: caller (transfer_corners.py) loads once per frame and passes as fused_cloud_points to transfer_frame_camera; lazy load inside only if caller omits it
- Board plane seed: ChArUco->PnP in camera frame -> world frame via R_cam.T; approximate through refractive interface but sufficient to locate the 12 mm slab
- Primary fallback plane is fit by SVD on the thin-slab crop of the fused dense cloud; only falls back to direct-corner SVD if cloud is unavailable or slab has < 3 points

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] RefractiveProjectionModel lacks .eval() method**
- **Found during:** Task 1 (projection model construction)
- **Issue:** Called model.eval() following nn.Module convention; RefractiveProjectionModel is not a torch.nn.Module
- **Fix:** Removed model.eval() call; no functional impact (model is always in inference mode)
- **Files modified:** analysis/projection.py
- **Verification:** Task 1 verification script passed
- **Committed in:** b5f0d3e (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — minor API assumption)
**Impact on plan:** One-line fix; no scope change.

## Issues Encountered
- RefractiveProjectionModel.eval() AttributeError: model is not an nn.Module; removed the call (first verification run).

## Headline Dropout Rate (XFER-04)

**0.4%** — 10 of 2611 detected corners required plane-fit fallback (2 were unrecovered due to no seed+cloud for (frame=8, camera=e3v829d) which had only 2 corners with invalid depth and no plane seed).

Full breakdown:
- total_detected: 2611
- total_direct: 2599 (99.5%)
- total_plane_fit: 10 (0.4%)
- total_unrecovered: 2 (0.08%)

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `data/analysis_output/corner_transfer/corners.npz` is ready for Phase 3 (flatness metric) and Phase 4 (scale check) to consume directly
- `dropout_report.json` provides XFER-04 evidence
- The 2 unrecovered corners (frame 8, camera e3v829d — only 2 corners detected, both with invalid depth, no PnP seed possible) are correctly counted and reported; Phase 3/4 should handle gracefully
- All 3D points verified finite and Z > water_z (1.0306); corners are in the MVS world frame

---
*Phase: 02-corner-transfer*
*Completed: 2026-06-30*
