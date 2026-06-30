# Requirements: AquaMVS ChArUco Ground-Truth Validation

**Defined:** 2026-06-30
**Core Value:** Produce defensible, non-circular accuracy numbers for the AquaMVS dense stage — led by flatness and spatial/angular consistency — that hold up in the manuscript.

## v1 Requirements

Requirements for the headline-first validation. Each maps to roadmap phases.

### Data & Setup

- [x] **DATA-01**: Input dataset is extracted into `./data/` (gitignored); the Downloads zip is deleted only after extraction is verified complete
- [x] **DATA-02**: Analysis loads calibration (camera params, refractive interface, board spec) and per-camera/per-frame depth maps + fused clouds from the extracted data
- [x] **DATA-03**: The validation set is the 8 held-out frames; output indices 0 and 5 (raw frames 0 and 3930) are excluded from every reported metric
- [x] **DATA-04**: Analysis runs in the `AquaMVS` conda env with `aquamvs` v1.5.2 importable and a single documented entrypoint

### Corner Transfer

- [x] **XFER-01**: ChArUco corners are detected subpixel in each camera's image, reusing the AquaCal detector for the known board (12×9, 60 mm squares, DICT_5X5_100)
- [ ] **XFER-02**: Each detected corner pixel samples the camera's MVS depth map (bilinear) and back-projects through `RefractiveProjectionModel.cast_ray` to a 3D corner in the MVS frame
- [ ] **XFER-03**: A plane-fit fallback evaluates corners with missing/weak depth on the board plane fit from dense points
- [ ] **XFER-04**: Corner-depth dropout rate is measured and reported (determines reliance on direct depth vs plane-fit)

### Metrics

- [ ] **MET-01**: Flatness (§4.1) — plane-fit RMS of the board's dense points, per frame, computed before any scaling step
- [ ] **MET-02**: Spatial/angular consistency (§4.2) — board size and flatness measured per frame and reported as variation across position, depth, and tilt over the working volume
- [ ] **MET-03**: Cross-camera agreement (§4.3) — quantify whether each camera's depth places the board and transferred corners at a consistent 3D location
- [ ] **MET-04**: Absolute scale (§4.5) — reconstructed square size vs known 60 mm, reported as a consistency check with circularity stated and the Maas (2015) factor-of-two context
- [ ] **MET-05**: Rigid alignment (ICP/Umeyama) of MVS corners to the ideal planar board with inlier RMSE per position; scale-independent metrics reported before any scaling so they cannot absorb scale error

### Deliverables

- [ ] **OUT-01**: Results table — per metric: value and whether it is scale-independent (non-circular) or a consistency check
- [ ] **OUT-02**: Spatial-consistency figure — flatness + size vs working-volume position — styled to match DissertationFigures conventions
- [ ] **OUT-03**: Per-camera board-localization agreement output
- [ ] **OUT-04**: Drafted methods paragraph — known-geometry target, measured 2-of-10 overlap + exclusion of the 8 held-out frames, corner transfer through refractive depth maps, scale-independent metrics led, scale as consistency check; cites de Jesus (method), Menna & Nocerino (domain), Maas (benchmark)
- [ ] **OUT-05**: Analysis is reproducible — one entrypoint regenerates all artifacts from the extracted data

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Additional Metrics

- **GRID-01**: Inter-corner spacing / grid regularity (§4.4) vs known square size — local scale/distortion check
- **XPATH-01**: Cross-pathway agreement (§4.6) — RoMa vs LightGlue on the same board (requires a second reconstruction not in the provided data)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Recalibration / rerunning AquaMVS reconstruction | Locked (§2.4); overlap measured exactly as 2 of 10 frames, 8 held-out frames suffice |
| Validating the calibration itself | Board square size is a calibration input (scale anchor); confirming it is partly circular |
| Frames 0 and 3930 (indices 0, 5) in metrics | Coincide with calibration-fit frames; retained on disk but excluded from all metrics |
| Pure-cloud / orthophoto corner detection (§3.4) | Backup only; build only if depth-based corner transfer fails |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Complete |
| DATA-02 | Phase 1 | Complete |
| DATA-03 | Phase 1 | Complete |
| DATA-04 | Phase 1 | Complete |
| XFER-01 | Phase 2 | Complete |
| XFER-02 | Phase 2 | Pending |
| XFER-03 | Phase 2 | Pending |
| XFER-04 | Phase 2 | Pending |
| MET-01 | Phase 3 | Pending |
| MET-02 | Phase 3 | Pending |
| MET-03 | Phase 3 | Pending |
| MET-04 | Phase 4 | Pending |
| MET-05 | Phase 4 | Pending |
| OUT-01 | Phase 5 | Pending |
| OUT-02 | Phase 5 | Pending |
| OUT-03 | Phase 5 | Pending |
| OUT-04 | Phase 5 | Pending |
| OUT-05 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 18 total
- Mapped to phases: 18 ✓
- Unmapped: 0

---
*Requirements defined: 2026-06-30*
*Last updated: 2026-06-30 after roadmap creation (traceability populated)*
