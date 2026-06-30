# AquaMVS ChArUco Ground-Truth Validation

## What This Is

A reproducible analysis that validates the **AquaMVS dense reconstruction** against a known-geometry ChArUco board captured in the calibration videos. It reconstructs a small set of board frames (already computed), transfers image-detected ChArUco corners into the reconstruction **through the MVS depth maps** (not by hunting for corners in the point cloud), and measures how well the reconstructed board matches the board's known flatness and square geometry. The deliverables are **manuscript artifacts** — a results table, a spatial-consistency figure, per-camera agreement, an honest scale line, and a drafted methods paragraph — that slot into the manuscript where the dropped tank-diameter check was.

This is the de Jesus et al. (2015) methodology (known target + held-out validation points) specialized to AquaMVS's refractive, fixed-array regime.

## Core Value

**Produce defensible, non-circular accuracy numbers for the AquaMVS dense stage — led by scale-independent metrics (flatness and spatial/angular consistency across the working volume) — that hold up in the manuscript.** Absolute scale is reported honestly as a consistency check, never as the headline.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. v1 = headline-first metric set. -->

- [ ] Extract the input dataset into the repo and stand up a reproducible analysis environment (AquaMVS conda env)
- [ ] Transfer image-detected ChArUco corners into the MVS frame by sampling each camera's depth map at corner pixels and back-projecting through the refractive model (`RefractiveProjectionModel.cast_ray`), with a plane-fit fallback for depth dropouts
- [ ] **Flatness (§4.1):** plane-fit RMS of the board's dense points — the single strongest non-circular number
- [ ] **Spatial / angular consistency (§4.2):** report how board size and flatness vary across position, depth, and tilt over the working volume — the highest-value output
- [ ] **Cross-camera agreement (§4.3):** confirm each camera's depth places the board (and transferred corners) in the same 3D location
- [ ] **Absolute scale (§4.5):** reconstructed square size vs known 60 mm, reported explicitly as a consistency check with circularity stated, contextualized by the factor-two refractive precision benchmark (Maas 2015)
- [ ] Results table (per metric: value + scale-independent vs consistency-check), spatial-consistency figure, per-camera agreement output, and a drafted methods paragraph — figures matching DissertationFigures conventions

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- **Recalibration / rerunning AquaMVS reconstruction** — locked decision (§2.4). Overlap with the calibration fit was measured exactly (2 of 10 frames); we validate on the 8 held-out frames as-is.
- **Frames 0 and 3930** (output indices 0 and 5) — coincide with calibration-fit frames; retained on disk but excluded from every reported metric.
- **Cross-pathway agreement (§4.6, RoMa vs LightGlue)** — the provided reconstruction is RoMa-only; a second LightGlue run is not in the data. Deferred to a later milestone.
- **Inter-corner grid regularity (§4.4)** — deferred from the headline-first v1; revisit if needed.
- **Validating the calibration itself** — out of scope by design; the board's square size is a calibration *input* (the scale anchor), so "confirming" it is partly circular.
- **Pure-cloud / orthophoto fallback (§3.4)** — backup only, build only if depth-based corner transfer fails.

## Context

- **Domain:** underwater multi-view stereo (MVS) metrology for an aquaculture/fish-imaging rig. The validation grades the *dense* stage (PatchMatch/plane-sweep, RoMa warp→depth, fusion, in-dense refraction handling) that adds error on top of the calibrated camera model.
- **Manuscript role:** pairs with the tank figures — the tank carries independent absolute scale, the board carries precision + spatial coverage. Reported together, the circularity worry largely dissolves.
- **Design spec:** `C:\Users\tucke\Desktop\aquamvs-groundtruth-validation-design.md` — a complete conceptual design ("what to build and why," not "how"). Open implementer decisions are in its §7; most are "confirm against the data" and are resolved during execution.
- **AquaMVS package (v1.5.2)** is installed in the `AquaMVS` conda env and provides the reusable hooks this validation assembles (verified present):
  - `aquamvs.projection.refractive.RefractiveProjectionModel.cast_ray` — pixel→ray (origin+direction); point at depth `d` = `origin + d·direction`. The (pixel, depth)→world map corner transfer needs.
  - `aquamvs.evaluation.metrics.height_map_difference` — plane-grid RMS; engine for flatness (§4.1) and spatial variance (§4.2).
  - `aquamvs.evaluation.alignment.icp_align` — point-to-plane ICP with `fitness` + `inlier_rmse`; for aligning MVS corners to the ideal board.
  - `aquamvs.evaluation.metrics.reprojection_error`, `cloud_to_cloud_distance`.
  - ChArUco detection available on the AquaCal side (same board/detector that produced the calibration) — reuse for image-side subpixel corners.
