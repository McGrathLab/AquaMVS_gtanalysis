---
phase: 05-manuscript-deliverables
verified: 2026-06-30T14:30:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
human_verification:
  - test: "Inspect spatial_consistency.png and range_vs_lateral.png visually"
    expected: "Figures match DissertationFigures visual style — fonts, palette, layout consistent with dissertation conventions"
    why_human: "Programmatic checks confirm dissertation_style() context manager and save_figure() API are used correctly; only a human can confirm the rendered aesthetic matches the locked dissertation style"
---

# Phase 5: Manuscript Deliverables — Verification Report

**Phase Goal:** All metrics assembled into manuscript-ready artifacts — results table, spatial-consistency figure, per-camera output, and methods paragraph — regenerable from one reproducible entrypoint.
**Verified:** 2026-06-30T14:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Results table lists each metric with scale-independent vs consistency-check label | VERIFIED | `results/table.{md,tex,csv}` — 6 rows, 4 labeled "scale-independent (non-circular)", MET-04 labeled "consistency check (partly circular)"; booktabs LaTeX present |
| 2 | Spatial-consistency figure rendered in DissertationFigures style | VERIFIED | `data/analysis_output/figures/spatial_consistency.{svg,pdf,png}` all exist (150–500 KB); `fig_spatial_consistency.py` wraps construction in `with dissertation_style()` and calls `save_figure(output_dir=FIGURES_DIR, formats=("svg","pdf","png"))` |
| 3 | Per-camera board-localization agreement output produced | VERIFIED | `results/per_camera_agreement.{md,csv}` exist; md has non-event framing ("This is a non-event (expected rig characteristic), not an error or failure."); CSV has `frames_included`/`frames_excluded` per camera |
| 4 | Methods paragraph covers all required narrative with correct citations; no banned strings | VERIFIED | `results/methods.md` is 88 lines; contains: 12x9/60 mm ChArUco, "exactly 2 of the 10 frames", `cast_ray`, scale-independent led, consistency check/circularity, range-dominated 4.41x refraction signature, "factor of two" (×2), [@deJesus2015], [@MennaNocerino2019], [@Maas2015]; grep for "0.5 %", "58.5", "173.7" returns zero hits |
| 5 | One entrypoint regenerates all artifacts from extracted data | VERIFIED | `analysis/run_all.py` orchestrates 5 compute stages in dependency order via subprocess then calls all 5 deliverable generator `main()` functions; `--skip-metrics` flag; prints file-by-file summary reading headline metrics from artifacts |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `analysis/deliverables/_style.py` | VERIFIED | Imports `dissertation_style`, `COLORS`, `PALETTE`, `save_figure` from DissertationFigures submodules directly; sys.path fallback to editable-install path included |
| `analysis/deliverables/_artifacts.py` | VERIFIED | Defines `load_flatness`, `load_cross_camera`, `load_scale_alignment`, `load_error_decomp`, `load_dropout`; anchors paths to `_REPO_ROOT = Path(__file__).resolve().parent.parent.parent` |
| `analysis/deliverables/make_table.py` | VERIFIED | Reads all 5 artifact loaders, builds 6 rows from artifact values (no hardcoding), writes MD/TeX/CSV with banned-string guard |
| `analysis/deliverables/make_per_camera.py` | VERIFIED | Reads `load_cross_camera()`, accesses `cameras_included`/`cameras_excluded` per frame, non-event framing in header |
| `analysis/deliverables/fig_spatial_consistency.py` | VERIFIED | Reads `load_flatness()`, uses `per_frame_arrays`, wraps in `dissertation_style()`, calls `save_figure(output_dir=FIGURES_DIR, ...)` |
| `analysis/deliverables/fig_range_lateral.py` | VERIFIED | Reads `load_error_decomp()`, reads `range_rms_mm`/`lateral_rms_mm`/`range_dominance` from artifact (never hardcoded), wraps in `dissertation_style()` |
| `analysis/deliverables/make_methods.py` | VERIFIED | Reads `load_scale_alignment()` and `load_error_decomp()` for cited numbers; prose cites deJesus2015, MennaNocerino2019, Maas2015; banned-string guard before write |
| `analysis/run_all.py` | VERIFIED | Substantive ~300-line entrypoint; 5 compute stages via subprocess in order; 5 deliverable generators via import+call; `print_summary()` lists every output file with EXISTS/size and reads headline metrics from artifacts |
| `results/table.csv` | VERIFIED | 6 data rows; contains "scale-independent", "consistency check"; values 1.09, 3.46, 1.05, 4.41, 60.013 present |
| `results/table.md` | VERIFIED | GitHub Markdown pipe table, 6 rows, 682 B |
| `results/table.tex` | VERIFIED | LaTeX booktabs table (`\toprule`/`\midrule`/`\bottomrule`), 882 B |
| `results/per_camera_agreement.md` | VERIFIED | 906 B; contains "included", "non-event" |
| `results/per_camera_agreement.csv` | VERIFIED | 212 B; header `camera_id,frames_included,frames_excluded`; 12 camera rows |
| `results/methods.md` | VERIFIED | 88 lines / 5711 B; all required claims and citations present; no banned strings |
| `data/analysis_output/figures/spatial_consistency.{svg,pdf,png}` | VERIFIED | 152 KB SVG, 203 KB PDF, 151 KB PNG |
| `data/analysis_output/figures/range_vs_lateral.{svg,pdf,png}` | VERIFIED | 72 KB SVG, 495 KB PDF, 72 KB PNG |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `make_table.py` | JSON artifacts | `_artifacts.load_flatness/load_cross_camera/load_scale_alignment/load_error_decomp/load_dropout` | WIRED | All 5 loaders imported at lines 18-25; called in `_build_rows()` lines 36-41 |
| `make_per_camera.py` | `cross_camera_agreement.json per_frame[].cameras_included/excluded` | `load_cross_camera()` | WIRED | `load_cross_camera` imported line 22; `cameras_included` accessed line 49; `cameras_excluded` accessed line 51 |
| `fig_spatial_consistency.py` | `flatness_consistency.json variation.per_frame_arrays` | `load_flatness()` | WIRED | `load_flatness` imported; `pfa = data["variation"]["per_frame_arrays"]`; `pfa["flatness_rms_mm"]` and `pfa["board_size_mm"]` read |
| `fig_range_lateral.py` | `error_decomposition.json per_frame[] + pooled.range_lateral` | `load_error_decomp()` | WIRED | `range_rms_mm`, `lateral_rms_mm`, `range_dominance` all read from artifact with comment "never hardcoded" |
| Both figure modules | `save_figure(output_dir=FIGURES_DIR, formats=...)` | `analysis.deliverables._style` | WIRED | Both modules import `save_figure` from `_style`; call with `output_dir=FIGURES_DIR` keyword |
| `run_all.py` | 5 compute stages in order | subprocess `-m analysis.transfer_corners` … `analysis.compute_error_decomposition` | WIRED | Lines 81-131; all 5 stages with correct arg paths from plan specification |
| `run_all.py` | 5 deliverable generators | `from analysis.deliverables.make_table import main as make_table` etc. | WIRED | Lines 142-165; all 5 generators imported and called |
| `make_methods.py` | `scale_alignment.json note.maas_2015_context + error_decomposition.json pooled.range_lateral` | `load_scale_alignment()`, `load_error_decomp()` | WIRED | Both loaders imported; `range_dominance` read from `ed["pooled"]["range_lateral"]["range_dominance"]` line 66 |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| OUT-01 | 05-01-PLAN.md | Results table — per metric: value and SI vs consistency-check label | SATISFIED | `results/table.{md,tex,csv}` with 6 rows and correct labels |
| OUT-02 | 05-02-PLAN.md | Spatial-consistency figure — flatness + size vs working-volume position — DissertationFigures style | SATISFIED | `data/analysis_output/figures/spatial_consistency.{svg,pdf,png}` all >100 KB; built under `dissertation_style()` |
| OUT-03 | 05-01-PLAN.md | Per-camera board-localization agreement output | SATISFIED | `results/per_camera_agreement.{md,csv}` with per-(frame,camera) inclusion and non-event framing |
| OUT-04 | 05-03-PLAN.md | Drafted methods paragraph with required claims and 3 citations | SATISFIED | `results/methods.md` 88 lines; all 9 required concepts verified; cites deJesus2015, MennaNocerino2019, Maas2015 |
| OUT-05 | 05-03-PLAN.md | Analysis reproducible — one entrypoint regenerates all artifacts | SATISFIED | `analysis/run_all.py` orchestrates 5 compute stages + 5 deliverable generators; `analysis/entrypoint.py` (DATA-04) untouched |

