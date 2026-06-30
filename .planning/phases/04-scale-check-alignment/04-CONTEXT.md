# Phase 4: Scale Check & Alignment - Context

**Gathered:** 2026-06-30
**Status:** Ready for planning

*Captured in auto mode. This phase produces the consistency-check numbers (absolute scale + rigid alignment RMSE), reported honestly with the circularity stated. Decisions grounded in design §4.5, §4 ("Alignment for error reporting"), §1–2 (circularity), and the corrected Phase 3 outputs.*

<domain>
## Phase Boundary

Report **absolute scale (MET-04)** and **rigid alignment (MET-05)** as honest **consistency checks** — explicitly NOT the headline. Runs only now that the scale-independent metrics (Phase 3) are computed and locked, so nothing here can feed back into them. Delivers two per-frame + pooled numbers and the honest framing for the manuscript. **Rendering the table/figure and writing the methods paragraph is Phase 5;** Phase 4 computes/persists the values and the circularity caveat.

</domain>

<decisions>
## Implementation Decisions

### The circularity framing (the most important part — this is why these are NOT headline)
- The board's **square size (60 mm) is the calibration scale anchor** — an *input* that set the whole system's scale, not an output. So reconstructing the board and "confirming" 60 mm is **partly circular**: near-zero scale error is partly true by construction.
- Therefore MET-04 is reported **explicitly as a consistency check with the circularity stated**, after the scale-independent headline (Phase 3). Lead with flatness/spatial-consistency; report scale honestly afterward.
- Benchmark framing: contextualize against the **Maas (2015) refractive precision penalty of ≈ a factor of two** — NOT a "0.5 % of dimension" figure (that was a misread and must not be used).

### MET-05 — Rigid alignment (no scale), inlier RMSE per position
- Align the reconstructed ChArUco corners to the **ideal planar board** (known geometry: internal-corner grid at exactly 60 mm spacing, z = 0 plane) and report **inlier RMSE per frame**.
- Use a **rigid (rotation + translation only, NO scale) closed-form fit with known corner_id correspondence** — i.e. Kabsch/Umeyama with `with_scaling=False`. Do NOT use `icp_align` as the primary (it's point-to-plane ICP without known correspondence); corner IDs give exact matches, so the closed-form rigid fit is correct and avoids search. (`icp_align` may serve as an optional cross-check only.)
- "Inlier" RMSE: reject gross per-corner outliers (consistent with the Phase 3 finding that a few corners can be off) before reporting RMSE, and record inlier count. Report per-frame and pooled, in mm.
- Input corners: build a **per-frame consensus 3D corner** (one point per corner_id, averaging the co-observing cameras' physically-valid corners from the cleaned `corners.npz`) for a stable per-frame alignment. (Per-camera variants optional.)
- This number is rigid-alignment residual = how well the reconstructed corner *grid shape* matches the ideal board, independent of where/how it's posed.

### MET-04 — Absolute scale (consistency check)
- Report reconstructed square size vs the known **60 mm**. Two compatible estimators:
  1. **Inter-corner spacing** (already computed in MET-02: mean ≈ 60.01 mm, CV ≈ 0.0015) — reframed here as the scale consistency check.
  2. **Umeyama-with-scale factor**: align corners to the ideal board *allowing scale*; the recovered scale `s` gives a single global scale-error number per frame (`s − 1`). Report this alongside the spacing.
- Present as a consistency check with the circularity sentence attached; do not headline it. Pair conceptually with the tank's independent absolute scale (the tank carries independent scale, the board carries precision/coverage).

### Ordering invariant (still in force)
- Phase 4 alignment/scaling is computed **after** Phase 3 and written to **separate artifacts**. It must never modify or feed back into the Phase 3 scale-independent outputs. The Phase 3 artifacts carry `computed_before_alignment: true`; Phase 4 outputs are the "after alignment" numbers.

### Units & persistence
- Distances in **mm**, scale as a dimensionless factor (and %). Persist a per-frame + pooled artifact under `data/analysis_output/` (e.g. `scale_alignment.json`) with: per-frame rigid inlier RMSE, inlier count, scale factor, board size; pooled summary; and a machine-readable note of the circularity caveat + Maas framing. Print a concise summary to stdout.

### Claude's Discretion
- Umeyama/Kabsch implementation (write directly; it's closed-form) and the outlier-rejection rule/threshold for inlier RMSE.
- Whether to also run a per-camera alignment in addition to the per-frame consensus.
- Exact ideal-board corner construction (reuse `board.get_opencv_board().getChessboardCorners()` board-local coords).
- Whether to include the optional `icp_align` cross-check.

</decisions>

<specifics>
## Specific Ideas

- Known corner_id correspondence → closed-form rigid/similarity fit (Kabsch/Umeyama), not ICP search. Implement both variants (with and without scale) from the same matched point sets: no-scale → MET-05 RMSE; with-scale → MET-04 scale factor.
- Ideal board corners come from `board.get_opencv_board().getChessboardCorners()` (board-local metres, z=0), indexed by corner_id — same source Phase 2 used for PnP.
- Consume the **cleaned** `data/analysis_output/corner_transfer/corners.npz` (post-fix, 2605 corners, all Z>0). Apply the same physical-validity gate defensively.
- Corrected Phase 3 numbers this pairs with: flatness 1.09 mm, size CV 0.0015, cross-camera 3.46 mm — Phase 4 adds the rigid RMSE + scale factor to complete the results table.
- Available hooks: `aquamvs.evaluation.alignment.icp_align` (point-to-plane ICP, optional cross-check only).

</specifics>

<deferred>
## Deferred Ideas

- Inter-corner grid-regularity metric (§4.4, GRID-01) — v2.
- The results table, spatial-consistency figure, per-camera output, and methods paragraph (OUT-01..05) — Phase 5.
- Cross-pathway agreement (§4.6, XPATH-01) — v2 (RoMa-only data).

</deferred>

---

*Phase: 04-scale-check-alignment*
*Context gathered: 2026-06-30*
