# Phase 1: Data & Environment - Context

**Gathered:** 2026-06-30
**Status:** Ready for planning

*Captured in auto mode. Phase 1 is pure infrastructure; the substantive choices were already locked during project initialization (PROJECT.md / REQUIREMENTS.md). This file records those locked decisions plus sensible defaults so the researcher/planner need not re-ask.*

<domain>
## Phase Boundary

Stand up a reproducible analysis environment with the input dataset extracted locally and loadable through a single documented entrypoint. Delivers DATA-01..04: extraction + verification, calibration/depth/cloud loading, held-out frame resolution, and a runnable entrypoint in the `AquaMVS` conda env. **Corner detection, metrics, and figures are later phases** — Phase 1 only makes the data accessible and trustworthy.

</domain>

<decisions>
## Implementation Decisions

### Data extraction & verification (DATA-01)
- Extract the source zip (`C:\Users\tucke\Downloads\aquamvs_ground_truth_analysis.zip`, ~9 GB) into the repo at `./data/` — extracted root will be `./data/aquamvs_ground_truth_analysis/`.
- `./data/` is gitignored (large binaries never enter version control).
- **Verify extraction completeness before deleting the source zip.** Verification = a manifest check, not just "no error": confirm `calibration.json`, `config.yaml`, all 10 `output/frame_0000NN/` dirs, and per-frame `depth_maps/*.npz` (12 cameras each), `point_cloud/fused.ply`, and `mesh/surface.ply` are present and non-zero. Only on a passing manifest is the Downloads zip deleted.
- The deletion is a deliberate, logged step — if verification fails, leave the zip in place and report.

### Loading interface (DATA-02)
- Provide a loader that returns, on demand: calibration (camera intrinsics/extrinsics, the refractive `interface` params, and the board spec — 12×9, 60 mm squares, DICT_5X5_100), per-camera/per-frame depth maps (the `.npz` arrays), undistorted images, and fused clouds.
- Load lazily / by reference where possible — `fused.ply` is ~650 MB per frame, so the loader should hand back paths or memory-mapped handles rather than eagerly reading every cloud.
- The data root is **configurable** (a small config value), defaulting to `./data/aquamvs_ground_truth_analysis/`, so the analysis isn't hardcoded to one machine.

### Held-out frame resolution (DATA-03)
- The default validation set is the **8 held-out frames**: output indices 1, 2, 3, 4, 6, 7, 8, 9 (raw frames 786, 1572, 2358, 3144, 4716, 5502, 6288, 7074).
- Output indices **0 and 5** (raw frames 0 and 3930) are **excluded** from the default set but remain loadable (retained on disk) — the loader flags them as calibration-overlap frames, never silently drops them.

### Entrypoint & environment (DATA-04)
- A single documented entrypoint runs in the `AquaMVS` conda env with `aquamvs` v1.5.2 importable.
- Invocation pattern: `conda run -n AquaMVS python <entrypoint>` (conda is not on PATH; full path is `C:\Users\tucke\anaconda3\Scripts\conda.exe`). Avoid multi-line `python -c` under `conda run` — it errors; use script files.

### Camera without depth map
- Camera `e3v8250` has raw frames but **no depth-map `.npz`** (12 of 13 cameras have depth). Treat it as a likely witness/reference view: present in calibration and frames, but excluded from depth-based steps. The loader must handle "camera present in calibration but no depth map" without crashing. Confirm its intended role while planning (already flagged in STATE.md).

### Claude's Discretion
- Package/module naming and internal layout of the analysis code.
- Exact loader API shape (functions vs dataclasses) and config file format (YAML/JSON/py).
- Logging/progress style for the extraction + verification step.
- Whether depth maps are returned as arrays vs lazy handles per call site.

</decisions>

<specifics>
## Specific Ideas

- Reuse `aquamvs` calibration/IO utilities rather than re-parsing `calibration.json` by hand where a loader already exists in the package — confirm against the live tree during planning.
- The extracted layout mirrors the zip exactly (see PROJECT.md "Context" for the confirmed structure), so the loader can rely on that fixed directory shape.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (Corner detection, metrics, figures, and the methods paragraph are already scoped to Phases 2–5.)

</deferred>

---

*Phase: 01-data-environment*
*Context gathered: 2026-06-30*
