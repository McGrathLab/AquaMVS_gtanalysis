---
phase: 02-corner-transfer
verified: 2026-06-30T00:00:00Z
status: passed
score: 9/9 must-haves verified
re_verification: false
---

# Phase 2: Corner Transfer Verification Report

**Phase Goal:** Image-detected ChArUco corners are placed as 3D points in the MVS frame via refractive back-projection through the depth maps, with a measured dropout rate.
**Verified:** 2026-06-30
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | Subpixel ChArUco corners detected on undistorted images of 12 depth-bearing cameras across 8 validation frames | VERIFIED | 2611 corners across 75/96 (frame,camera) pairs; grand total confirmed by corners.npz N=2609 (2 unrecovered) |
| 2  | Detection reuses AquaCal `detect_charuco` + `BoardGeometry` — no re-implementation | VERIFIED | `from aquacal.io.detection import detect_charuco` imported and called at charuco_detect.py:39,129 |
| 3  | Each detection yields integer corner_ids (0..87) and float (u,v) pixels on undistorted grid | VERIFIED | corner_id range [0, 87] confirmed; pixels (2609,2) all finite |
| 4  | Each detected corner pixel samples its camera's MVS depth map bilinearly and back-projects via `RefractiveProjectionModel.cast_ray` to a 3D point | VERIFIED | `model.cast_ray(pixels)` at projection.py:200; `origins + depths_t * directions` replicates fusion path exactly |
| 5  | Back-projection uses K_new (post-undistortion intrinsics) from `compute_undistortion_maps` | VERIFIED | `K_new = compute_undistortion_maps(cam).K_new` at projection.py:80; K_new passed to RefractiveProjectionModel |
| 6  | Corners with missing/weak depth fall back to board plane fit from a thin-slab crop of the fused dense cloud (PRIMARY source), flagged method='plane_fit' | VERIFIED | `ds.fused_cloud_path(frame)` called at corner_transfer.py:369; `crop_cloud_to_slab` + `fit_board_plane` on slab; 10 plane_fit corners confirmed |
| 7  | Fused dense cloud is PRIMARY plane-fit source; direct-corner SVD is only a degraded last resort | VERIFIED | Code logic: cloud slab fit attempted first; direct-corner SVD fallback only if cloud unavailable or slab < 3 pts |
| 8  | Reloadable corner artifact keyed by (frame_idx, camera_id, corner_id) persisted with point_3d/method/confidence/pixel | VERIFIED | corners.npz: parallel arrays frame_idx/camera_id/corner_id/points(2609,3)/method/confidence/pixels(2609,2) all confirmed |
| 9  | Per-frame/per-camera dropout fractions and single headline dropout rate computed and written | VERIFIED | dropout_report.json: 96 per-(frame,camera) rows + headline rate=0.0038 (0.38%); partition n_direct+n_plane_fit+n_unrecovered == n_detected confirmed |

**Score:** 9/9 truths verified

---

### Required Artifacts

| Artifact | Min Lines | Actual Lines | Status | Details |
|----------|-----------|-------------|--------|---------|
| `analysis/charuco_detect.py` | 60 | 178 | VERIFIED | Exposes build_board_geometry, depth_bearing_cameras, detect_corners, detect_validation_set; calls detect_charuco |
| `analysis/detect_corners.py` | 40 | 129 | VERIFIED | CLI with argparse --data-root; prints 8x12 corner-count table; exits 1 only on grand_total==0 |
| `analysis/projection.py` | 70 | 204 | VERIFIED | build_projection_models (K_new), sample_map_bilinear (F.grid_sample + NaN-mask), back_project (origins+depth*directions) |
| `analysis/corner_transfer.py` | 110 | 457 | VERIFIED | CornerRecord, fit_board_plane, intersect_ray_plane, board_pose_seed (PnP+SVD fallback), crop_cloud_to_slab, transfer_frame_camera |
| `analysis/transfer_corners.py` | 60 | 315 | VERIFIED | Full CLI; fused cloud loaded once per frame; persists corners.npz + dropout_report.json; prints headline rate |
| `data/analysis_output/corner_transfer/corners.npz` | — | N=2609 | VERIFIED | All required arrays present; points (2609,3) all finite; methods subset of {direct,plane_fit}; frame_idx in {1,2,3,4,6,7,8,9} |
| `data/analysis_output/corner_transfer/dropout_report.json` | — | 96 rows | VERIFIED | headline.dropout_rate=0.0038 in [0,1]; per_frame_camera has 96 rows; partition check passed |

---

### Key Link Verification

#### Plan 02-01 Key Links

