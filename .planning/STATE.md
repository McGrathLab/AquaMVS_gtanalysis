---
gsd_state_version: 1.0
milestone: v1.5
milestone_name: milestone
status: in_progress
last_updated: "2026-06-30T17:52:00.000Z"
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 10
  completed_plans: 8
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-30)

**Core value:** Produce defensible, non-circular accuracy numbers for the AquaMVS dense stage — led by flatness and spatial/angular consistency — that hold up in the manuscript.
**Current focus:** Phase 5 — Manuscript Deliverables

## Current Position

Phase: 5 of 5 (Manuscript Deliverables)
Plan: 1 of 3 in current phase (05-01 complete)
Status: Phase 5 in progress — 05-01 complete (deliverables subpackage + OUT-01 table + OUT-03 per-camera)
MET-06 addition (user-requested, 2026-06-30): error-direction decomposition. analysis/error_decomposition.py + compute_error_decomposition.py → data/analysis_output/error_decomposition.json. RANGE-vs-LATERAL (camera/refraction frame, cross-camera offset projected onto in-water cast_ray): pooled range_dominance=4.41 (range 3.64mm vs lateral 0.82mm; range-dominated every frame 3.16-4.89x = REFRACTIVE SIGNATURE). Board-frame (MET-05 rigid residuals): out-of-plane 0.79mm vs in-plane 0.70mm. 25 tests pass. Phase 5 must add: a results-table row, a range-vs-lateral figure, and a methods sentence ("residual error is range-dominated, consistent with refraction").
Last activity: 2026-06-30 — Phase 4 scale/alignment consistency check shipped. Closed-form Umeyama (analysis/alignment.py) aligns per-frame consensus MVS corners to the ideal 60mm board with known corner_id correspondence (no ICP). MET-05 pooled rigid inlier RMSE=1.055mm (per-frame 0.66-1.61mm, 667 inliers/8 frames; outlier rule max(5mm, median+3*MAD)). MET-04 scale factor mean=1.00040 (+0.040%, range -0.153..+0.390%), board size mean=60.013mm — labeled a PARTLY CIRCULAR consistency check (60mm is the calibration anchor) framed against Maas (2015) factor-of-two. Ordering invariant PROVEN: Phase 3 JSON hashes byte-identical before/after (tests/check_ordering_invariant.py); scale_alignment.json on separate data/analysis_output path; compute refuses (exit 1) if Phase 3 absent. No "0.5 %" misread anywhere. entrypoint.py untouched (OUT-05 deferred to Phase 5). All 5 tests/checkers exit 0.

Progress: [████████░░] ~85%

## Performance Metrics

**Velocity:**
- Total plans completed: 7
- Average duration: 7 min
- Total execution time: 0.45 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-data-environment | 2/2 | 11 min | 5.5 min |
| 02-corner-transfer | 3/3 | 55 min | 18 min |
| 03-scale-independent-metrics | 2/2 | 14 min | 7 min |
| 04-scale-check-alignment | 1/1 | 6 min | 6 min |
| 05-manuscript-deliverables | 1/3 | 18 min | 18 min |

**Recent Trend:**
- Last 5 plans: 3 min, 10 min, 8 min, 6 min, 6 min
- Trend: baseline

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Assembly of existing `aquamvs` v1.5.2 hooks + corner-transfer glue; no new reconstruction code.
- Non-circularity is structural: scale-independent metrics (Phase 3) computed and locked before the scale check (Phase 4).
- Validate on the 8 held-out frames; exclude output indices 0 and 5 (raw 0, 3930) from all metrics.
- [Phase 01]: Extraction script is stdlib-only so it can run outside the AquaMVS conda env
- [Phase 01]: Zip deleted only after passing 172-item manifest check; retained on failure with exit code 1
- [Phase 01]: verify_dataset.py kept as flat assertions for use as CI-style gate in future plans
- [Phase 01]: Board JSON key is 'dictionary' (not 'dict_name'); mapped to BoardSpec.dict_name in loader
- [Phase 01]: e3v8250 confirmed as auxiliary fisheye witness view — no depth map, handled with None return
- [Phase 01]: Fused clouds returned as lazy Path objects only (~590 MB each); never loaded by loader
- [Phase 03-02]: Coverage threshold default=6 corners/frame; below-threshold cameras recorded as excluded (not errors); board-blind cameras (0 rows) absent from coverage — non-event
- [Phase 03-02]: Overall MET-03 RMS uses pooled per-corner residuals across all frames (not mean-of-frame-means) to preserve distribution shape for Phase 5
- [Phase 03-01]: board_size_from_corners uses median adjacent-pair 3D spacing (not fitted extent) as MET-02 consistency measure; docstring flags this as variation, not absolute accuracy (MET-04 is Phase 4)
- [Phase 03-01]: depth_m defined as centroid projection onto calib.interface_normal for cross-frame comparability; seed plane for slab crop from corner fit_board_plane (no PnP re-detection)
- [Phase 03-01]: data/ gitignored by design; flatness_consistency.json exists on disk but not committed; only code is versioned

