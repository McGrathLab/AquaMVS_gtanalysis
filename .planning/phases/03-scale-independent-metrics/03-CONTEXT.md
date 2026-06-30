# Phase 3: Scale-Independent Metrics - Context

**Gathered:** 2026-06-30
**Status:** Ready for planning

*Captured in auto mode. This is the headline phase — the non-circular accuracy numbers. Decisions below are grounded in design §4.1–4.3, the Phase 2 corner outputs, the live `aquamvs` evaluation hooks, and the confirmed rig fact (the array images a volume larger than any single camera's FOV).*

<domain>
## Phase Boundary

Compute the three **scale-independent (non-circular)** accuracy metrics — flatness (MET-01), spatial/angular consistency (MET-02), and cross-camera agreement (MET-03) — over the 8 held-out frames, and persist them for downstream consumption. **Everything here is computed in the raw MVS frame, BEFORE any rigid/scale alignment to the ideal board** (that alignment + the absolute-scale check are Phase 4). This phase produces and locks the numbers; **rendering the figure and the results table is Phase 5.** Phase 3 = compute + persist values, not plots.

</domain>

<decisions>
## Implementation Decisions

### The ordering invariant (why this phase exists separately)
- All three metrics are computed from the MVS reconstruction **as-is**, with **no rigid/scale alignment to the ideal board applied first**. A scale or pose fit must never run before these numbers are recorded — otherwise it could absorb the very error we're measuring. Phase 4 may align afterward; Phase 3 outputs are immutable once written.

### Inputs (reuse Phase 1 + Phase 2, do not recompute)
- Dense board surface points: crop each frame's fused cloud (`point_cloud/fused.ply`, ~586 MB) to a thin slab around the board, using the board pose known image-side from ChArUco→PnP (same machinery Phase 2's plane-fit fallback used). These cropped dense points drive flatness.
- Transferred corners: `data/analysis_output/corner_transfer/corners.npz` (2,609 corners keyed by `(frame_idx, camera_id, corner_id)`, with 3D point + method + confidence). These drive size/spacing and cross-camera agreement. No re-detection or re-transfer.
- Loader: `analysis/loader.py` `GroundTruthDataset` for calibration, models, paths, and the 8-frame validation split.

### MET-01 — Flatness (the single strongest non-circular number)
- Definition: fit a plane to each frame's **dense board points** and report the **RMS of point-to-plane residuals** (per frame), plus a pooled value across frames.
- Use a robust fit (e.g. RANSAC to reject outliers, then refit the plane to inliers by SVD/total-least-squares); report inlier count and the residual RMS in mm.
- Do **not** force `height_map_difference` for this — that hook compares two clouds on an XY grid, which is the wrong primitive for single-cloud plane-fit RMS. (It remains available if a planner finds a clean use; the *metric definition* above is what's locked.)
- This number is the board's known flatness vs reconstructed flatness, i.e. pure MVS noise/distortion — independent of scale and of any calibration overlap.

### MET-02 — Spatial / angular consistency (the highest-value output)
- For each of the 8 frames (each a distinct board pose), compute and record: board **centroid 3D position** (XY + depth from the rig), board **tilt** (angle of the fitted plane normal), board **flatness RMS** (from MET-01), and a board **size measure** (inter-corner spacing / fitted board extent from the corners).
- The deliverable is how these **vary across the working volume** — flatness and size as functions of depth, lateral position, and tilt. Report the spread/trend (ranges, and the relationship, e.g. flatness-vs-depth, size-vs-tilt), not just per-frame points.
- Framing is **consistency, not absolute accuracy**: report size *variation* across the volume (e.g. coefficient of variation / range), since absolute size correctness is the partly-circular MET-04 (Phase 4). Variance is non-circular even with global scale locked.
- This is the metric that most directly tests "does the refractive model hold across the volume."

### MET-03 — Cross-camera agreement
- For each `(frame_idx, corner_id)` **co-observed by ≥2 depth cameras**, compare the 3D positions each camera's depth independently places that corner at; report the dispersion (e.g. RMS distance of the per-camera points to their centroid), aggregated per frame and overall, in mm.
- **Rig fact — do NOT treat sparse cameras as error:** the array images a volume larger than any one camera's FOV, so each board pose is seen by only a *subset* of cameras; per-(frame,camera) corner counts vary widely (0, 2, 12, 52…) by design. A camera that sees nothing is a non-event, not a dropout. Agreement is measured **only among co-observing cameras** (shared corner IDs).
- Apply a **coverage threshold**: ignore camera observations with too few corners to be meaningful (e.g. a 2-corner glimpse) when computing agreement; record what was included/excluded. Weight or filter by per-camera coverage rather than treating all 12 cameras equally.
- Needs no ground truth — it's an internal consistency check on the dense depth.

### Units & persistence
- Report distances in **mm**. Persist a structured metrics artifact (per-frame records + pooled summary) under `data/analysis_output/` (e.g. JSON/CSV), keyed so Phase 5 can build the table and the spatial-consistency figure directly. Print a concise human-readable summary to stdout.

### Claude's Discretion
- Plane-fit estimator details (RANSAC params, slab thickness for board cropping, inlier criteria).
- Exact dispersion statistic for MET-03 and the coverage threshold value.
- The precise "size" estimator (mean inter-corner spacing vs fitted rectangle extent) and how tilt/depth are parameterized.
- Output file format/layout, as long as it's reloadable and Phase-5-friendly.
- Whether to memory-manage the large fused clouds via cropping-on-load vs streaming.

</decisions>

<specifics>
## Specific Ideas

- Reuse the board-slab crop + plane-pose logic already written for Phase 2's fallback (`analysis/corner_transfer.py`) rather than re-deriving the board pose.
- Cross-camera agreement consumes the per-camera corner sets in `corners.npz` directly — those are exactly the independent per-camera placements MET-03 compares.
- Keep flatness (dense surface) and size/agreement (sparse corners) as distinct data paths: flatness wants the dense board cloud; spacing/agreement want the corner junctions.
- Available hooks if useful: `aquamvs.evaluation.metrics.{height_map_difference, cloud_to_cloud_distance, reprojection_error}`. None are required for the locked metric definitions above; the planner may use them where they genuinely fit.

</specifics>

<deferred>
## Deferred Ideas

- Rigid/Umeyama alignment to the ideal board + absolute-scale check (MET-04, MET-05) — Phase 4. Must not run before Phase 3 metrics are recorded.
- Inter-corner grid-regularity metric (§4.4, GRID-01) — v2.
- The spatial-consistency figure and results table (OUT-01/OUT-02) — Phase 5. Phase 3 only computes/persists the values.

</deferred>

---

*Phase: 03-scale-independent-metrics*
*Context gathered: 2026-06-30*