| From | To | Via | Status | Evidence |
|------|----|-----|--------|----------|
| `analysis/charuco_detect.py` | `aquacal.io.detection.detect_charuco` | direct call on undistorted image | WIRED | Line 39 imports; line 129 calls `detect_charuco(image, board)` |
| `analysis/charuco_detect.py` | `analysis/loader.py GroundTruthDataset` | `undistorted_image_path` | WIRED | Line 111 calls `ds.undistorted_image_path(frame, camera)` |

#### Plan 02-02 Key Links

| From | To | Via | Status | Evidence |
|------|----|-----|--------|----------|
| `analysis/projection.py` | `aquamvs.projection.refractive.RefractiveProjectionModel.cast_ray` | `origins + depth * directions` | WIRED | Line 200: `origins, directions = model.cast_ray(pixels)`; line 202: `pts = origins + depths_t * directions` |
| `analysis/projection.py` | `aquamvs.calibration.compute_undistortion_maps` | K_new for post-undistortion model | WIRED | Line 41 imports; line 80 calls `K_new = compute_undistortion_maps(cam).K_new` |
| `analysis/transfer_corners.py` | `analysis/charuco_detect.py detect_corners` | 2D corners before transfer_frame_camera | WIRED | Line 42 imports `detect_corners`; line 94 calls it per (frame,camera) |
| `analysis/corner_transfer.py` | `analysis/loader.py fused_cloud_path` | thin-slab crop of fused dense cloud | WIRED | Line 369 calls `ds.fused_cloud_path(frame)` in the plane-fit fallback path |
| `analysis/transfer_corners.py` | `analysis/corner_transfer.py transfer_frame_camera` | per-(frame,camera) transfer + dropout aggregation | WIRED | Line 45 imports; line 133 calls `transfer_frame_camera(...)` |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| XFER-01 | 02-01-PLAN.md | Subpixel ChArUco detection reusing AquaCal detector | SATISFIED | 2611 corners detected across 75/96 pairs; detect_charuco called on undistorted images |
| XFER-02 | 02-02-PLAN.md | Bilinear depth sampling + RefractiveProjectionModel.cast_ray back-projection | SATISFIED | sample_map_bilinear + back_project via cast_ray; K_new used; exact fusion path replicated |
| XFER-03 | 02-02-PLAN.md | Plane-fit fallback for missing/weak depth from dense points | SATISFIED | Fused-cloud slab crop (12 mm) + SVD plane fit; 10 plane_fit corners confirmed |
| XFER-04 | 02-02-PLAN.md | Corner-depth dropout rate measured and reported | SATISFIED | dropout_report.json headline 0.38%; 96 per-(frame,camera) rows; partition verified |

All 4 required requirements satisfied. No orphaned requirements (REQUIREMENTS.md traceability table maps XFER-01..04 exclusively to Phase 2; no additional XFER IDs mapped to this phase).

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `analysis/corner_transfer.py` | 308 | `return [], {...}` | Info | Legitimate early-return guard for missing depth path (defensive; NO_DEPTH_CAMERAS already excludes e3v8250 upstream); not a stub |

No blocking or warning-level anti-patterns.

---

### Human Verification Required

None. All success criteria are verifiable programmatically. The headline dropout rate of 0.38% and the 2 unrecovered corners (frame 8, camera e3v829d — only 2 corners detected, both with invalid depth, no PnP seed possible) are consistent with the documented output and match the SUMMARY report.

---

### Summary

Phase 2 goal is fully achieved. All 5 source code artifacts are substantive (no stubs), all 7 key links are wired and active, and both data output files are present and structurally correct:

- **XFER-01:** 2611 corners detected across 75/96 (frame,camera) pairs on undistorted images using the AquaCal detector for the known 12x9 board.
- **XFER-02:** Every detected corner with valid depth bilinearly samples the MVS depth map and back-projects through `RefractiveProjectionModel.cast_ray` using K_new — the exact fusion construction.
- **XFER-03:** 10 corners with missing/weak depth are placed via ray-plane intersection against a board plane fit from a 12 mm thin-slab crop of the fused dense cloud.
- **XFER-04:** `dropout_report.json` records 96 per-(frame,camera) rows and a headline rate of 0.38%; `corners.npz` holds the 2609 recovered corners (2 unrecovered) keyed by frame_idx/camera_id/corner_id with point_3d/method/confidence/pixel arrays all finite.

Phases 3 and 4 can consume `corners.npz` and `dropout_report.json` directly without re-running detection or transfer.

---

_Verified: 2026-06-30_
_Verifier: Claude (gsd-verifier)_