### Key Decisions (Phase 02)

- [Phase 02-01]: Detect on UNDISTORTED images only so pixel (u,v) matches depth-map grid
- [Phase 02-01]: No dist_coeffs passed to detect_charuco; CharucoDetector handles subpixel refinement internally on undistorted images
- [Phase 02-01]: Results keyed by (frame.output_idx, camera) for direct consumption by Plan 02-02

### Key Decisions (Phase 04-01)

- [Phase 04-01]: Closed-form Umeyama/Kabsch used directly (no icp_align) — corner_id correspondence is known one-to-one, so the similarity fit is exact and avoids ICP correspondence ambiguity
- [Phase 04-01]: MET-05 outlier rule = keep residual <= max(5.0mm abs floor, median+3*MAD), then rigid refit on inliers; documented in artifact outlier_rule block. Pooled rigid RMSE accumulated from inlier squared residuals across frames (not mean-of-frame-means)
- [Phase 04-01]: MET-04 reported via two estimators on the SAME inlier set — Umeyama-with-scale factor (+%) and median inter-corner spacing (board_size_mm)
- [Phase 04-01]: Ordering invariant enforced at runtime AND proven by test — compute refuses (exit 1) if Phase 3 artifacts absent/not computed_before_alignment; scale_alignment.json on separate data/analysis_output path; Phase 3 JSON hashes byte-identical before/after; "0.5 %" misread banned and absent
- [Phase 04-01]: OUT-05 one-command regeneration (--run-metrics/run_pipeline) deferred to Phase 5; analysis/entrypoint.py untouched in Phase 4
- [Phase 05-01]: DissertationFigures made importable in AquaMVS env via editable install (pip install -e); _style.py also inserts src/ on sys.path as fallback for OUT-05 reproducibility
- [Phase 05-01]: Artifact paths anchored to repo root via Path(__file__).resolve() chain so generators run correctly from any cwd under conda run
- [Phase 05-01]: Banned strings (58.5, 173.7, 0.5 %) guarded programmatically at write time in both make_table.py and make_per_camera.py
- [Phase 05-01]: Per-camera exclusions framed as non-events (expected rig characteristic, not failure); "non-event" appears in per_camera_agreement.md intro prose

### Key Decisions (Phase 02-02)

- [Phase 02-02]: K_new (post-undistortion) used for projection models, NOT cam.K — corners and depth maps share the undistorted pixel grid
- [Phase 02-02]: NaN-mask channel sampled with padding_mode='border' to propagate NaN from bilinear neighbours (corners near depth holes treated as missing)
- [Phase 02-02]: Fused cloud loaded once per frame; passed as argument to transfer_frame_camera to avoid repeated 650 MB reloads
- [Phase 02-02]: Primary fallback plane fit from thin-slab (12 mm) crop of fused dense cloud via SVD; HEADLINE dropout = 0.4% (10/2611 corners plane_fit, 2 unrecovered)

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- Camera `e3v8250` RESOLVED: confirmed as auxiliary fisheye witness view (is_auxiliary=True, is_fisheye=True); no depth map by design.
- Plane-fit fallback (XFER-03) and pure-cloud fallback are backups; confirm depth-based corner transfer works on real data before relying on fallbacks.

## Session Continuity

Last session: 2026-06-30
Stopped at: Completed 05-01-PLAN.md: deliverables subpackage (_style.py, _artifacts.py, make_table.py, make_per_camera.py); OUT-01 results/table.{md,tex,csv} (6 metrics, SI vs circularity labels); OUT-03 results/per_camera_agreement.{md,csv} (non-event framing); DissertationFigures editable install in AquaMVS env
Resume file: None
