---
phase: 05-manuscript-deliverables
plan: 02
subsystem: analysis
tags: [python, matplotlib, dissertationfigures, figures, svg, pdf, png]

requires:
  - phase: 05-01
    provides: analysis/deliverables/_style.py, _artifacts.py (DissertationFigures wrapper + artifact loaders)
  - phase: 03-scale-independent-metrics
    provides: flatness_consistency.json (MET-01..02 per-frame arrays)
  - phase: 04-scale-check-alignment
    provides: error_decomposition.json (MET-06 range-vs-lateral, per-frame + pooled)

provides:
  - analysis/deliverables/fig_spatial_consistency.py — OUT-02 spatial-consistency figure generator
  - analysis/deliverables/fig_range_lateral.py — MET-06 range-vs-lateral refraction-signature figure generator
  - data/analysis_output/figures/spatial_consistency.{svg,pdf,png} — rendered OUT-02 figure (all >1 KB)
  - data/analysis_output/figures/range_vs_lateral.{svg,pdf,png} — rendered MET-06 figure (all >1 KB)

affects:
  - 05-03-entrypoint (imports these modules; calls main() for OUT-05 regeneration)

tech-stack:
  added: []
  patterns:
    - matplotlib.use("Agg") headless backend set before any plt import
    - All figure construction wrapped in `with dissertation_style():` context manager
    - All numeric values read from JSON artifacts at runtime (load_flatness, load_error_decomp)
    - save_figure(fig, name, output_dir=FIGURES_DIR, formats=(...)) with keyword output_dir
    - LinearSegmentedColormap from palette colours for tilt-encoded scatter
    - data/ gitignored by design — only Python modules committed; figures regenerated on demand

key-files:
  created:
    - analysis/deliverables/fig_spatial_consistency.py
    - analysis/deliverables/fig_range_lateral.py
  modified: []

key-decisions:
  - "Figure data read exclusively from load_flatness() and load_error_decomp() — no values recomputed, no literals used"
  - "depth_m displayed as abs(depth_m) (positive depth below surface) for readability on scatter x-axis"
  - "Tilt encoded as colormap (blue-teal-gold LinearSegmentedColormap) with shared colorbar on fig_spatial_consistency 2x3 grid"
  - "Dominance ratio annotation uses f'{dominance:.2f}' read from pooled.range_lateral.range_dominance, verified present in SVG text"
  - "fig_range_lateral adds second panel (board-frame out-of-plane vs in-plane pooled) as conceptual contrast per plan option"

metrics:
  duration: 10min
  completed: 2026-06-30
  tasks: 2
  files_modified: 2
---

# Phase 5 Plan 02: Manuscript Figures Summary

**Two dissertation-styled manuscript figures generated from on-disk JSON artifacts: OUT-02 spatial-consistency 2x3 scatter grid and MET-06 range-vs-lateral grouped-bar + board-frame contrast, both exported as svg+pdf+png.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-06-30T17:52:00Z
- **Completed:** 2026-06-30T18:02:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `analysis/deliverables/fig_spatial_consistency.py`: 2x3 grid showing flatness_rms_mm and board_size_mm vs depth/lateral/tilt for all 8 frames; tilt colour-encoded (blue-teal-gold colormap); reference lines at pooled flatness (1.09 mm), 60 mm nominal, and measured board mean; exports to `data/analysis_output/figures/spatial_consistency.{svg,pdf,png}` (152 KB SVG, 203 KB PDF, 151 KB PNG).
- Created `analysis/deliverables/fig_range_lateral.py`: grouped-bar chart per-frame + pooled contrasting range_rms_mm (blue) vs lateral_rms_mm (gold); pooled dominance ratio annotation (`{dominance:.2f}` = 4.41, read from artifact, verified present in SVG text); second panel with board-frame out-of-plane vs in-plane (pooled); exports to `data/analysis_output/figures/range_vs_lateral.{svg,pdf,png}` (72 KB SVG, 495 KB PDF, 72 KB PNG).

## Task Commits

