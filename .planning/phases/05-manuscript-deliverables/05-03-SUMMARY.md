---
phase: 05-manuscript-deliverables
plan: 03
subsystem: analysis
tags: [python, markdown, manuscript, methods, entrypoint, reproducibility]

requires:
  - phase: 05-01
    provides: analysis/deliverables subpackage (_artifacts.py, make_table, make_per_camera)
  - phase: 05-02
    provides: fig_spatial_consistency.py, fig_range_lateral.py (callable main())
  - phase: 04-scale-check-alignment
    provides: scale_alignment.json (MET-04/05), error_decomposition.json (MET-06)
  - phase: 03-scale-independent-metrics
    provides: flatness_consistency.json (MET-01/02), cross_camera_agreement.json (MET-03)

provides:
  - analysis/deliverables/make_methods.py — OUT-04 generator reading artifact values at runtime
  - results/methods.md — OUT-04 manuscript-ready methods paragraph (88 lines, 3 citations)
  - analysis/run_all.py — OUT-05 single reproducible entrypoint (5 compute stages + 5 deliverable generators)

affects: []

tech-stack:
  added: []
  patterns:
    - Banned-string guard (_check_banned) applied to methods prose before write_text
    - Artifact-driven prose: every cited number read from JSON artifact at runtime (no literals)
    - Subprocess orchestration for compute stages (inherit stdout/stderr, check returncode)
    - Direct-import call for deliverable generators (main() with no args)
    - sys.path.insert(0, str(_REPO_ROOT)) in run_all.py mirrors entrypoint.py pattern

key-files:
  created:
    - analysis/deliverables/make_methods.py
    - results/methods.md
    - analysis/run_all.py
  modified: []

key-decisions:
  - "Maas (2015) benchmark framed exclusively as 'factor of two' in methods prose — '0.5 %' never appears; banned-string guard raises ValueError on write if any banned string present"
  - "Artifact-driven prose: all headline numbers (flatness, cross-camera RMS, range_dominance, scale_error_pct, dropout_rate) read from JSON via _artifacts loaders; no literals that could drift"
  - "run_all.py uses subprocess for compute stages (cleaner stage isolation, correct stdout, returncode gate) and direct import for deliverable generators (already idempotent main() functions)"
  - "Scale result framed as 'partly circular consistency check' in both prose and run_all.py summary line — never presented as the headline accuracy number"
  - "entrypoint.py (DATA-04 smoke-test) left completely untouched; run_all.py is a new file"

patterns-established:
  - "Manuscript prose generator pattern: load artifacts -> compose f-string text -> _check_banned -> write_text"
  - "Pipeline entrypoint pattern: repo-root sys.path insertion + subprocess stage runner + direct-import deliverable caller + file-by-file summary with headline metrics"

requirements-completed: [OUT-04, OUT-05]

duration: 12min
completed: 2026-06-30
---

# Phase 5 Plan 03: Methods Paragraph and Single Entrypoint Summary

**OUT-04 manuscript methods paragraph (88 lines, artifact-driven numbers, 3 citations, refraction/circularity framing) and OUT-05 single reproducible entrypoint regenerating all 18 artifacts + deliverables in dependency order from one command — final plan of the final phase.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-30T17:50:28Z
- **Completed:** 2026-06-30T18:03:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Created `analysis/deliverables/make_methods.py`: reads flatness RMS, cross-camera RMS, scale error %, board size, range dominance, lateral RMS, and dropout rate from on-disk JSON artifacts at runtime; composes 88-line manuscript-ready prose covering the 12x9 ChArUco target, 2-of-10 calibration overlap exclusion (8 held-out frames), `cast_ray` corner transfer, scale-independent metrics as the headline, scale as a partly-circular consistency check, range-dominated residual (4.41x) as refraction signature, and Maas (2015) factor-of-two benchmark; asserts "0.5 %", "58.5", "173.7" absent before writing.
- Created `analysis/run_all.py`: single command regenerates all 18 output files deterministically in dependency order (5 compute stages via subprocess, 5 deliverable generators via direct import); `--skip-metrics` flag for fast iteration; prints file-by-file EXISTS/size summary and headline metric recap from artifacts; safe to re-run.
- Verified full end-to-end pipeline run exits 0 and all 18 files present; `analysis/entrypoint.py` DATA-04 smoke-test confirmed still passing.

## Task Commits

1. **Task 1: Methods paragraph generator (OUT-04)** - `5adf6ed` (feat)
2. **Task 2: Single reproducible entrypoint run_all.py (OUT-05)** - `2283fbe` (feat)

## Files Created/Modified

