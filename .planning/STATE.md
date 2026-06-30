---
gsd_state_version: 1.0
milestone: v1.5
milestone_name: milestone
status: unknown
last_updated: "2026-06-30T16:24:14.860Z"
progress:
  total_phases: 3
  completed_phases: 3
  total_plans: 6
  completed_plans: 6
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-30)

**Core value:** Produce defensible, non-circular accuracy numbers for the AquaMVS dense stage — led by flatness and spatial/angular consistency — that hold up in the manuscript.
**Current focus:** Phase 1 — Data & Environment

## Current Position

Phase: 3 of 5 (Scale-Independent Metrics)
Plan: 2 of 2 in current phase (03-01 and 03-02 complete)
Status: Phase 3 Complete (+ post-hoc fix) — ready for Phase 4
Last activity: 2026-06-30 — Phase 3 metrics corrected. Root-caused the frame-2 cross-camera outlier to 4 non-physical (Z<0, behind-interface) plane-fit-fallback corners from a degenerate seed plane (camera e3v83e9). Hardened Phase 2 transfer (intersect_ray_plane rejects t<=0; world-Z physical band) + added defensive Z>0 gates in the metric loaders. Re-ran transfer + both metrics. CORRECTED HEADLINE: MET-01 flatness pooled=1.093mm; MET-02 size mean=60.01mm CV=0.0015 (tilt 2.8-55.5°); MET-03 cross-camera pooled=3.46mm (was 58.5), per-frame 1.67-6.39mm, frame-2 173.7->2.0mm. plane_fit 10->6, 4 now unrecovered. 14 tests pass. corners.npz regenerated clean (2605).

Progress: [██████░░░░] ~60%

## Performance Metrics

**Velocity:**
- Total plans completed: 3
- Average duration: 7 min
- Total execution time: 0.35 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-data-environment | 2/2 | 11 min | 5.5 min |
| 02-corner-transfer | 3/3 | 55 min | 18 min |
| 03-scale-independent-metrics | 2/2 | 14 min | 7 min |

**Recent Trend:**
- Last 5 plans: 8 min, 3 min, 10 min, 8 min, 6 min
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
Stopped at: Completed 03-01-PLAN.md: flatness.py + compute_flatness_consistency.py; MET-01 pooled RMS=1.09mm, MET-02 size CV=0.0015; flatness_consistency.json persisted; Phase 3 complete
Resume file: None
