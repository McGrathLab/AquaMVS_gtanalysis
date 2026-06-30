---
phase: 04-scale-check-alignment
plan: 01
subsystem: metrics
tags: [umeyama, kabsch, alignment, scale, rmse, charuco, met-04, met-05, numpy]

# Dependency graph
requires:
  - phase: 03-scale-independent-metrics
    provides: "corners.npz (cleaned Z>0-gated consensus corners); locked Phase 3 artifacts (flatness_consistency.json, cross_camera_agreement.json) that the ordering invariant guards against"
  - phase: 02-corner-transfer
    provides: "corners.npz transferred ChArUco corners in MVS world metres"
provides:
  - "analysis/alignment.py: closed-form Umeyama/Kabsch fit (with/without scale), rigid_inlier_fit (MET-05 outlier rejection + refit), consensus-corner builder, ideal-board accessor, matched-array builder"
  - "analysis/compute_scale_alignment.py: MET-04/MET-05 CLI writing data/analysis_output/scale_alignment.json + schema sidecar, with runtime ordering-invariant guard and embedded circularity+Maas note"
  - "data/analysis_output/scale_alignment.json: per-frame + pooled rigid inlier RMSE, scale factor/%, board size, honest-framing note"
  - "tests/check_ordering_invariant.py: byte-identical proof that Phase 3 artifacts survive a Phase 4 run"