- `analysis/deliverables/make_methods.py` - OUT-04 generator; loads 5 artifact JSONs, composes academic prose, banned-string guard, writes results/methods.md
- `results/methods.md` - OUT-04 drafted methods paragraph: 88 lines covering target/overlap/transfer/SI-metrics/scale-circularity/refraction-signature/Maas-benchmark
- `analysis/run_all.py` - OUT-05 entrypoint; subprocess pipeline (stages 1-5) + import deliverables (5 generators) + file-by-file summary

## Methods Paragraph Content

The `results/methods.md` prose covers:
1. **Target geometry**: 12x9 ChArUco board, DICT_5X5_100, 60 mm squares `[@deJesus2015; @MennaNocerino2019]`
2. **Frame selection**: 2-of-10 overlap measured and excluded (output indices 0 and 5 = raw 0, 3930); 8 genuinely held-out frames
3. **Corner transfer**: `RefractiveProjectionModel.cast_ray`, measured dropout 0.2%
4. **Scale-independent metrics**: flatness 1.09 mm, size CV 0.0016, cross-camera 3.46 mm — computed/locked before alignment
5. **Scale as consistency check**: +0.040% scale error / 60.013 mm recovered — explicitly framed as partly circular
6. **Refraction signature**: range dominance 4.41x (range 3.64 mm vs lateral 0.82 mm)
7. **Maas benchmark**: factor of two `[@Maas2015]` — never "0.5 %"

## run_all.py Stage Order

| Stage | Module | Outputs |
|-------|--------|---------|
| 1/5 | `analysis.transfer_corners` | corners.npz, dropout_report.json |
| 2/5 | `analysis.compute_flatness_consistency` | flatness_consistency.json |
| 3/5 | `analysis.compute_cross_camera` | cross_camera_agreement.json |
| 4/5 | `analysis.compute_scale_alignment` | scale_alignment.json (guards on stage 2+3) |
| 5/5 | `analysis.compute_error_decomposition` | error_decomposition.json |
| D1 | `make_table.main()` | results/table.{md,tex,csv} |
| D2 | `make_per_camera.main()` | results/per_camera_agreement.{md,csv} |
| D3 | `make_methods.main()` | results/methods.md |
| D4 | `fig_spatial_consistency.main()` | figures/spatial_consistency.{svg,pdf,png} |
| D5 | `fig_range_lateral.main()` | figures/range_vs_lateral.{svg,pdf,png} |

## Decisions Made

- **Subprocess for compute stages, direct import for deliverables**: subprocess gives correct stdout inheritance and clean stage isolation; direct import is simpler for the no-arg generator `main()` functions and avoids spawning extra processes.
- **Artifact-driven prose**: all metric values in methods.md read from JSON via `_artifacts` loaders so the prose can never drift from the computed values. Only the surrounding explanatory text is literal.
- **Banned-string guard in make_methods.py**: `_check_banned()` raises `ValueError` before `write_text()` if "0.5 %", "58.5", or "173.7" appears, matching the pattern established in make_table.py.
- **"factor of two" not "0.5 %"**: the Maas (2015) benchmark is described as a factor-of-two refractive precision penalty throughout — this is the correct characterisation and avoids the banned percentage form.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Entrypoint Smoke-Test

`analysis/entrypoint.py` (DATA-04 loader smoke-test) confirmed passing after all changes:
```
=== SMOKE TEST PASSED ===
```
The file was not modified at any point in this plan.

## Phase Completion

This is the final plan (05-03) of the final phase (05-manuscript-deliverables). All OUT deliverables are now present:

| Deliverable | File | Status |
|-------------|------|--------|
| OUT-01 | results/table.{md,tex,csv} | Complete (05-01) |
| OUT-02 | data/analysis_output/figures/spatial_consistency.{svg,pdf,png} | Complete (05-02) |
| OUT-03 | results/per_camera_agreement.{md,csv} | Complete (05-01) |
| OUT-04 | results/methods.md | Complete (this plan) |
| OUT-05 | analysis/run_all.py | Complete (this plan) |

The entire AquaMVS ground-truth validation pipeline is now reproducible from a single command:
```
conda run -n AquaMVS python analysis/run_all.py
```

## Self-Check: PASSED

- `analysis/deliverables/make_methods.py` — FOUND
- `results/methods.md` — FOUND (5,711 bytes, 88 lines)
- `analysis/run_all.py` — FOUND
- Commit 5adf6ed — VERIFIED (feat(05-03): methods paragraph generator)
- Commit 2283fbe — VERIFIED (feat(05-03): single reproducible entrypoint)
- All 18 output files verified via scratch_verify_runall.py — RUNALL OK
- entrypoint.py smoke-test — SMOKE TEST PASSED

---
*Phase: 05-manuscript-deliverables*
*Completed: 2026-06-30*