- **Input data:** `C:\Users\tucke\Downloads\aquamvs_ground_truth_analysis.zip` (~9 GB). Confirmed structure:
  - `config.yaml`, `calibration.json` (camera + refractive `interface` + board params).
  - `frames/<cam>/frame_NNNNNN.png` — raw frames for the 10 timepoints (raw indices 0, 786, 1572, 2358, 3144, 3930, 4716, 5502, 6288, 7074).
  - `output/frame_000000..009/` each with: `depth_maps/<cam>.npz`, `point_cloud/fused.ply` (~650 MB), `mesh/surface.ply`, `undistorted/<cam>.png`, `consistency_maps/`, `viz/`.
  - **13 cameras** in config; **12** have depth-map `.npz` (camera `e3v8250` has frames but no depth map — likely a witness/reference view; confirm during execution).
- **Board spec (from `calibration.json`):** ChArUco **12×9 squares**, **square_size = 0.06 m (60 mm)**, **marker_size = 0.045 m**, dictionary **DICT_5X5_100**. Outer board ≈ 0.72 × 0.54 m. The **square size (60 mm) is the metric scale anchor** — this is the honest label for the §4.5 scale check.

## Constraints

- **Tech stack**: Python in the existing `AquaMVS` conda env (gives `aquamvs` v1.5.2 + numpy/open3d/opencv/etc.). Reuse library hooks; avoid new reconstruction code — this is "assembly of existing capabilities + the corner-transfer glue."
- **Platform**: Windows 11; conda at `C:\Users\tucke\anaconda3` (env `AquaMVS`). `conda run` cannot take multi-line `python -c` — use script files.
- **Data location**: extract the zip into `./data/` inside the repo (gitignored), then delete the Downloads zip **after verifying extraction**. Code reads from the in-repo data path.
- **Non-circularity**: scale-independent metrics must be reported **before** any scaling/alignment step so they cannot absorb a scale error.
- **Figures**: match the conventions/styling of the existing `DissertationFigures` env (inspect during planning) so plots match the rest of the manuscript.
- **Honesty**: every accuracy claim leads with scale-independent metrics; absolute scale stated as a consistency check with circularity acknowledged and benchmarked against Maas (2015) factor-of-two (not "0.5 %").

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| No recalibration / no reconstruction rerun | Overlap measured exactly (2 of 10 frames); 8 held-out frames suffice | — Pending |
| Validate on 8 held-out frames; omit indices 0 and 5 (raw 0, 3930) | Zero overlap with calibration fit; negligible spatial-coverage loss | — Pending |
| Corner transfer through depth maps, not cloud corner-finding | Isolates the dense per-pixel depth at high-contrast junctions MVS reconstructs best | — Pending |
| Deliverable = manuscript artifacts (table + spatial figure + per-camera + scale line + methods paragraph) | Slots into the manuscript where the tank-diameter check was | — Pending |
| v1 scope = headline-first (§4.1, 4.2, 4.3, 4.5) | Lead with non-circular metrics; defer grid-regularity (4.4) and cross-pathway (4.6) | — Pending |
| Cross-pathway (§4.6) out of scope for v1 | Provided reconstruction is RoMa-only; no LightGlue run on disk | — Pending |
| Extract data into `./data/` (gitignored), delete Downloads zip after verifying | Self-contained, reproducible; verify before deleting source | — Pending |
| Figures match DissertationFigures conventions | Consistency with the rest of the manuscript | — Pending |

---
*Last updated: 2026-06-30 after initialization*
