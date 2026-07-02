# AquaMVS_gtanalysis

Post-hoc ground-truth analysis for the AquaMVS reconstruction library via ChArUco board calibration targets.

This repository holds the analysis code that validates the geometric accuracy of the
AquaMVS underwater multi-view stereo (MVS) pipeline against independent ChArUco
calibration-board ground truth. The validation is non-circular: ground-truth corner
geometry is recovered from the calibration boards independently of the MVS reconstruction
it is used to assess.

## Reproducing the analysis with the archived dataset

The input imagery, calibration, full AquaMVS reconstruction output, and derived validation
artifacts are archived on Zenodo (~8.6 GB uncompressed):

**Dataset DOI:** https://doi.org/10.5281/zenodo.21134748 (concept DOI — always resolves to the latest version) · [Zenodo record](https://zenodo.org/records/21134749)

### 1. Get the code and the data

```bash
git clone https://github.com/McGrathLab/AquaMVS_gtanalysis.git
cd AquaMVS_gtanalysis
```

Download the archive from the Zenodo record above and extract it at the repository root.
The archive contains a top-level `data/` directory, so extracting here yields
`data/aquamvs_ground_truth_analysis/` (reconstruction inputs + output) and
`data/analysis_output/` (derived metrics and figures) exactly where the analysis expects
them:

```bash
# Any unzip tool works; a helper that also checks completeness is provided:
python scripts/extract_verify.py --data-root ./data --zip-path /path/to/downloaded.zip
```

### 2. Set up the environment

The analysis requires the pip-distributed `aquamvs` package (v1.5.2 was used to produce the
archived artifacts), which supplies the refractive projection model and evaluation hooks the
validation reuses. Follow the install instructions on the AquaMVS repository:

- **AquaMVS:** https://github.com/McGrathLab/AquaMVS

The commands below assume `aquamvs` is installed in a conda environment named `AquaMVS`;
adjust to match your setup.

```bash
conda run -n AquaMVS python analysis/entrypoint.py   # smoke-test: prints a dataset summary
```

### 3. Regenerate all metrics and figures

`analysis/run_all.py` is the single reproducible entrypoint. It re-runs every stage in
dependency order (corner transfer → flatness/consistency → cross-camera agreement → scale
alignment → error decomposition) and regenerates all deliverable tables and figures. It is
deterministic and safe to re-run — each stage overwrites its artifacts in place.

```bash
conda run -n AquaMVS python analysis/run_all.py
```

All regenerated artifacts are written under `data/analysis_output/` (JSON metrics,
`figures/` in PDF/PNG/SVG). Because the archive already ships these derived artifacts,
re-running lets you confirm the published numbers and figures reproduce from the raw inputs.

Useful flags:

```bash
conda run -n AquaMVS python analysis/run_all.py --data-root data/aquamvs_ground_truth_analysis
conda run -n AquaMVS python analysis/run_all.py --skip-metrics   # regenerate deliverables only
```
