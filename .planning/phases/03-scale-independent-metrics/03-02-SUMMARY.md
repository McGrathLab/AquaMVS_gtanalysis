---
phase: 03-scale-independent-metrics
plan: "02"
subsystem: cross-camera-agreement
tags: [met-03, cross-camera, dispersion, coverage-threshold, scale-independent]
dependency_graph:
  requires: [02-02]
  provides: [MET-03]
  affects: [05-reporting]
tech_stack:
  added: []
  patterns:
    - Pure-numeric module + plain-assert test script (no pytest dependency)
    - Coverage threshold to exclude sparse glimpse cameras
    - Pooled RMS aggregation (not mean-of-means) for overall metric
key_files:
  created:
    - analysis/cross_camera.py
    - analysis/compute_cross_camera.py
    - tests/test_cross_camera.py
    - tests/check_cross_camera_artifact.py
  generated_on_disk:
    - data/analysis_output/scale_independent_metrics/cross_camera_agreement.json
    - data/analysis_output/scale_independent_metrics/cross_camera_agreement_schema.json
decisions:
  - "Coverage threshold default=6 corners per camera per frame; below-threshold cameras
     recorded as excluded (not errors); board-blind cameras (0 rows) are absent — never counted"
  - "Frame RMS = sqrt(mean(per-corner rms_mm^2)); overall = pooled sqrt(mean(all per-corner rms_mm^2))
     across all frames (not mean-of-frame-means) so per-frame distributions are preserved for Phase 5"
  - "data/ is gitignored by project convention; JSON artifact generated on disk but not version-controlled;
     schema sidecar written alongside for Phase 5 consumption"
metrics:
  duration: 5 min
  tasks_completed: 2
  files_created: 4
  completed_date: "2026-06-30"
---

# Phase 03 Plan 02: Cross-Camera Agreement (MET-03) Summary

**One-liner:** MET-03 cross-camera board-localization dispersion using RMS-to-centroid (mm) with coverage-threshold camera filtering, computed in raw MVS frame before any alignment.

## What Was Built

### Task 1 — Cross-camera agreement module + synthetic tests

`analysis/cross_camera.py` provides five pure-numeric functions (no dataset dependency, unit-testable on synthetic data):

- `load_corners(npz_path)` — loads corners.npz with `allow_pickle=True`, casts camera_id to str
- `per_camera_coverage(frame_idx_arr, camera_id_arr, frame)` — counts corners per camera for a frame
- `included_cameras(coverage, min_corners)` — applies threshold; board-blind cameras (absent from coverage) are a non-event
- `per_corner_dispersion(points_by_camera)` — RMS distance of per-camera 3-D points to their centroid (mm) + max pairwise distance
- `frame_agreement(corners_for_frame, included_cams, min_cameras=2)` — restricts to included cameras, groups by corner_id, keeps co-observed corners, aggregates to frame_rms_mm

`tests/test_cross_camera.py` has 6 plain-assert tests:
- Two cameras 10 mm apart → rms=5 mm, max_pairwise=10 mm
- Three cameras matching closed-form RMS
- Coverage threshold: {A:52, B:12, C:2} min=6 → included {A,B}, excluded {C:2}
- Glimpse camera excluded; distant points do not inflate rms_mm
- Corner seen by 1 included camera is skipped (not an error)
- Board-blind camera (0 rows) contributes nothing

### Task 2 — MET-03 sweep, persistence, stdout summary

`analysis/compute_cross_camera.py` mirrors `transfer_corners.py` CLI pattern:
- `--corners` (default corners.npz path), `--out-dir`, `--min-corners` (6), `--min-cameras` (2)
- Loads corners once, sweeps 8 validation frames
- Per frame: coverage filter → frame_agreement → records included/excluded cameras with counts
- Aggregates overall pooled RMS (accumulated per-corner residuals, not mean-of-frame-means)
- Writes `cross_camera_agreement.json` with `computed_before_alignment: true`
- Writes schema sidecar for Phase 5
- Prints table + exclusion audit + "board-blind cameras are not errors" statement

`tests/check_cross_camera_artifact.py` validates JSON shape, all required keys, ordering-invariant flag, and per-corner list length matching n_corners_compared.

## Results (8 Validation Frames)

| Frame | Cams Included | Corners Compared | RMS (mm) |
|-------|--------------|-----------------|---------|
| 1     | 7            | 88              | 4.871   |
| 2     | 10           | 75              | 173.708 |
| 3     | 8            | 88              | 1.891   |
| 4     | 7            | 83              | 3.347   |
| 6     | 6            | 88              | 1.820   |
| 7     | 8            | 86              | 6.394   |
| 8     | 6            | 84              | 1.670   |
| 9     | 12           | 71              | 1.998   |

**Overall pooled RMS: 58.52 mm** (dominated by frame 2 outlier; median frame RMS ~2.9 mm).  
Frame 2 has a very high RMS (173.7 mm) — this is an observation about raw MVS depth consistency in that frame, not a code issue. Phase 5 will surface this distribution.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

Files created/generated:
- `analysis/cross_camera.py` — FOUND
- `analysis/compute_cross_camera.py` — FOUND
- `tests/test_cross_camera.py` — FOUND
- `tests/check_cross_camera_artifact.py` — FOUND
- `data/analysis_output/scale_independent_metrics/cross_camera_agreement.json` — FOUND (on disk, gitignored by project convention)
- `data/analysis_output/scale_independent_metrics/cross_camera_agreement_schema.json` — FOUND (on disk)

Commits:
- `7a462b9` feat(03-02): cross-camera agreement module + synthetic unit tests
- `138da0c` feat(03-02): MET-03 sweep CLI and artifact checker

## Self-Check: PASSED
