# Roadmap: AquaMVS ChArUco Ground-Truth Validation

## Overview

This project assembles existing `aquamvs` v1.5.2 hooks (plus a thin corner-transfer glue layer) into a reproducible analysis that grades the AquaMVS dense reconstruction against a known-geometry ChArUco board. The journey runs along the natural data dependency: stand up the environment and load the extracted dataset, transfer image-detected ChArUco corners into the MVS frame through the refractive depth maps, compute the headline scale-independent metrics (flatness, spatial/angular consistency, cross-camera agreement) before any scaling can absorb error, then run the honest absolute-scale and alignment consistency checks, and finally assemble everything into manuscript artifacts from a single entrypoint. The structure is sequenced so the non-circular metrics are produced and locked before the scale check ever runs.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Data & Environment** - Extract the dataset and stand up a reproducible loader in the AquaMVS env (completed 2026-06-30)
- [x] **Phase 2: Corner Transfer** - Move image-detected ChArUco corners into the MVS frame through refractive depth maps (completed 2026-06-30)
- [ ] **Phase 3: Scale-Independent Metrics** - Compute flatness, spatial consistency, and cross-camera agreement before any scaling
- [ ] **Phase 4: Scale Check & Alignment** - Report absolute scale and rigid alignment as honest consistency checks
- [ ] **Phase 5: Manuscript Deliverables** - Assemble the table, figure, per-camera output, and methods paragraph from one entrypoint

## Phase Details

### Phase 1: Data & Environment
**Goal**: A reproducible analysis environment with the input dataset extracted and loadable through a single documented entrypoint.
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04
**Success Criteria** (what must be TRUE):
  1. The dataset is extracted into `./data/` (gitignored) and extraction is verified complete before the Downloads zip is deleted.
  2. A documented entrypoint runs in the `AquaMVS` conda env with `aquamvs` v1.5.2 importable.
  3. The loader returns calibration (camera params, refractive interface, board spec), per-camera/per-frame depth maps, and fused clouds from the extracted data.
  4. The validation set resolves to the 8 held-out frames with output indices 0 and 5 (raw frames 0 and 3930) excluded.
**Plans**: 2 plans

Plans:
- [ ] 01-01-PLAN.md — Extract dataset to `./data/`, manifest-verify completeness, gitignore, delete source zip after verification
- [ ] 01-02-PLAN.md — Build GroundTruthDataset loader + single documented entrypoint (calibration, depth maps, clouds, held-out frame selection, e3v8250 handling)

### Phase 2: Corner Transfer
**Goal**: Image-detected ChArUco corners are placed as 3D points in the MVS frame via refractive back-projection through the depth maps, with a measured dropout rate.
**Depends on**: Phase 1
**Requirements**: XFER-01, XFER-02, XFER-03, XFER-04
**Success Criteria** (what must be TRUE):
  1. ChArUco corners are detected subpixel in each camera's image using the reused AquaCal detector for the known board (12x9, 60 mm, DICT_5X5_100).
  2. Each detected corner pixel samples its camera's MVS depth map (bilinear) and back-projects through `RefractiveProjectionModel.cast_ray` to a 3D corner.
  3. Corners with missing or weak depth fall back to the board plane fit from dense points.
  4. Per-frame, per-camera corner-depth dropout rate is computed and reported.
**Plans**: 2 plans

Plans:
- [ ] 02-01-PLAN.md — Subpixel ChArUco detection per depth-bearing camera on undistorted images (AquaCal detector reuse) [XFER-01]
- [ ] 02-02-PLAN.md — Depth sampling + refractive back-projection (cast_ray, K_new) with board-plane-fit fallback and per-frame/per-camera dropout report [XFER-02, XFER-03, XFER-04]

### Phase 3: Scale-Independent Metrics
**Goal**: The headline non-circular accuracy numbers — flatness, spatial/angular consistency, and cross-camera agreement — computed before any scaling or alignment step.
**Depends on**: Phase 2
**Requirements**: MET-01, MET-02, MET-03
**Success Criteria** (what must be TRUE):
  1. Per-frame plane-fit RMS flatness of the board's dense points is computed with no scaling applied.
  2. Board size and flatness variation across position, depth, and tilt over the working volume is measured and reported per frame.
  3. Cross-camera agreement quantifies whether each camera's depth places the board and transferred corners at a consistent 3D location.
  4. All three metrics are produced and recorded before any alignment or scaling step runs.
**Plans**: 2 plans

Plans:
- [ ] 03-01-PLAN.md — Flatness (RANSAC+SVD plane-fit RMS, MET-01) + spatial/angular consistency across the working volume (MET-02) [dense cloud + corners]
- [ ] 03-02-PLAN.md — Cross-camera board-localization agreement (MET-03) [sparse corners.npz]

### Phase 4: Scale Check & Alignment
**Goal**: Absolute scale and rigid alignment reported honestly as consistency checks, run only after the scale-independent metrics are locked.
**Depends on**: Phase 3
**Requirements**: MET-04, MET-05
**Success Criteria** (what must be TRUE):
  1. Rigid (no-scale) alignment of MVS corners to the ideal planar board yields inlier RMSE per position.
  2. Reconstructed square size vs the known 60 mm is computed and labeled explicitly as a consistency check with circularity stated.
  3. The scale result is contextualized against the Maas (2015) factor-of-two refractive precision benchmark (not framed as "0.5 %").
  4. These steps run only after Phase 3's scale-independent metrics are computed and recorded.
**Plans**: TBD (~1 plan)

Plans:
- [ ] 04-01: Rigid alignment (ICP/Umeyama, no scale) + absolute scale consistency check with Maas benchmark context

### Phase 5: Manuscript Deliverables
**Goal**: All metrics assembled into manuscript-ready artifacts — results table, spatial-consistency figure, per-camera output, and methods paragraph — regenerable from one reproducible entrypoint.
**Depends on**: Phase 4
**Requirements**: OUT-01, OUT-02, OUT-03, OUT-04, OUT-05
**Success Criteria** (what must be TRUE):
  1. A results table lists each metric's value and whether it is scale-independent (non-circular) or a consistency check.
  2. A spatial-consistency figure (flatness + size vs working-volume position) is rendered in DissertationFigures style.
  3. A per-camera board-localization agreement output is produced.
  4. A drafted methods paragraph covers the known target, the measured 2-of-10 overlap and 8 held-out frames, corner transfer through refractive depth maps, scale-independent metrics led, and scale as a consistency check, citing de Jesus, Menna & Nocerino, and Maas.
  5. One entrypoint regenerates all artifacts from the extracted data.
**Plans**: TBD (~2 plans)

Plans:
- [ ] 05-01: Results table + spatial-consistency figure + per-camera agreement output (DissertationFigures style)
- [ ] 05-02: Drafted methods paragraph + single-entrypoint reproducibility wiring

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Data & Environment | 2/2 | Complete   | 2026-06-30 |
| 2. Corner Transfer | 2/2 | Complete   | 2026-06-30 |
| 3. Scale-Independent Metrics | 0/2 | Planned | - |
| 4. Scale Check & Alignment | 0/1 | Not started | - |
| 5. Manuscript Deliverables | 0/2 | Not started | - |
