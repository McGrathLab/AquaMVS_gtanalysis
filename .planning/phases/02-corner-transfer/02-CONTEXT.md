# Phase 2: Corner Transfer - Context

**Gathered:** 2026-06-30
**Status:** Ready for planning

*Captured in auto mode. The design doc (§3.2, §3.3, §7.5) is prescriptive about this method, and Phase 1 surfaced the concrete data facts. This file locks those decisions so the planner can act without re-asking. Decisions are grounded in the live `aquamvs` v1.5.2 source (see Specific Ideas for the exact hook).*

<domain>
## Phase Boundary

Place image-detected ChArUco corners as **3D points in the MVS world frame** by sampling each camera's MVS depth map at the corner pixel and back-projecting through the refractive model — the same back-projection fusion uses. Delivers XFER-01..04: subpixel detection, depth-based transfer, plane-fit fallback for dropouts, and a measured dropout rate. **Computing accuracy metrics from these corners is Phase 3+** — Phase 2 only produces the trustworthy 3D corner sets and reports how it got each one (direct depth vs fallback).

</domain>

<decisions>
## Implementation Decisions

### ChArUco detection (XFER-01)
- Reuse the AquaCal ChArUco detector for the known board (**12×9, square 60 mm, marker 45 mm, DICT_5X5_100**) — do not re-implement detection.
- **Detect on the pipeline's `undistorted/<cam>.png` images**, not the raw `frames/` images. The depth maps live on the undistorted pixel grid (the pipeline undistorts, then computes depth), so corner pixels must be in that same grid to index the depth map correctly.
- Apply subpixel corner refinement (e.g. `cornerSubPix`); corners are the high-contrast black/white junctions ChArUco localizes to subpixel.
- Detect per camera, independently, for the **12 depth-bearing cameras**. Skip `e3v8250` (auxiliary fisheye, no depth map — confirmed Phase 1).
- Run on the **8 held-out validation frames** by default (indices 1,2,3,4,6,7,8,9). Overlap frames 0 and 5 remain loadable but are not in the default set.

### Depth-based transfer (XFER-02) — the core primitive
- For each detected corner pixel, **bilinearly sample the camera's depth map** (the `depth` array in the `.npz`; the file also carries a `confidence` array — Phase 1 finding).
- Back-project by **replicating the fusion path exactly** (do NOT re-derive geometry):
  `origins, directions = model.cast_ray(pixels); point_3d = origins + depth * directions`
  i.e. the stored depth is the ray-parameter along the `cast_ray` direction. This guarantees corner transfer matches how fusion itself placed the dense cloud, so corners and cloud live in one consistent frame.
- Use the per-camera `RefractiveProjectionModel` from the loaded calibration (refractive interface: n_air=1.0, n_water=1.333, water_z≈1.03 m — Phase 1).
- Output 3D corners in the **MVS world frame**, keyed by `(frame_idx, camera_id, charuco_corner_id)` so Phase 3 can compare the same corner across cameras (cross-camera agreement) and across frames.

### Validity & plane-fit fallback (XFER-03)
- A corner's direct depth is **valid** when the sampled depth is positive/finite and its confidence clears a threshold (default aligned to the pipeline's `min_confidence`, ≈0.1 — confirm against the saved maps; treat as Claude's discretion to tune).
- **Fallback for invalid/dropped corners:** fit the **board plane** from the dense board points (crop the fused cloud / dense points to a thin slab around the board pose, which is known image-side from ChArUco→PnP), then take the corner's 3D position as the intersection of its back-projected corner ray with that fitted plane. This is robust to per-pixel depth dropouts.
- Every transferred corner records **which method produced it** (`direct` vs `plane_fit`) and its source confidence, so downstream metrics can weight or filter.
- Order matches the design: direct depth at the junction first; plane-fit only where direct depth is missing/weak.

### Dropout reporting (XFER-04)
- Compute and report, **per frame and per camera**, the fraction of detected corners that had valid direct depth vs required the plane-fit fallback.
- Persist this as a small structured artifact (table/JSON) plus a one-line headline rate. This is the number that decides whether the project leans on §3.2 (direct) or §3.3 (plane-fit) — surface it prominently for the Phase 3/manuscript narrative.

### Output / persistence
- Persist the transferred corner sets to disk (under the analysis output area) in a structured, reloadable form keyed by `(frame, camera, corner_id)` with fields: 3D point (world frame), method flag, confidence, and the source 2D pixel. Phases 3–4 consume this directly — they should not need to re-run detection or transfer.

### Claude's Discretion
- Exact persisted file format (npz / parquet / json) and on-disk layout.
- Plane-fit estimator (RANSAC vs SVD/total-least-squares) and slab thickness for board-point cropping.
- Confidence-threshold value (default to the pipeline's `min_confidence`; tune if dropout is pathological).
- Bilinear sampling implementation details and handling of corners that fall on depth-map NaN/zero borders.
- Whether to also retain corners from frames 0 and 5 (overlap) for diagnostics — not required.

</decisions>

<specifics>
## Specific Ideas

- **Exact hook to replicate:** `aquamvs/fusion.py` lines ~133–134 (and ~289–290) do
  `origins, directions = ref_model.cast_ray(pixels); points_3d = origins + depths * directions`.
  Corner transfer should use this same construction with `aquamvs.projection.refractive.RefractiveProjectionModel.cast_ray` (defined in `projection/refractive.py:65`, protocol in `projection/protocol.py:36`). `cast_ray` takes a torch tensor of pixels and returns `(origins, directions)`.
- Depth `.npz` per camera/frame holds two 1200×1600 float32 arrays: `depth` and `confidence` (Phase 1). Sample `depth`; gate on `confidence`.
- Detect on `output/frame_NNNNNN/undistorted/<cam>.png` to stay on the depth-map grid.
- Reuse Phase 1's `GroundTruthDataset` loader (`analysis/loader.py`) for calibration, models, depth maps, and frame/camera enumeration — don't re-parse calibration.

</specifics>

<deferred>
## Deferred Ideas

- Inter-corner grid-regularity metric (§4.4) — already v2 (GRID-01), not Phase 2.
- Orthophoto / pure-cloud corner detection (§3.4) — backup only; build only if depth-based transfer + plane-fit both prove insufficient on real data.
- All metric computation (flatness, spatial consistency, cross-camera agreement, scale) — Phases 3–4.

</deferred>

---

*Phase: 02-corner-transfer*
*Context gathered: 2026-06-30*