1. **Task 1: Spatial-consistency figure (OUT-02)** - `4e37691` (feat)
2. **Task 2: Range-vs-lateral refraction-signature figure (MET-06)** - `c5934a7` (feat)

## Files Created/Modified

- `analysis/deliverables/fig_spatial_consistency.py` - OUT-02 generator; 2x3 scatter grid, tilt colormap, reference lines, save_figure via FIGURES_DIR
- `analysis/deliverables/fig_range_lateral.py` - MET-06 generator; grouped bars per-frame + pooled, dominance annotation from artifact, board-frame panel, save_figure via FIGURES_DIR

## Artifact Keys Used

**fig_spatial_consistency.py:**
- `flatness_consistency.json` > `variation.per_frame_arrays.{depth_m, lateral_xy_m, tilt_deg, flatness_rms_mm, board_size_mm}` (8-element lists)
- `flatness_consistency.json` > `pooled.flatness_rms_mm_pooled` (reference line)
- `flatness_consistency.json` > `variation.board_size_mm_mean` (measured mean reference line)

**fig_range_lateral.py:**
- `error_decomposition.json` > `per_frame[].range_lateral.{range_rms_mm, lateral_rms_mm, range_dominance}` (per-frame bars)
- `error_decomposition.json` > `pooled.range_lateral.{range_rms_mm, lateral_rms_mm, range_dominance}` (pooled bar group + annotation)
- `error_decomposition.json` > `pooled.board_frame.{out_of_plane_rms_mm, in_plane_rms_mm}` (second panel)

## Output Files

| File | Format | Size |
|------|--------|------|
| data/analysis_output/figures/spatial_consistency.svg | SVG | 152 KB |
| data/analysis_output/figures/spatial_consistency.pdf | PDF | 203 KB |
| data/analysis_output/figures/spatial_consistency.png | PNG | 151 KB |
| data/analysis_output/figures/range_vs_lateral.svg | SVG | 72 KB |
| data/analysis_output/figures/range_vs_lateral.pdf | PDF | 495 KB |
| data/analysis_output/figures/range_vs_lateral.png | PNG | 72 KB |

## Decisions Made

- **Read-only artifact access:** Both generators call `load_flatness()` / `load_error_decomp()` and read numeric values at runtime. No literals for metric values.
- **Depth display:** `abs(depth_m)` shown as positive depth below surface — visually cleaner for scatter axes.
- **Tilt colormap:** `LinearSegmentedColormap.from_list` using palette colours (blue, teal, gold) with shared colorbar on the right column of the 2x3 grid.
- **Dominance annotation verified in SVG:** `scratch_verify_f2.py` asserts `"4.41" in svg_text` — confirmed the vector text is present, not rasterized.
- **Board-frame panel included:** Plan says "optional"; included as it adds conceptual context (out-of-plane 0.79 mm vs in-plane 0.70 mm — nearly isotropic once range direction excluded).

## Deviations from Plan

None — plan executed exactly as written. The tight_layout UserWarning on the spatial-consistency figure is benign (colorbar sharing axes is expected; figure renders correctly).

## Issues Encountered

None.

## Self-Check: PASSED

- `analysis/deliverables/fig_spatial_consistency.py` — FOUND
- `analysis/deliverables/fig_range_lateral.py` — FOUND
- `data/analysis_output/figures/spatial_consistency.svg` — FOUND (152,294 bytes)
- `data/analysis_output/figures/spatial_consistency.pdf` — FOUND (203,389 bytes)
- `data/analysis_output/figures/spatial_consistency.png` — FOUND (150,825 bytes)
- `data/analysis_output/figures/range_vs_lateral.svg` — FOUND (72,110 bytes)
- `data/analysis_output/figures/range_vs_lateral.pdf` — FOUND (494,849 bytes)
- `data/analysis_output/figures/range_vs_lateral.png` — FOUND (71,866 bytes)
- Commits 4e37691 and c5934a7 — VERIFIED in git log

---
*Phase: 05-manuscript-deliverables*
*Completed: 2026-06-30*
