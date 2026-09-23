# AquaMVS ChArUco Ground-Truth Validation — Findings & Conclusions

*Plain-language summary of what the validation found and what it means. Numbers are
read from the computed artifacts of the refractive reconstruction under the current
libraries (AquaCal 2.1.0 calibration — the same file the AquaCal paper publishes —
and AquaMVS 1.7.2), in `data/analysis_output.modern_refractive/`; the manuscript-ready
prose is in `results/methods.md`, the metric table in `results/table.md`, and the
refraction/pathway comparison in `data/results.modern_comparison/`.*

---

## Bottom line

The AquaMVS dense reconstruction is **metric-grade through water**. Across 8 held-out
ChArUco-board poses spanning the working volume, the reconstructed board is **flat to
~1.1 mm**, its **square size is correct to ~0.06 %**, independent cameras place the same
board points to **~1.8 mm**, and the reconstructed corner grid matches the ideal 60 mm
board to **~1.08 mm** after rigid alignment. What residual error remains is **range
(depth) error, not lateral** — the expected signature of refraction, and small.

The headline accuracy claims rest on **scale-independent (non-circular)** metrics, so
they are not an artifact of the board having set the calibration's scale.

---

## Key findings

1. **Flatness ≈ 1.11 mm (non-circular).** Plane-fit RMS of the board's dense points.
   The board is known-flat, so this is pure reconstruction noise/distortion —
   independent of scale and of any calibration overlap. It barely varies across the
   volume (1.00–1.18 mm).

2. **The refractive model holds across the working volume (non-circular).** Board size
   and flatness are essentially constant across depth (1.27–1.35 m), lateral position,
   and tilt (2.6°–40.9°). Reconstructed square size varies by only **CV 0.0016**
   (±0.16 %). No depth- or angle-dependent drift — the contribution under test.

3. **Cross-camera agreement ≈ 1.82 mm (non-circular), uniform across poses.** Cameras
   that co-observe the board place the same corners within ~2 mm of each other, using
   only their own depth maps — and the per-frame RMS is uniform (1.5–2.1 mm) with **no
   dependence on tilt, depth, or camera count**. (Each pose is seen by a *subset* of the
   array by design — the rig images a volume larger than any one camera's field of view,
   so a camera seeing nothing is expected, not a failure.)

4. **Residual error is range-dominated (~3.4×) — a refraction signature.** Decomposing
   residuals into along-the-viewing-ray (range) vs perpendicular (lateral):
   range **1.78 mm** vs lateral **0.53 mm**, dominance **3.39×**, on every frame.
   In-plane geometric fidelity is sub-millimetre; the larger errors live along the
   line of sight, exactly where refraction acts. This is arguably the single strongest
   statement in the validation.

5. **Absolute scale is correct to +0.06 % — and this bounds dense-stage scale bias
   (weakly circular, not a tautology).** Reconstructed square size 60.018 mm vs the
   known 60 mm. The 60 mm square size is the *sole* metric anchor of the camera
   calibration (verified in the AquaCal source: the board's corners enter as fixed
   object points in metres; extrinsics, board poses, water distance, and intrinsics are
   all free; no independent baseline/ruler is used). So this measurement **cannot
   independently establish absolute scale** — that traces back to the board. *But* the
   dense MVS stage is one level removed: it reconstructs the corner spacing from
   photometric depth (RoMa/fusion/in-dense refraction), never from the board model. A
   dense stage with a systematic scale/depth bias would reconstruct the board at the
   wrong size *even with perfect calibration*. The +0.06 % agreement (CV 0.0016 across
   the volume) therefore **bounds any dense-stage scale bias to < 0.1 %** — a real, if
   secondary, result. (Caveat: correct triangulation over the calibrated baselines
   reproduces the board scale by construction, so ~unity is the expected null; the power
   is in detecting *deviation*. Independent absolute scale comes from the tank.)

