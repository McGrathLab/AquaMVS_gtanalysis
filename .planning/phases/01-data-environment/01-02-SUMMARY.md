---
phase: 01-data-environment
plan: "02"
subsystem: data
tags: [python, loader, calibration, aquamvs, dataset, lazy-loading]

# Dependency graph
requires:
  - "data/aquamvs_ground_truth_analysis/ extracted and manifest-verified (from 01-01)"
provides:
  - "analysis/loader.py: GroundTruthDataset class with lazy calibration, board spec, frame metadata, depth maps, fused cloud paths"
  - "analysis/__init__.py: package marker"
  - "analysis/entrypoint.py: smoke-test entrypoint (SMOKE TEST PASSED)"
  - "scripts/verify_loader.py: assertion-based verification gate"
affects: [02-analysis, 03-metrics, 04-scale, 05-reporting]

# Tech tracking
tech-stack:
  added:
    - "aquamvs.calibration.load_calibration_data (v1.5.2) — camera + interface params"
  patterns:
    - "Lazy loading with instance-level caching (_calib_cache, _board_spec_cache)"
    - "Optional[Path] / Optional[np.ndarray] return pattern for unavailable data (no exceptions)"
    - "frozenset constants for immutable exclusion sets (CALIBRATION_OVERLAP_INDICES, NO_DEPTH_CAMERAS)"
    - "All dataclasses frozen=True for safe sharing across modules"

key-files:
  created:
    - analysis/__init__.py
    - analysis/loader.py
    - analysis/entrypoint.py
    - scripts/verify_loader.py
  modified: []

key-decisions:
  - "Board JSON key is 'dictionary' (not 'dict_name'); BoardSpec.dict_name maps to calibration.json['board']['dictionary']"
  - "load_calibration_data exposes water_z even though it is absent from JSON interface dict (derived internally by aquamvs)"
  - "npz depth arrays use key 'depth'; 'confidence' array also present but not loaded by default"
  - "e3v8250 confirmed as auxiliary fisheye witness view (is_auxiliary=True, is_fisheye=True) — no depth map, returns None gracefully"
  - "Fused clouds are ~586-592 MB each; loader returns Path only, never loads eagerly"

# Metrics
duration: 3min
completed: 2026-06-30
---

# Phase 01 Plan 02: Dataset Loader Module Summary

**GroundTruthDataset loader implemented in analysis/loader.py: lazy-cached calibration (13 cameras via aquamvs v1.5.2), board spec from JSON, 8/10 frame split with calibration-overlap flagging, None-safe depth map access for e3v8250, and lazy fused cloud paths — smoke test passed**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-06-30T15:05:05Z
- **Completed:** 2026-06-30T15:08:22Z
- **Tasks:** 2 of 2
- **Files created:** 4

## Accomplishments

- `analysis/loader.py` — `GroundTruthDataset` with full interface per plan spec
- `analysis/__init__.py` — package marker
- `analysis/entrypoint.py` — structured dataset summary + smoke-test gate (SMOKE TEST PASSED)
- `scripts/verify_loader.py` — 8-assertion verification script, all pass
- Confirmed: 13 cameras, 12 ring + 1 auxiliary fisheye (e3v8250), BoardSpec(12, 9, 0.06 m, 0.045 m, DICT_5X5_100)
- Confirmed: 8 validation frames at output indices [1,2,3,4,6,7,8,9]; indices 0 and 5 loadable but flagged
- Confirmed: e3v8250 returns None for all depth-map calls, no exception
- Confirmed: fused cloud paths are ~586-592 MB, returned as Path objects only

## Task Commits

1. **Task 1: analysis/__init__.py, analysis/loader.py, scripts/verify_loader.py** — `5f15605`
2. **Task 2: analysis/entrypoint.py** — `9533df7`

## Actual calibration.json Board Spec Keys

```json
"board": {
  "squares_x": 12,
  "squares_y": 9,
  "square_size": 0.06,
  "marker_size": 0.045,
  "dictionary": "DICT_5X5_100"
}
```

Note: JSON key is `dictionary`, not `dict_name`. BoardSpec dataclass exposes it as `dict_name`.

## Actual Camera Names

Ring cameras (12): e3v829d, e3v82e0, e3v82f9, e3v831e, e3v832e, e3v8334, e3v83e9, e3v83eb, e3v83ee, e3v83ef, e3v83f0, e3v83f1

Auxiliary (1): e3v8250 — is_auxiliary=True, is_fisheye=True (witness fisheye view, no depth map)

## aquamvs Version

v1.5.2 (confirmed by `import aquamvs; aquamvs.__version__`)

## npz Structure

Each `depth_maps/<cam>.npz` contains:
- `depth`: float32 array, shape (1200, 1600)
- `confidence`: float32 array, shape (1200, 1600)

`load_depth_map()` returns `arr['depth']`.

## Deviations from Plan

**1. [Inspection finding] JSON board key is `dictionary`, not `dict_name`**
- Plan noted "inspect actual keys during execution" — the actual key is `dictionary`
- BoardSpec dataclass continues to use `dict_name` as the field name for clarity
- No code deviation needed; loader correctly reads `board["dictionary"]`

**2. [Inspection finding] `water_z` not in JSON interface dict**
- The JSON `interface` section only has `normal`, `n_air`, `n_water`
- `water_z=1.030555` is derived by `load_calibration_data` internally (not hand-parsed)
- Consistent with plan's instruction to use `load_calibration_data` for camera/interface params

No logic deviations — plan executed as written with JSON key names verified.

## Self-Check: PASSED

Files confirmed:
- analysis/__init__.py: EXISTS
- analysis/loader.py: EXISTS
- analysis/entrypoint.py: EXISTS
- scripts/verify_loader.py: EXISTS

Commits confirmed:
- 5f15605: feat(01-02): implement GroundTruthDataset loader module
- 9533df7: feat(01-02): add analysis/entrypoint.py with dataset summary and smoke test

All assertions in scripts/verify_loader.py passed. Entrypoint prints SMOKE TEST PASSED.

---
*Phase: 01-data-environment*
*Completed: 2026-06-30*
