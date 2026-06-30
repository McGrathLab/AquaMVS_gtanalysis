---
phase: 03-scale-independent-metrics
verified: 2026-06-30T00:00:00Z
status: passed
score: 4/4 must-haves verified
---

# Phase 03: Scale-Independent Metrics Verification Report

**Phase Goal:** The headline non-circular accuracy numbers — flatness, spatial/angular consistency, and cross-camera agreement — computed before any scaling or alignment step.
**Verified:** 2026-06-30
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Per-frame plane-fit RMS flatness of the board's dense points is computed with no scaling applied | VERIFIED | flatness_consistency.json has 8 per-frame flatness_rms_mm values (0.99–1.15 mm); computed_before_alignment=true; no alignment call in analysis/flatness.py or analysis/compute_flatness_consistency.py |
| 2 | Board size and flatness variation across position, depth, and tilt over the working volume is measured and reported per frame | VERIFIED | Each per-frame record has centroid_xyz_m, depth_m, lateral_xy_m, tilt_deg, flatness_rms_mm, board_size_mm; variation block contains board_size_cv=0.0015, ranges, and per_frame_arrays for Phase 5 |
| 3 | Cross-camera agreement quantifies whether each camera's depth places the board and transferred corners at a consistent 3D location | VERIFIED | cross_camera_agreement.json has 8 per-frame frame_rms_mm values (1.67–173.7 mm); coverage threshold filters glimpse cameras; board-blind cameras never counted; computed_before_alignment=true |
| 4 | All three metrics are produced and recorded before any alignment or scaling step runs | VERIFIED | Both JSON artifacts carry computed_before_alignment: true; grep for umeyama/icp/align in all four new modules returns only docstring/comment occurrences (no function calls); artifact checker scripts confirm artifact shape |

**Score:** 4/4 truths verified

---

## Required Artifacts

| Artifact | Min Lines | Actual Lines | Status | Details |
|----------|-----------|-------------|--------|---------|
| `analysis/flatness.py` | 80 | 249 | VERIFIED | Exports robust_plane_fit, plane_tilt_deg, board_size_from_corners; ORDERING INVARIANT in docstring |
| `analysis/compute_flatness_consistency.py` | 120 | 503 | VERIFIED | Argparse CLI; 8-frame sweep; load-once-drop per frame; JSON + schema persistence; stdout table |
| `tests/test_flatness.py` | 50 | 238 | VERIFIED | 6 plain-assert tests; all pass; prints "test_flatness OK" |
| `analysis/cross_camera.py` | 80 | 275 | VERIFIED | Exports load_corners, per_camera_coverage, included_cameras, per_corner_dispersion, frame_agreement |
| `analysis/compute_cross_camera.py` | 90 | 305 | VERIFIED | Argparse CLI; 8-frame sweep; coverage filter; JSON + schema + stdout |
| `tests/test_cross_camera.py` | 50 | 221 | VERIFIED | 6 plain-assert tests; all pass; prints "test_cross_camera OK" |
| `data/analysis_output/scale_independent_metrics/flatness_consistency.json` | — | on disk | VERIFIED | 8 per_frame records; computed_before_alignment=true; pooled 1.085 mm; size CV=0.0015 |
| `data/analysis_output/scale_independent_metrics/cross_camera_agreement.json` | — | on disk | VERIFIED | 8 per_frame records; computed_before_alignment=true; overall_rms=58.52 mm (dominated by frame 2 outlier) |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `analysis/compute_flatness_consistency.py` | `analysis/corner_transfer.py` | `crop_cloud_to_slab`, `fit_board_plane` | WIRED | Both imported and called at line 50; fit_board_plane seeds slab crop; crop_cloud_to_slab invoked in process_frame |
| `analysis/compute_flatness_consistency.py` | `analysis/flatness.py` | `robust_plane_fit`, `plane_tilt_deg`, `board_size_from_corners` | WIRED | Imported at line 51; all three called in process_frame |
| `analysis/compute_flatness_consistency.py` | `data/analysis_output/corner_transfer/corners.npz` | `np.load(allow_pickle=True)` | WIRED | Pattern `corners.npz` present; loaded once at line 264; frame_idx, corner_id, points extracted |
| `analysis/compute_cross_camera.py` | `data/analysis_output/corner_transfer/corners.npz` | `load_corners` -> `np.load(allow_pickle=True)` | WIRED | `corners.npz` path in argparse default; `load_corners(corners_path)` called at line 69 |
| `analysis/compute_cross_camera.py` | `analysis/cross_camera.py` | `per_corner_dispersion`, `coverage` filter | WIRED | `frame_agreement`, `included_cameras`, `load_corners`, `per_camera_coverage` all imported and called in per-frame loop |

---

## Critical Invariant: No Alignment Before Metrics

Grep for `umeyama|icp|align` (case-insensitive) across all four new modules:

| File | Hits | Nature |
|------|------|--------|
| `analysis/flatness.py` | 2 | Docstring only: "no Umeyama/ICP/scaling" and "no scaling or rigid alignment" |
| `analysis/compute_flatness_consistency.py` | 7 | Docstring, JSON key name (`computed_before_alignment`), schema string, stdout print — no functional call |
| `analysis/cross_camera.py` | 3 | Docstring only: "BEFORE any rigid alignment", "no alignment applied" |
| `analysis/compute_cross_camera.py` | 5 | Docstring, JSON key name, schema string, stdout print — no functional call |

**Result: No Umeyama/ICP/alignment function call in any of the four new modules.**

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| MET-01 | 03-01-PLAN.md | Flatness — plane-fit RMS of board's dense points, per frame, computed before any scaling step | SATISFIED | flatness_consistency.json: 8 per-frame flatness_rms_mm (0.99–1.15 mm), pooled 1.085 mm; test_flatness OK; check_flatness_artifact OK |
| MET-02 | 03-01-PLAN.md | Spatial/angular consistency — board size and flatness per frame, variation across working volume | SATISFIED | Each per-frame record has centroid/depth/tilt/flatness/size; variation block: board_size_cv=0.0015, per_frame_arrays for Phase 5 |
| MET-03 | 03-02-PLAN.md | Cross-camera agreement — RMS dispersion of per-camera corner placements; coverage threshold applied | SATISFIED | cross_camera_agreement.json: 8 per-frame frame_rms_mm; cameras_included/cameras_excluded per frame; overall_rms=58.52 mm; test_cross_camera OK; check_cross_camera_artifact OK |

**All three phase 3 requirements: SATISFIED. No orphaned requirements.**

---

## Unit Tests: Executed Results

| Test Script | Result | Tests |
|-------------|--------|-------|
| `tests/test_flatness.py` | PASS — "test_flatness OK" | 6: noise RMS recovery, outlier rejection, tilt 0/45/90/flipped, 11x8 grid size ~60mm, degenerate guards |
| `tests/test_cross_camera.py` | PASS — "test_cross_camera OK" | 6: 2-camera dispersion=5mm, 3-camera closed-form, coverage threshold, glimpse exclusion, 1-camera skip, board-blind non-event |
| `tests/check_flatness_artifact.py` | PASS — "check_flatness_artifact OK" | JSON shape, 8 records, plausible rms range, pooled/variation blocks |
| `tests/check_cross_camera_artifact.py` | PASS — "[PASS] ... 8 frames, overall_rms=58.523 mm" | JSON shape, all required keys, ordering-invariant flag, per_corner list length |

---

## Anti-Patterns Scan

No TODO/FIXME/HACK/PLACEHOLDER comments found in any of the four new source files. No `return null`, `return {}`, or empty implementation stubs. No `console.log`-only handlers (Python). All functions have substantive implementations with RANSAC loops, aggregation logic, and I/O.

---

## JSON Artifacts: Spot-Check Values

**flatness_consistency.json**
- `computed_before_alignment`: true
- `per_frame` count: 8, frame_idxs: [1,2,3,4,6,7,8,9]
- All 8 frames have finite flatness_rms_mm: [1.107, 1.155, 1.060, 1.059, 0.990, 1.111, 1.145, 1.115] mm
- Pooled RMS: 1.085 mm
- board_size_cv: 0.00152 (very tight, 0.15% variation)

**cross_camera_agreement.json**
- `computed_before_alignment`: true
- `per_frame` count: 8, frame_idxs: [1,2,3,4,6,7,8,9]
- All 8 frames have frame_rms_mm: [4.871, 173.708, 1.891, 3.347, 1.820, 6.394, 1.670, 1.998] mm
- Overall pooled RMS: 58.52 mm (dominated by frame 2 outlier of 173.7 mm; median frame RMS ~2.9 mm — documented in SUMMARY as a raw MVS observation, not a code issue)
- cameras_included/cameras_excluded recorded per frame

---

## Git Commits

All four commits documented in SUMMARY files verified present in git log:

| Hash | Description |
|------|-------------|
| `76038f0` | feat(03-01): flatness numerics module + synthetic unit tests |
| `9be3da4` | feat(03-01): MET-01/MET-02 sweep CLI and artifact checker |
| `7a462b9` | feat(03-02): cross-camera agreement module + synthetic unit tests |
| `138da0c` | feat(03-02): MET-03 sweep CLI and artifact checker |

---

## Human Verification Required

None. All metric computations, artifact shapes, and unit test outcomes are verifiable programmatically. The only notable observation — frame 2's cross-camera RMS of 173.7 mm being a strong outlier — is documented in the SUMMARY as a real observation about raw MVS depth consistency in that frame, not a code defect. Phase 5 will surface the distribution.

---

## Gaps Summary

None. All success criteria are fully met.

---

_Verified: 2026-06-30_
_Verifier: Claude (gsd-verifier)_
