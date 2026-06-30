---
phase: 04-scale-check-alignment
verified: 2026-06-30T00:00:00Z
status: passed
score: 4/4 must-haves verified
re_verification: null
---

# Phase 4: Scale Check & Alignment Verification Report

**Phase Goal:** Absolute scale and rigid alignment reported honestly as consistency checks, run only after the scale-independent metrics are locked.
**Verified:** 2026-06-30
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Rigid (no-scale) alignment yields inlier RMSE per position (per-frame + pooled, with inlier counts) | ✓ VERIFIED | `scale_alignment.json` per_frame entries carry `rigid_rms_mm`, `n_inliers`, `n_corners` for frames {1,2,3,4,6,7,8,9}; pooled `rigid_rms_mm_pooled`=1.0545 from `n_inlier_residuals`=667. `rigid_inlier_fit` in alignment.py does no-scale Umeyama + MAD/abs outlier reject + refit. `test_alignment.py` PASS (5/5, incl. outlier rejection). |
| 2 | Reconstructed square size vs known 60 mm computed, labeled a consistency check with circularity stated | ✓ VERIFIED | `board_size_mm` per frame (59.90–60.15) + pooled mean 60.013; `scale_factor`/`scale_error_pct` present. `note.circularity_caveat` explicitly states the 60 mm square is the calibration scale anchor (input, not output) and near-zero scale error is "PARTLY CIRCULAR". artifact `metric` string labels it "(consistency check)". |
| 3 | Scale contextualized against Maas (2015) factor-of-two benchmark, NOT framed as "0.5 %" | ✓ VERIFIED | `note.maas_2015_context` states the "FACTOR OF TWO" refractive precision penalty (Maas 2015). Banned substrings "0.5 %" / "0.5%" appear NOWHERE in `scale_alignment.json` or its schema (grep count 0, before and after regeneration). |
| 4 | Steps run only after Phase 3; ordering invariant holds (Phase 3 byte-identical; separate path) | ✓ VERIFIED | `_ordering_invariant_guard()` asserts both Phase 3 artifacts exist with `computed_before_alignment:true` or sys.exit(1). `check_ordering_invariant.py` PASS: ran compute via subprocess (exit 0), Phase 3 sha256 identical before/after (flatness `52ecc80...`, cross-camera `c1afa9a...` unchanged), artifact lands on `data/analysis_output/` (NOT scale_independent_metrics/). |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `analysis/alignment.py` | Umeyama/Kabsch fit (±scale), consensus builder, outlier rejection, ideal-board accessor | ✓ VERIFIED | 359 lines (min 120). Exports umeyama_fit, rigid_inlier_fit, build_consensus_corners, ideal_board_corners, matched_arrays. Imported + used by compute CLI. |
| `analysis/compute_scale_alignment.py` | MET-04/05 CLI: consume corners.npz, align, write JSON+schema, Maas/circularity note, ordering guard | ✓ VERIFIED | 428 lines (min 150). Runs clean, writes artifact + schema sidecar, guard present. |
| `data/analysis_output/scale_alignment.json` | per-frame + pooled rigid RMSE, scale factor/%, board size, note; contains `computed_after_alignment` | ✓ VERIFIED | Present; `computed_after_alignment:true`; all required keys present; checker exits 0. |
| `tests/test_alignment.py` | Synthetic unit tests (R/t/s recovery, outlier rejection) | ✓ VERIFIED | 158 lines (min 50). Exits 0, 5 tests PASS. |
| `tests/check_scale_alignment_artifact.py` | Artifact-shape checker incl. no "0.5 %" misread | ✓ VERIFIED | 120 lines (min 60). Exits 0. |
| `tests/check_ordering_invariant.py` | Proof Phase 3 unchanged + separate path | ✓ VERIFIED | 108 lines (min 40). Exits 0. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| compute_scale_alignment.py | alignment.py | `from analysis.alignment import ...` | ✓ WIRED | Imports umeyama_fit, rigid_inlier_fit, build_consensus_corners, ideal_board_corners, matched_arrays (lines 57-63) and calls them in main(). |
| compute_scale_alignment.py | scale_alignment.json | json.dump outside scale_independent_metrics/ | ✓ WIRED | Default --out `data/analysis_output/scale_alignment.json`; written via json.dump (line 295). Ordering checker confirms separate path. |
| compute_scale_alignment.py | ideal 60 mm board | getChessboardCorners() | ✓ WIRED | Reached via `ideal_board_corners(board)` (alignment.py line 324 calls `board.get_opencv_board().getChessboardCorners()`). PLAN pattern expected the call literally in compute; implementation correctly factored it into the `ideal_board_corners` accessor that compute invokes — functionally equivalent, fully wired. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| MET-04 | 04-01-PLAN | Absolute scale — reconstructed square size vs known 60 mm, consistency check w/ circularity + Maas factor-of-two | ✓ SATISFIED | board_size_mm + scale_factor per-frame/pooled; circularity_caveat + maas_2015_context note; no "0.5 %". |
| MET-05 | 04-01-PLAN | Rigid alignment of MVS corners to ideal planar board, inlier RMSE per position; scale-independent before scaling | ✓ SATISFIED | rigid_rms_mm + n_inliers per-frame, pooled rigid_rms_mm_pooled; rigid_inlier_fit (no-scale) verified by tests; ordering guard ensures Phase 3 ran first. |

No orphaned requirements: REQUIREMENTS.md maps only MET-04 and MET-05 to Phase 4, both declared in PLAN frontmatter `requirements: [MET-04, MET-05]`.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| (none) | — | — | — | No TODO/FIXME/placeholder/stub patterns found in any phase file. |

### Human Verification Required

None. All success criteria are programmatically verifiable and verified (artifact contents, banned-string absence, byte-identity hashes, deterministic numeric tests).

### Gaps Summary

No gaps. All four Phase 4 success criteria are met:
- MET-05 rigid inlier RMSE (per-frame + pooled + inlier counts) and MET-04 reconstructed size / scale factor are computed and persisted to `data/analysis_output/scale_alignment.json`.
- The honest framing is present and correct: circularity of the 60 mm anchor is stated, the result is contextualized against the Maas (2015) factor-of-two benchmark, and the banned "0.5 %" misread appears nowhere.
- The ordering invariant holds: a runtime guard refuses to run unless the locked Phase 3 artifacts exist with `computed_before_alignment:true`, the Phase 3 JSONs are sha256 byte-identical before/after a Phase 4 run, and the artifact lands on the separate `data/analysis_output/` path.
- All five tests/checkers exit 0 in the AquaMVS env; OUT-05 entrypoint regeneration correctly deferred to Phase 5 (analysis/entrypoint.py untouched).

---

_Verified: 2026-06-30_
_Verifier: Claude (gsd-verifier)_
