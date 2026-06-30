# Phase 5: Manuscript Deliverables - Context

**Gathered:** 2026-06-30
**Status:** Ready for planning

*Captured in auto mode. Final phase — assembles all computed metrics into manuscript-ready artifacts. Decisions grounded in design §8, the user's `DissertationFigures` package (inspected), the corrected Phase 3/4 numbers, and the added MET-06 decomposition.*

<domain>
## Phase Boundary

Turn the already-computed metrics into manuscript deliverables: a **results table**, the **spatial-consistency figure**, a **range-vs-lateral figure** (MET-06 refraction signature), **per-camera agreement output**, a drafted **methods paragraph**, and a **single reproducible entrypoint** (OUT-01..05). **No new metrics** — this phase reads the persisted artifacts and presents them. All numbers already exist on disk.

</domain>

<decisions>
## Implementation Decisions

### Inputs (read-only; do not recompute)
- `data/analysis_output/corner_transfer/{corners.npz, dropout_report.json}`
- `data/analysis_output/scale_independent_metrics/{flatness_consistency.json, cross_camera_agreement.json}`
- `data/analysis_output/scale_alignment.json`
- `data/analysis_output/error_decomposition.json`
Phase 5 loads these; it never re-runs transfer/metrics (the single entrypoint *orchestrates* the earlier stages — see OUT-05 — but the presentation code reads artifacts).

### Figure styling — match DissertationFigures (locked)
- Use the user's `dissertationfigures` package API directly: `dissertation_style()` (rcParams context manager), `COLORS` / `PALETTE` (Tol colorblind-safe), and `save_figure(fig, name, dest, formats=("svg","pdf","png"))`.
- Conventions inherited: serif (Computer Modern Roman; DejaVu Serif fallback), single-column width, 300 dpi savefig, small fonts. Export **svg + pdf + png** for every figure.
- **Make it importable in the AquaMVS env**: preferred = editable install `pip install -e C:\Users\tucke\PycharmProjects\DissertationFigures`; fallback = insert its `src` on `sys.path` at runtime. (It currently does NOT import in the AquaMVS env — Phase 5 must resolve this.) Do not re-implement the palette/rcParams locally if the package can be imported.
- Note: the package already has a `figures/aquamvs/` subpackage; mirror its import pattern (`from dissertationfigures.core.style import COLORS; from dissertationfigures.core.export import save_figure`).

### OUT-01 — Results table
- One row per metric: **value, units, and a label** of "scale-independent (non-circular)" vs "consistency check (partly circular)".
- Rows (with current values): flatness 1.09 mm (SI); spatial-consistency size CV 0.0015 / tilt 2.8–55.5° (SI); cross-camera agreement 3.46 mm (SI); rigid inlier RMSE 1.05 mm (SI); **range-vs-lateral dominance 4.41** — range 3.64 mm vs lateral 0.82 mm (SI, refraction); absolute scale +0.04% / 60.013 mm (**consistency check, circularity stated**).
- Emit in **three forms**: Markdown (review), LaTeX booktabs (manuscript), and CSV (source). Generated from the artifacts so it never drifts.

### OUT-02 — Spatial-consistency figure (highest-value)
- Flatness and board size **vs working-volume position** (depth, lateral position, and tilt) across the 8 frames — the figure that shows the refractive model holds across the volume. DissertationFigures style.

### MET-06 — Range-vs-lateral figure (the refraction signature)
- A figure contrasting **range vs lateral** residual RMS (per-frame and pooled) — visually carries "residual error is range-dominated (~4.4×), consistent with refraction; lateral/in-plane error is sub-mm." Pair conceptually with the board-frame (in-plane vs out-of-plane) split.

### OUT-03 — Per-camera agreement output
- Per-camera board-localization agreement, derived from `cross_camera_agreement.json` (which records per-(frame,camera) inclusion/exclusion and co-observation). Honor the rig fact: board-blind / low-coverage cameras are non-events, not errors — present inclusion explicitly.

### OUT-04 — Methods paragraph (drafted, manuscript-ready)
- Must state: known-geometry ChArUco target (12×9, 60 mm); **measured** calibration/validation overlap (exactly 2 of 10 frames — 0 and 3930 — omitted; all metrics on the 8 held-out frames); corner transfer **through the refractive depth maps** (`cast_ray`); **scale-independent metrics led** (flatness, spatial consistency, cross-camera); **absolute scale reported as a consistency check with circularity stated**; the **range-dominated residual = refraction signature** finding; contextualized by the **Maas (2015) factor-of-two** refractive precision benchmark (NEVER "0.5 %").
- Cite: **de Jesus et al. 2015** (method / held-out control), **Menna & Nocerino 2019** (underwater-metrology domain), **Maas 2015** (benchmark). Use placeholder cite keys; the prose is the deliverable.
- Output as committed Markdown (it's manuscript text, small — belongs in the repo, not gitignored).

### OUT-05 — Single reproducible entrypoint
- One command regenerates **all** artifacts from the extracted data, in order: corner transfer → flatness/consistency → cross-camera → scale/alignment → MET-06 decomposition → table + figures + methods. Deterministic; safe to re-run.
- Run in the AquaMVS env (`conda run -n AquaMVS python ...`). Surface a clear final summary of what was written.

### Output locations
- **Figures** (binary, regenerable) → `data/analysis_output/figures/` (gitignored).
- **Text deliverables** (table.md / table.tex / table.csv, methods.md) → a committed `results/` dir in the repo (small, the actual manuscript content). Per-camera summary table likewise committed.

### Claude's Discretion
- Exact figure layouts/sub-panels, marker/color choices within the palette, and how depth/tilt are encoded (color vs axis).
- Whether the entrypoint is an extension of `analysis/entrypoint.py` or a new `run_all` script.
- LaTeX table column set/ordering; cite-key names.
- Whether per-camera agreement is a table, a small figure, or both.

</decisions>

<specifics>
## Specific Ideas

- DissertationFigures public API (from `__init__`): `dissertation_style`, `save_figure`, `load_data`, `COLORS`, `PALETTE`. `save_figure(fig, name, dest, formats=("svg","pdf","png"))`. Palette is Tol colorblind-safe (keys: blue #003070, gold #EAD34C, teal, coral, …).
- The board carries **precision + spatial coverage**; the tank (separate, in the manuscript) carries **independent absolute scale**. The methods paragraph should note they pair so the circularity worry dissolves (design §8).
- Corrected headline numbers to report (do not use the pre-fix 58.5 mm cross-camera or the 173.7 mm frame-2 value): flatness 1.09 mm, size CV 0.0015, cross-camera 3.46 mm, rigid RMSE 1.05 mm, scale +0.04%, range-dominance 4.41.

</specifics>

<deferred>
## Deferred Ideas

- Inter-corner grid-regularity (§4.4, GRID-01) and cross-pathway RoMa-vs-LightGlue (§4.6, XPATH-01) — v2.
- Integrating the figure modules INTO the DissertationFigures `figures/aquamvs/` package (vs generating in this repo) — keep generation in this repo for OUT-05 self-containment; upstreaming is a later nicety.

</deferred>

---

*Phase: 05-manuscript-deliverables*
*Context gathered: 2026-06-30*
