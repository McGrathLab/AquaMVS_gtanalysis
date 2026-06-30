---
phase: 03-scale-independent-metrics
plan: "01"
subsystem: analysis
tags: [numpy, open3d, ransac, svd, plane-fit, charuco, metrics, met-01, met-02]

# Dependency graph
requires:
  - phase: 02-corner-transfer
    provides: corners.npz with 2609 transferred ChArUco corner 3D positions
  - phase: 01-data-environment
    provides: fused point clouds (fused.ply ~586 MB per frame), loader.py, calibration

provides:
  - robust_plane_fit (RANSAC + SVD refit, rms_mm in metres->mm)
  - plane_tilt_deg (sign-agnostic, reference-direction angle)
  - board_size_from_corners (median adjacent-pair spacing, mm)
  - MET-01 per-frame + pooled dense-board flatness RMS (pooled=1.09mm)
  - MET-02 per-frame centroid/depth/tilt/size + variation summary (size CV=0.0015)
  - flatness_consistency.json artifact with computed_before_alignment=true
  - 6 synthetic unit tests covering all three functions

affects:
  - 03-scale-independent-metrics (plan 02 MET-03 depends on corners.npz)
  - 04-scale-check (reads flatness_consistency.json; must not run before this plan)
  - 05-figures-results-table (reads flatness_consistency.json per_frame_arrays for plots)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - RANSAC + SVD-refit plane fit (sample 3 pts, count inliers, refit via fit_board_plane)
    - Load fused cloud once per frame, crop to slab, set cloud=None before next frame
    - Seeds board location from corner plane fit (cheap, no PnP) for dense slab crop
    - Pooled RMS accumulated as squared residuals (not mean-of-means)

key-files:
  created:
    - analysis/flatness.py
    - analysis/compute_flatness_consistency.py
    - tests/test_flatness.py
    - tests/check_flatness_artifact.py
  modified: []

key-decisions:
  - "board_size_from_corners uses median adjacent-pair 3D spacing (not fitted extent) for MET-02 consistency; docstring flags this as variation measure, not absolute accuracy (MET-04 is Phase 4)"
  - "depth_m defined as centroid projection onto calib.interface_normal (rig viewing axis) for cross-frame comparability; documented in script"
  - "data/ is gitignored by design; JSON artifacts exist on disk but are not committed — only code is versioned"
  - "Seed plane for slab crop comes from fit_board_plane on transferred corners (cheap, no PnP/detection), consistent with Phase 2 fallback pattern"

patterns-established:
  - "Ordering invariant docstring in both modules: state RAW MVS frame + no alignment before these numbers"
  - "Per-frame cloud load-once-drop pattern (cloud = None after crop) matches transfer_corners.py"
  - "Artifact has computed_before_alignment: true as a machine-readable ordering guarantee"

requirements-completed: [MET-01, MET-02]

# Metrics
duration: 6min
completed: 2026-06-30
---

# Phase 03 Plan 01: Flatness & Spatial/Angular Consistency Summary

**RANSAC+SVD dense-board plane-fit flatness (MET-01 pooled=1.09 mm) and per-frame centroid/tilt/size consistency sweep (MET-02 size CV=0.0015) over 8 validation frames, raw MVS frame, no alignment**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-06-30T16:12:02Z
- **Completed:** 2026-06-30T16:17:57Z
- **Tasks:** 2
- **Files modified:** 4 created (+ 2 JSON artifacts on disk, gitignored)

## Accomplishments

- Flatness numerics module (`analysis/flatness.py`) with three pure-numeric functions: `robust_plane_fit` (RANSAC + SVD refit, rms in mm), `plane_tilt_deg` (sign-agnostic tilt angle), `board_size_from_corners` (median adjacent-corner spacing)
- 6 synthetic unit tests all passing: noise RMS recovery, outlier rejection, 0/45/90-degree tilt edge cases, 11x8 tilted-grid size at 60 mm ± 1 mm, degenerate guards
- Full MET-01/MET-02 sweep over 8 validation frames: pooled flatness RMS = 1.09 mm, per-frame range 0.99–1.15 mm; board size mean = 60.01 mm, CV = 0.0015 (very tight)
- JSON artifact `flatness_consistency.json` with `computed_before_alignment: true`, 8 per_frame records, pooled block, variation block with Phase-5-ready parallel arrays

## Task Commits

1. **Task 1: Flatness + geometry numerics module with synthetic tests** - `76038f0` (feat)
2. **Task 2: Per-frame MET-01/MET-02 sweep, persistence, and stdout summary** - `9be3da4` (feat)

## Files Created/Modified

- `analysis/flatness.py` — `robust_plane_fit`, `plane_tilt_deg`, `board_size_from_corners`; all pure-numeric, no dataset dependency
- `analysis/compute_flatness_consistency.py` — argparse CLI, 8-frame sweep, load-once-drop per frame, JSON + schema persistence, stdout table
- `tests/test_flatness.py` — 6 plain-assert synthetic tests, prints "test_flatness OK"
- `tests/check_flatness_artifact.py` — JSON shape/plausibility checks (8 records, plausible rms range, pooled/variation blocks)
- `data/analysis_output/scale_independent_metrics/flatness_consistency.json` — on disk (gitignored)
- `data/analysis_output/scale_independent_metrics/flatness_consistency_schema.json` — on disk (gitignored)

## Decisions Made

- **board_size_from_corners uses median adjacent-pair 3D spacing** (not fitted rectangle extent) — simpler, robust to missing corners, and framed as MET-02 consistency (variation across frames), not absolute size accuracy (that is MET-04 in Phase 4)
- **depth_m = centroid projected onto calib.interface_normal** — chosen so depth is on the rig viewing axis for cross-frame comparability; documented in the script
- **Seed plane from corner fit_board_plane** (not PnP re-detection) — consistent with Phase 2's plane-fit fallback pattern; corners already available from corners.npz
- **data/ gitignored** — JSON artifacts exist and verified on disk but intentionally not committed; only code is versioned (consistent with initial commit pattern for the dataset)

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- First conda run invocation got a transient Windows temp-file conflict (`__conda_tmp_xxxx.txt`); retried immediately and succeeded.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- MET-01 and MET-02 numbers are locked in `flatness_consistency.json` (on disk) before any alignment step
- Phase 4 (scale check / Umeyama/ICP alignment to ideal board) may now run — it MUST read these numbers before aligning
- Phase 5 (figures + results table) can consume `variation.per_frame_arrays` directly for flatness-vs-depth and size-vs-tilt plots
- Plan 03-02 (MET-03 cross-camera agreement) uses the same `corners.npz`; already committed per git log

---
*Phase: 03-scale-independent-metrics*
*Completed: 2026-06-30*