affects: [05-manuscript-deliverables, results-table, methods-paragraph, entrypoint-regeneration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Closed-form similarity alignment with known corner_id correspondence (no ICP)"
    - "Runtime ordering-invariant guard: assert Phase 3 artifacts exist + computed_before_alignment before computing; write only to a separate path"
    - "Pooled RMSE from accumulated inlier squared residuals (not mean-of-frame-means)"

key-files:
  created:
    - analysis/alignment.py
    - analysis/compute_scale_alignment.py
    - tests/test_alignment.py
    - tests/check_scale_alignment_artifact.py
    - tests/check_ordering_invariant.py
  modified: []

key-decisions:
  - "Outlier rule for MET-05: keep corners with residual <= max(5.0 mm abs floor, median + 3*MAD), then refit rigid on inliers; documented in artifact outlier_rule block"
  - "MET-04 reported via two estimators on the SAME inlier set: Umeyama-with-scale factor (+%) and median inter-corner spacing (board_size_mm)"
  - "Pooled rigid RMSE accumulated from inlier squared residuals across frames (mirrors Phase 3 pooling), not a mean of per-frame RMS"
  - "icp_align cross-check intentionally NOT used: corner_id correspondence is known, so closed-form Umeyama is exact and avoids correspondence ambiguity"
  - "OUT-05 one-command entrypoint regeneration deferred to Phase 5; analysis/entrypoint.py untouched"

patterns-established:
  - "Phase 4 numerics are dataset-free + write-nothing; persistence and the ordering guard live in the compute CLI"
  - "Honest-framing machine-readable note block (circularity_caveat + maas_2015_context) ships inside the artifact"

requirements-completed: [MET-04, MET-05]

# Metrics
duration: 6min
completed: 2026-06-30
---

# Phase 4 Plan 01: Scale Check & Alignment Summary

**Closed-form Umeyama alignment of consensus MVS corners to the ideal 60 mm board — pooled rigid inlier RMSE 1.055 mm (MET-05) and scale factor mean 1.00040 / +0.040% with size mean 60.013 mm (MET-04) — reported as an honest, Maas-framed consistency check that provably never touches the locked Phase 3 artifacts.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-06-30T17:00:23Z
- **Completed:** 2026-06-30T17:06:00Z
- **Tasks:** 3
- **Files modified:** 5 created

## Headline Phase 4 Numbers

**MET-05 — Rigid (no-scale) inlier RMSE:**

| Frame | Corners | Inliers | Rigid RMSE (mm) | Scale factor | Scale err % | Size (mm) |
|------:|--------:|--------:|----------------:|-------------:|------------:|----------:|
| 1 | 88 | 85 | 1.013 | 1.00153 | +0.153 | 60.132 |
| 2 | 80 | 80 | 0.825 | 0.99879 | -0.121 | 59.898 |
| 3 | 88 | 88 | 0.808 | 0.99994 | -0.006 | 59.987 |
| 4 | 83 | 81 | 1.614 | 1.00390 | +0.390 | 60.151 |
| 6 | 88 | 88 | 0.657 | 0.99925 | -0.075 | 59.939 |
| 7 | 86 | 83 | 1.027 | 1.00195 | +0.195 | 60.105 |
| 8 | 85 | 85 | 1.040 | 0.99847 | -0.153 | 59.930 |
| 9 | 77 | 77 | 1.217 | 0.99938 | -0.062 | 59.961 |

**Pooled (MET-05):** rigid inlier RMSE = **1.055 mm** (667 inlier residuals across 8 frames).
**Pooled (MET-04):** scale factor mean = **1.00040** (error mean **+0.040%**, range -0.153% .. +0.390%); reconstructed board size mean = **60.013 mm**.

These pair with the locked Phase 3 headline (flatness pooled 1.09 mm, cross-camera pooled 3.46 mm).

## Outlier Rule Used

`max(abs_thresh_mm=5.0, median + mad_k=3.0 * MAD)`, min_inliers=3, then rigid refit on the inlier subset. Five of eight frames kept all corners; frames 1/4/7 dropped 2-3 corners each. The rule is serialized into `scale_alignment.json` under `outlier_rule`.

## Ordering Invariant — HELD

`tests/check_ordering_invariant.py` sha256'd both Phase 3 artifacts, ran `compute_scale_alignment.py` via subprocess (exit 0), and confirmed both hashes are **byte-identical before/after** the run. `scale_alignment.json` lands on `data/analysis_output/` (the separate path), never inside `scale_independent_metrics/`. The compute CLI additionally refuses to run (exit 1) if either Phase 3 artifact is missing or lacks `computed_before_alignment: true`. `analysis/entrypoint.py` was not modified.

## Task Commits

1. **Task 1: Closed-form alignment numeric core + synthetic tests** - `e2aa134` (feat)
2. **Task 2: MET-04/MET-05 compute CLI + artifact + checker** - `16f346a` (feat)
3. **Task 3: Ordering-invariant proof** - `ab66e74` (test)

_Note: data/ is gitignored; scale_alignment.json exists on disk but is not committed (only code is versioned)._

## Files Created/Modified
- `analysis/alignment.py` - umeyama_fit, rigid_inlier_fit, build_consensus_corners, ideal_board_corners, matched_arrays (write-nothing numeric core)
- `analysis/compute_scale_alignment.py` - MET-04/MET-05 CLI: aligns consensus corners to ideal board, ordering-invariant guard, JSON + schema, circularity+Maas note, stdout table
- `tests/test_alignment.py` - exact R/t/s recovery, rigid recovery, 50 mm outlier rejection, scale-error sign, degenerate guard
- `tests/check_scale_alignment_artifact.py` - per-frame + pooled shape checks, finite bounds, note block, no "0.5 %" misread
- `tests/check_ordering_invariant.py` - byte-identical Phase 3 proof + separate-path assertion

## Decisions Made
- **MET-05 outlier rule:** combined absolute 5 mm floor with robust median+3*MAD cutoff so a tight cluster is never over-pruned while gross outliers are rejected; refit rigid on inliers.
- **MET-04 dual estimator:** Umeyama-with-scale factor and median inter-corner spacing, both on the SAME inlier set used by MET-05 for internal consistency.
- **No icp_align cross-check:** corner_id correspondence is known one-to-one, so closed-form Umeyama is exact and avoids ICP correspondence ambiguity. The optional ICP path was deliberately skipped.
- **Pooled RMSE pooling:** accumulated inlier squared residuals across frames (mirrors Phase 3), not mean-of-frame-means.

## Deviations from Plan

None - plan executed exactly as written. The ordering-invariant guard, banned-substring check, and circularity+Maas framing were all implemented as specified; all five tests/checkers exit 0 in the AquaMVS env.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- MET-04/MET-05 numbers are computed and persisted, completing the results-table inputs (rigid RMSE + scale factor + board size) alongside the Phase 3 scale-independent headline.
- **OUT-05 explicitly deferred to Phase 5:** one-command regeneration (`--run-metrics` / `run_pipeline`) and the single-entrypoint wiring of all compute mains were intentionally left out of Phase 4; `analysis/entrypoint.py` is untouched. Phase 5 will own that deliverable and wire the real compute signatures (note `compute_cross_camera.main` takes NO data_root).
- Phase 5 can now assemble the results table, spatial-consistency figure, per-camera output, and methods paragraph (circularity + Maas factor-of-two framing already machine-readable in the note block).

## Self-Check: PASSED

All 5 created files exist on disk (plus the gitignored scale_alignment.json artifact); all 3 task commits (e2aa134, 16f346a, ab66e74) are present in git history.

---
*Phase: 04-scale-check-alignment*
*Completed: 2026-06-30*
