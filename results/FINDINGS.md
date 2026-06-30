# AquaMVS ChArUco Ground-Truth Validation — Findings & Conclusions

*Plain-language summary of what the validation found and what it means. Numbers are
read from the computed artifacts in `data/analysis_output/`; the manuscript-ready
prose is in `results/methods.md`, the metric table in `results/table.md`.*

---

## Bottom line

The AquaMVS dense reconstruction is **metric-grade through water**. Across 8 held-out
ChArUco-board poses spanning the working volume, the reconstructed board is **flat to
~1.1 mm**, its **square size is correct to ~0.04 %**, independent cameras place the same
board points to **~3.5 mm**, and the reconstructed corner grid matches the ideal 60 mm
board to **~1.05 mm** after rigid alignment. What residual error remains is **range
(depth) error, not lateral** — the expected signature of refraction, and small.

The headline accuracy claims rest on **scale-independent (non-circular)** metrics, so
they are not an artifact of the board having set the calibration's scale.

---

## Key findings

1. **Flatness ≈ 1.09 mm (non-circular).** Plane-fit RMS of the board's dense points.
   The board is known-flat, so this is pure reconstruction noise/distortion —
   independent of scale and of any calibration overlap. It barely varies across the
   volume (0.99–1.15 mm).

2. **The refractive model holds across the working volume (non-circular).** Board size
   and flatness are essentially constant across depth (1.26–1.42 m), lateral position,
   and tilt (2.8°–40.7°). Reconstructed square size varies by only **CV 0.0016**
   (±0.15 %). No depth- or angle-dependent drift — the contribution under test.

3. **Cross-camera agreement ≈ 3.46 mm (non-circular).** Cameras that co-observe the
   board place the same corners within a few mm of each other, using only their own
   depth maps. (Each pose is seen by a *subset* of the array by design — the rig images
   a volume larger than any one camera's field of view, so a camera seeing nothing is
   expected, not a failure.)

4. **Residual error is range-dominated (~4.4×) — a refraction signature.** Decomposing
   residuals into along-the-viewing-ray (range) vs perpendicular (lateral):
   range **3.64 mm** vs lateral **0.82 mm**, dominance **4.41×**, on every frame.
   In-plane geometric fidelity is sub-millimetre; the larger errors live along the
   line of sight, exactly where refraction acts. This is arguably the single strongest
   statement in the validation.

5. **Absolute scale is correct to +0.04 % — and this bounds dense-stage scale bias
   (weakly circular, not a tautology).** Reconstructed square size 60.013 mm vs the
   known 60 mm. The 60 mm square size is the *sole* metric anchor of the camera
   calibration (verified in the AquaCal source: the board's corners enter as fixed
   object points in metres; extrinsics, board poses, water distance, and intrinsics are
   all free; no independent baseline/ruler is used). So this measurement **cannot
   independently establish absolute scale** — that traces back to the board. *But* the
   dense MVS stage is one level removed: it reconstructs the corner spacing from
   photometric depth (RoMa/fusion/in-dense refraction), never from the board model. A
   dense stage with a systematic scale/depth bias would reconstruct the board at the
   wrong size *even with perfect calibration*. The +0.04 % agreement (CV 0.0016 across
   the volume) therefore **bounds any dense-stage scale bias to < 0.1 %** — a real, if
   secondary, result. (Caveat: correct triangulation over the calibrated baselines
   reproduces the board scale by construction, so ~unity is the expected null; the power
   is in detecting *deviation*. Independent absolute scale comes from the tank.)

6. **The direct depth-transfer method is the right primitive.** Only **0.2 %** of
   detected corners lacked valid depth and needed the plane-fit fallback, so the
   analysis leans confidently on direct refractive back-projection (§3.2), not the
   fallback (§3.3).

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
- **One reconstruction pathway.** Validated on the RoMa pathway only; cross-pathway
  agreement (RoMa vs LightGlue) is deferred to v2 (needs a second reconstruction).
- **8 board poses.** Good spatial/tilt spread, but a modest pose count; the two
  calibration-overlap poses were dropped to keep the set clean.
- **Not validated here:** the calibration itself (the board is its input), and
  inter-corner grid regularity (§4.4, deferred to v2).

## A finding from the process

During validation a latent bug surfaced: the plane-fit fallback could emit
**non-physical corners** (behind the water interface, negative depth) from a
degenerate seed plane, which inflated one frame's cross-camera number ~85×. It was
root-caused, fixed at the source (reject behind-camera/negative-depth solutions),
gated defensively in the metrics, and covered by regression tests. The corrected
numbers above are what stand.

---

## Reproducing

One command regenerates every artifact (corner transfer → metrics → scale/alignment →
decomposition → table + figures + methods) from the extracted data:

```
conda run -n AquaMVS python analysis/run_all.py
```

Artifacts: metrics JSON in `data/analysis_output/`, figures in
`data/analysis_output/figures/`, text deliverables in `results/`.

---
*Generated 2026-06-30. Numbers sourced from the computed artifacts; see `results/table.md`
and `results/methods.md`.*
