---
gsd_state_version: 1.0
milestone: v1.5
milestone_name: milestone
status: unknown
last_updated: "2026-06-30T15:13:11.921Z"
progress:
  total_phases: 1
  completed_phases: 1
  total_plans: 2
  completed_plans: 2
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-30)

**Core value:** Produce defensible, non-circular accuracy numbers for the AquaMVS dense stage — led by flatness and spatial/angular consistency — that hold up in the manuscript.
**Current focus:** Phase 1 — Data & Environment

## Current Position

Phase: 2 of 5 (Corner Transfer)
Plan: 1 of 3 in current phase (02-01 complete)
Status: In Progress
Last activity: 2026-06-30 — 02-01 complete: charuco_detect.py + detect_corners.py, XFER-01 PASSED (2611 corners, 75/96 pairs)

Progress: [███░░░░░░░] ~20%

## Performance Metrics

**Velocity:**
- Total plans completed: 3
- Average duration: 7 min
- Total execution time: 0.35 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-data-environment | 2/2 | 11 min | 5.5 min |
| 02-corner-transfer | 1/3 | 10 min | 10 min |

**Recent Trend:**
- Last 5 plans: 8 min, 3 min, 10 min
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

### Key Decisions (Phase 02)

- [Phase 02-01]: Detect on UNDISTORTED images only so pixel (u,v) matches depth-map grid
- [Phase 02-01]: No dist_coeffs passed to detect_charuco; CharucoDetector handles subpixel refinement internally on undistorted images
- [Phase 02-01]: Results keyed by (frame.output_idx, camera) for direct consumption by Plan 02-02

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- Camera `e3v8250` RESOLVED: confirmed as auxiliary fisheye witness view (is_auxiliary=True, is_fisheye=True); no depth map by design.
- Plane-fit fallback (XFER-03) and pure-cloud fallback are backups; confirm depth-based corner transfer works on real data before relying on fallbacks.

## Session Continuity

Last session: 2026-06-30
Stopped at: Completed 02-01-PLAN.md: analysis/charuco_detect.py + detect_corners.py implemented; XFER-01 PASSED (2611 corners, 75/96 pairs)
Resume file: None