6. **The direct depth-transfer method is the right primitive; the fallback is excluded.**
   Only **0.2 %** of detected corners (6 of 2,610) needed the plane-fit fallback;
   a further 29 (1.1 %) had neither direct depth nor a usable fallback. That fallback, though geometrically valid, proved cm-inaccurate and was the
   **dominant residual-error source** (see process note below), so all reported metrics
   use direct refractive-depth corners only (§3.2, not §3.3). This is what makes the
   cross-camera number uniform and the residual cloud clean.

---

## How the design's circularity concern was handled

- **Frame overlap was measured, not assumed.** Exactly **2 of 10** reconstructed board
  frames (raw 0 and 3930) coincided with calibration-fit frames; both were **excluded**.
  All metrics use the **8 genuinely held-out frames**.
- **Ordering is structural.** Every scale-independent metric is computed and locked
  **before** any scale-dependent alignment runs, so a scale error cannot be absorbed
  into the headline numbers. This was proven (the scale-independent artifacts are
  byte-identical before and after the alignment step).
- **Scale stated honestly.** Absolute scale is reported as a bound on dense-stage scale
  bias (weakly circular — it can't establish absolute scale independently), benchmarked
  against the **Maas (2015) factor-of-two** refractive precision penalty.

---

## Limitations & scope

- **Scale is weakly circular**: it bounds dense-stage scale bias but cannot establish
  absolute scale on its own (that traces to the board through calibration). Independent
  absolute scale comes from the separate tank measurement, which this pairs with.
- **Pathways and refraction ablation.** The headline numbers are the RoMa pathway. The
  LightGlue pathway and two pinhole ablations are evaluated on the same metrics in
  `data/results.modern_comparison/` (see `scripts/make_comparison_table.py`); the
  pathways are compared under an identical cross-camera depth filter, because the two
  save depth maps at different stages (`scripts/filter_depth_maps.py`).
- **8 board poses.** Good spatial/tilt spread, but a modest pose count; the two
  calibration-overlap poses were dropped to keep the set clean.
- **Not validated here:** the calibration itself (the board is its input), and
  inter-corner grid regularity (§4.4, deferred to v2).

## A finding from the process — the plane-fit fallback

The plane-fit fallback (used when direct depth is missing) turned out to be the one
weak link, and chasing it produced two corrections:

1. **Non-physical corners (fixed at source).** The fallback could emit corners *behind*
   the water interface (negative depth) from a degenerate seed plane, inflating one
   frame's cross-camera number ~85×. Root-caused, fixed (reject behind-camera/negative
   depth), gated, and regression-tested.

2. **Physical-but-imprecise fallback corners (excluded from metrics).** Even the
   *physically valid* fallback corners proved cm-inaccurate, and they were the **dominant
   driver of the apparent frame-to-frame error variation**. (Figures in this note are from
   the original analysis under the February 2026 calibration, where the effect was found.) Diagnosis: the per-corner
   *median* range error is flat at ~1.3 mm across all frames (no tilt/depth/camera trend),
   but a handful of fallback corners — 6 of 2605, mostly one camera — each contaminate
   their cross-camera consensus and manufacture apparent outliers, which RMS then
   amplifies. Excluding the fallback (direct-depth only) collapsed the per-frame RMS to a
   uniform 1.6–2.0 mm and dropped pooled cross-camera agreement from 3.46 → **1.87 mm**.

The lesson: at 0.2 % dropout the fallback is not worth its error cost, so all reported
metrics use direct refractive-depth corners. The numbers above are post-exclusion.

---

## Reproducing

One command regenerates every artifact (corner transfer → metrics → scale/alignment →
decomposition → table + figures + methods) from the extracted data:

```
python analysis/run_all.py --data-root <reconstruction> \
    --output-root data/analysis_output.modern_refractive --results-dir results
```

Artifacts: metrics JSON in the output root, figures in `<output root>/figures/`, text
deliverables in `results/`. The comparison table: `python scripts/make_comparison_table.py`.

---
*Generated 2026-06-30; numbers updated 2026-09-23 for the AquaCal 2.1.0 / AquaMVS 1.7.2
re-run. Numbers sourced from the computed artifacts; see `results/table.md` and
`results/methods.md`.*
