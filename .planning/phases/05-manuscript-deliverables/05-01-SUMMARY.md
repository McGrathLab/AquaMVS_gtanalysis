---
phase: 05-manuscript-deliverables
plan: 01
subsystem: analysis
tags: [python, json, latex, markdown, csv, dissertationfigures, booktabs]

requires:
  - phase: 04-scale-check-alignment
    provides: scale_alignment.json with MET-04/MET-05 pooled values
  - phase: 03-scale-independent-metrics
    provides: flatness_consistency.json and cross_camera_agreement.json (MET-01..03)
  - phase: 04-scale-check-alignment
    provides: error_decomposition.json with MET-06 range-vs-lateral dominance

provides:
  - analysis/deliverables/ importable subpackage (_style.py, _artifacts.py, make_table.py, make_per_camera.py)
  - DissertationFigures editable install in AquaMVS env (editable + sys.path fallback)
  - results/table.{md,tex,csv} — 6-row results table with SI vs circularity labels
  - results/per_camera_agreement.{md,csv} — per-camera inclusion/exclusion roll-up (non-event framing)

affects:
  - 05-02-figures (imports _style.py, _artifacts.py)
  - 05-03-entrypoint (calls make_table.main(), make_per_camera.main())

tech-stack:
  added: [dissertationfigures (editable install via pip install -e)]
  patterns:
    - Repo-root-anchored artifact paths via Path(__file__).resolve().parent.parent.parent
    - Read-only artifact loaders (JSON only, never recompute values)
    - Banned-string guard at write time (assert before file.write_text)
    - sys.path fallback in _style.py for reproducibility without editable install

key-files:
  created:
    - analysis/deliverables/__init__.py
    - analysis/deliverables/_style.py
    - analysis/deliverables/_artifacts.py
    - analysis/deliverables/make_table.py
    - analysis/deliverables/make_per_camera.py
    - results/table.md
    - results/table.tex
    - results/table.csv
    - results/per_camera_agreement.md
    - results/per_camera_agreement.csv
  modified: []

key-decisions:
  - "DissertationFigures made importable via editable install (pip install -e) in AquaMVS env; _style.py also inserts src/ on sys.path as self-contained fallback for OUT-05 reproducibility"
  - "Artifact paths anchored to repo root via Path(__file__).resolve() chain so scripts run correctly from any cwd under conda run"
  - "Banned strings (58.5, 173.7, 0.5 %) guarded programmatically at write time in both make_table.py and make_per_camera.py"
  - "Per-camera exclusions framed as non-events in header prose and Markdown output — excluded = did not co-observe enough corners this frame, not an error"
  - "MET-06 range-vs-lateral dominance row added to table with refraction-signature note; MET-04 row labeled consistency check (partly circular)"

patterns-established:
  - "Deliverables subpackage pattern: _artifacts.py (read-only loaders) + _style.py (styling wrapper) + make_*.py (generators with main())"
  - "All numeric values read from JSON artifacts at runtime — never hardcoded or drifted"

requirements-completed: [OUT-01, OUT-03]

duration: 18min
completed: 2026-06-30
---

# Phase 5 Plan 01: Manuscript Deliverables Foundation Summary

**Importable `analysis/deliverables/` subpackage with DissertationFigures styling wrapper and artifact loaders; OUT-01 results table (md/tex/csv, 6 metrics, SI vs circularity labels) and OUT-03 per-camera board-localization agreement (md/csv, non-event framing) committed to `results/`**

## Performance

- **Duration:** 18 min
- **Started:** 2026-06-30T17:34:42Z
- **Completed:** 2026-06-30T17:52:00Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- Created `analysis/deliverables/` as an importable Python subpackage with DissertationFigures editable install + sys.path fallback in `_style.py`, and five read-only JSON artifact loaders in `_artifacts.py` (all paths anchored to repo root)
- Generated `results/table.{md,tex,csv}` from live artifact values: 6 rows covering MET-01 through MET-06, LaTeX booktabs, banned-string guards enforced at write time
- Generated `results/per_camera_agreement.{md,csv}` from `cross_camera_agreement.json`: per-camera inclusion/exclusion roll-up with non-event framing in the intro prose

## Task Commits

1. **Task 1: Create deliverables subpackage** - `a384297` (feat)
2. **Task 2: Results table generator (OUT-01)** - `7382493` (feat)
3. **Task 3: Per-camera board-localization agreement (OUT-03)** - `9a96fa4` (feat)

## Files Created/Modified

- `analysis/deliverables/__init__.py` - Package init (one-line docstring)
- `analysis/deliverables/_style.py` - DissertationFigures wrapper; editable install + sys.path fallback; re-exports dissertation_style, COLORS, PALETTE, save_figure
- `analysis/deliverables/_artifacts.py` - Read-only loaders for all 5 JSON artifacts; RESULTS_DIR / FIGURES_DIR / ANALYSIS_OUTPUT constants; repo-root-anchored paths
- `analysis/deliverables/make_table.py` - OUT-01 generator; reads artifacts, emits 6-row table in md/tex/csv; banned-string guard; CLI __main__
- `analysis/deliverables/make_per_camera.py` - OUT-03 generator; reads cross_camera_agreement.json per_frame[]; per-camera roll-up; non-event framing; CLI __main__
- `results/table.md` - GitHub Markdown results table (6 rows, SI + circularity labels)
- `results/table.tex` - LaTeX booktabs results table (\\toprule/\\midrule/\\bottomrule)
- `results/table.csv` - CSV source-of-truth (header + 6 data rows)
- `results/per_camera_agreement.md` - Per-camera inclusion summary + per-frame RMS table with non-event intro
- `results/per_camera_agreement.csv` - Per-camera roll-up (camera_id, frames_included, frames_excluded)

## Decisions Made

- **DissertationFigures importability:** Installed via `pip install -e` (preferred) AND added `sys.path.insert(0, r"...DissertationFigures\src")` in `_style.py` as a fallback for OUT-05 reproducibility without the editable install.
- **Repo-root anchoring:** Artifact paths computed as `Path(__file__).resolve().parent.parent.parent` so `conda run` from any cwd resolves correctly.
- **Banned-string guard:** `_check_banned()` runs before every `write_text()` call in both generators, raising ValueError if "58.5", "173.7", or "0.5 %" appears.
- **Non-event framing:** Per-camera agreement header explicitly states exclusion = not co-observing enough corners, not a failure. The word "non-event" appears in the Markdown intro.
- **MET-06 in table:** Range-vs-lateral dominance row labeled "scale-independent (non-circular, refraction signature)" per plan specification.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `analysis/deliverables/` subpackage is ready for 05-02 (figures) to import `_style.py` and `_artifacts.py`
- `results/` dir is committed (not gitignored); both OUT-01 and OUT-03 artifacts are ready for manuscript review
- DissertationFigures is installed in AquaMVS env (editable); `_style.py` also provides a sys.path fallback

---
*Phase: 05-manuscript-deliverables*
*Completed: 2026-06-30*