All 5 Phase 5 requirements satisfied. No orphaned requirements.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `analysis/deliverables/make_table.py` | 106 | `f"+{scale_err_pct:+.2f}%"` — literal `"+"` prefix combined with `:+.2f` format spec produces `"++0.04%"` (double plus) in all three table outputs | Warning | Cosmetic formatting defect in manuscript table; the numeric value (0.04%) is correct; no banned string introduced; fix by removing the leading `"+"` literal or switching to `:.2f` instead of `:+.2f` |

No TODO/FIXME/PLACEHOLDER/stub anti-patterns found in any deliverable file or results output.

---

### Human Verification Required

#### 1. Figure Visual Style

**Test:** Open `data/analysis_output/figures/spatial_consistency.png` and `range_vs_lateral.png` in an image viewer.
**Expected:** Figures use the DissertationFigures palette (blue #003070, gold #EAD34C etc.), correct font family and sizes (set by `dissertation_style()` context manager), clean layout with labeled axes; visual style matches other dissertation figures.
**Why human:** Programmatic checks confirm the correct API calls (`dissertation_style()` + `save_figure()`), but aesthetic conformance to the locked dissertation style requires visual inspection.

---

### Gaps Summary

No gaps found. All 5 observable truths verified, all artifacts exist and are substantive (not stubs), all key links wired.

The one warning-level issue (double-plus "++0.04%" in the MET-04 table row) is a cosmetic formatting defect with no impact on goal achievement. The correct value is communicated; no banned string is introduced. Recommend fixing `make_table.py` line 106 by changing `f"+{scale_err_pct:+.2f}%"` to `f"{scale_err_pct:+.2f}%"` before manuscript submission.

---

_Verified: 2026-06-30T14:30:00Z_
_Verifier: Claude (gsd-verifier)_
