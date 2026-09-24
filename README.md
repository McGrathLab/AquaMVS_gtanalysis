# AquaMVS_gtanalysis

Post-hoc ground-truth analysis for the AquaMVS reconstruction library via ChArUco board calibration targets.

This repository holds the analysis code that validates the geometric accuracy of the
AquaMVS underwater multi-view stereo (MVS) pipeline against independent ChArUco
calibration-board ground truth. The validation is non-circular: ground-truth corner
geometry is recovered from the calibration boards independently of the MVS reconstruction
it is used to assess.

## Software versions

Every number in `results/` and in the paper comes from this stack:

| Component | Version | Source |
|---|---|---|
| AquaMVS | 1.7.2 | `git+https://github.com/McGrathLab/AquaMVS.git@v1.7.2` |
| AquaCal | 2.1.0 | PyPI |
| RoMa v2 | 2.0.1 + GPU-memory fix | `tlancaster6/RoMaV2@29ee427` (AquaMVS 1.7.2's pinned prerequisite) |
| LightGlue | `edb2b83` | `cvg/LightGlue` (AquaMVS 1.7.2's pinned prerequisite) |
| PyTorch | 2.5.1 (CUDA 12.1) | pytorch.org |
| Python | 3.12 | |

The calibration is the AquaCal paper's own: `reference_outputs/calibration.json` from the
AquaCal real-rig results package ([Record B, 10.5281/zenodo.22117061](https://doi.org/10.5281/zenodo.22117061)).
Refitting it with AquaCal 2.1.0 from `config_paper.yaml` on the Record A frames reproduces
it bit for bit.

## Environment

```bash
conda create -n aquamvs-gt python=3.12 && conda activate aquamvs-gt
pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu121
pip install --no-deps -r requirements-romav2.txt
pip install -r requirements.txt
python -m pytest -q tests          # 26 tests
python analysis/entrypoint.py      # smoke test: prints a dataset summary
```

`requirements.txt` pins everything above plus the libraries this repository imports.
LightGlue and RoMa v2 install from git because they are not on PyPI. AquaMVS 1.7.2 also
installs from its git tag, because PyPI stops at 1.7.1 (the same source code).

**Install RoMa v2 with `--no-deps`, in the order shown.** It declares `torchvision>=0.23.0`,
and letting pip resolve that replaces the torch 2.5.1 stack with a much newer one. The
results were produced with RoMa v2 installed without its dependencies: torchvision 0.20.1
and no `fused-local-corr`. `pip check` reports those two unmet requirements; that is
expected.
Reconstruction needs a CUDA GPU. Every run here used a 12 GB card, one run at a time.
Metric computation runs on the CPU.

## 1. Recompute the metrics from the archived reconstruction

This is the quick path: no GPU, no reconstruction.

**Dataset DOI:** https://doi.org/10.5281/zenodo.21134748 (concept DOI, which always resolves to the latest version)

<!-- TODO(release): name the Zenodo version that ships the AquaCal 2.1.0 / AquaMVS 1.7.2
     reconstruction once it is published, and say which earlier version holds the
     February 2026 calibration / AquaMVS 1.5.2 reconstruction. -->

Download the archive and extract it at the repository root. It contains a top-level `data/`,
which yields `data/aquamvs_ground_truth_analysis/` (frames, config, calibration,
reconstruction output) and `data/analysis_output/` (derived metrics and figures):

```bash
git clone https://github.com/McGrathLab/AquaMVS_gtanalysis.git
cd AquaMVS_gtanalysis
python scripts/extract_verify.py --data-root ./data --zip-path /path/to/downloaded.zip
```

`analysis/run_all.py` is the single entry point for the metrics. It runs every stage in
dependency order: corner transfer, then flatness and consistency, cross-camera agreement,
scale alignment and error decomposition. It then regenerates the tables and figures. It is
deterministic, and each stage overwrites its own artifacts.

```bash
python analysis/run_all.py                    # writes data/analysis_output/ and results/
python analysis/run_all.py --skip-metrics     # regenerate the deliverables only
```

## 2. Reproduce everything from the raw inputs

This path regenerates the calibrations, all reconstructions and every table behind the
reviewer-response results. The comparison runs are the refractive vs pinhole ablation
(R2.1), RoMa vs LightGlue (R2.2), and the temporal-median and temporal-coverage readouts
(R1.5, R2.3). Budget about an hour of CPU for the pinhole calibration fit and about 3.5
hours of GPU time for the reconstructions.

A clean environment built as above reproduces this repository's refractive reconstruction
bit for bit: identical depth maps and fused point counts.

**Inputs:**
- the GT dataset above: its `frames/` and `config.yaml` (from `data/aquamvs_ground_truth_analysis/`);
- AquaCal Record B ([10.5281/zenodo.22117061](https://doi.org/10.5281/zenodo.22117061)): the refractive calibration, and `config_paper.yaml`;
- AquaCal Record A ([10.5281/zenodo.22116461](https://doi.org/10.5281/zenodo.22116461), 4.3 GB): calibration frames, needed only for the pinhole refit.

```bash
GT=data/aquamvs_ground_truth_analysis
REFR=/path/to/record_b/reference_outputs/calibration.json
```

### 2a. Pinhole-ablation calibrations (R2.1)

Pinhole B is AquaCal's own fit with refraction off. Copy `config_paper.yaml` into the
extracted Record A directory (its paths are relative to the working directory), set
`interface.n_water: 1.0`, and fit it there:

```bash
cd /path/to/record_a && python /path/to/AquaMVS_gtanalysis/scripts/fit_pinhole_calibration.py config_pinhole.yaml
```

Use this script, not plain `aquacal calibrate`. At `n_water = 1` the fitted interface height
is unidentifiable, and it drifts to 1 cm below the cameras. Against that height AquaCal
fails to register the auxiliary camera `e3v8250`, which silently costs every ring camera
about a third of its depth. The script's docstring has the details.

Then build both ablation calibrations. Pinhole A is the refractive calibration with only
`n_water` set to 1. Pinhole B is the fit above, with the unidentifiable `water_z` pinned to
0.5 m, which has no optical effect:

```bash
python scripts/make_ablation_calibrations.py --refractive $REFR \
    --pinhole-fit /path/to/record_a/output/calibration.json \
    --out-a cal_pinhole_A.json --out-b cal_pinhole_B.json
```

### 2b. Board reconstructions

Each run is a directory holding the GT config (with only its paths rewritten), a calibration
and a link to the frames:

```bash
python scripts/make_run_dir.py data/runs/modern_refractive --config $GT/config.yaml --calibration $REFR --frames $GT/frames
python scripts/make_run_dir.py data/runs/modern_pinhole_B  --config $GT/config.yaml --calibration cal_pinhole_B.json --frames $GT/frames
python scripts/make_run_dir.py data/runs/modern_pinhole_A  --config $GT/config.yaml --calibration cal_pinhole_A.json --frames $GT/frames
python scripts/make_run_dir.py data/runs/modern_lightglue  --config $GT/config.yaml --calibration $REFR --frames $GT/frames --matcher lightglue

for r in modern_refractive modern_pinhole_B modern_pinhole_A modern_lightglue; do
    (cd data/runs/$r && aquamvs run config.yaml)      # about 25-35 min each on the GPU
done
```

### 2c. Matched depth filtering (R2.2)

The two matchers save depth maps at different stages. RoMa saves them after its own
consistency filter; LightGlue saves raw plane-sweep depths and filters only at fusion. To
compare like with like, apply AquaMVS's own cross-camera filter to both:

```bash
python scripts/filter_depth_maps.py data/runs/modern_refractive data/runs/modern_refractive_matchfilt
python scripts/filter_depth_maps.py data/runs/modern_lightglue  data/runs/modern_lightglue_matchfilt
```

### 2d. Metrics, comparison table and statistics

```bash
for r in modern_refractive modern_pinhole_B modern_pinhole_A modern_refractive_matchfilt modern_lightglue_matchfilt; do
    python analysis/run_all.py --data-root data/runs/$r \
        --output-root data/analysis_output.$r --results-dir data/results.$r
done

# the committed results/ come from the refractive run
python analysis/run_all.py --data-root data/runs/modern_refractive \
    --output-root data/analysis_output.modern_refractive --results-dir results --skip-metrics

# five-column comparison table -> data/results.modern_comparison/table.{md,tex,csv}
python scripts/make_comparison_table.py

# per-frame mean, SD and 95% CI (R1.3) and the tilt breakdown (R2.1)
python scripts/revision_stats.py \
    --root refractive=data/analysis_output.modern_refractive \
    --root pinhole_B=data/analysis_output.modern_pinhole_B \
    --root pinhole_A=data/analysis_output.modern_pinhole_A \
    --json data/results.modern_comparison/revision_stats.json
```

To run the interface-sensitivity check, also analyze the February 2026 reconstruction
shipped in the archive (`--data-root data/aquamvs_ground_truth_analysis`). Pass its output
root as a further `--root`, then add `--pair <that name> refractive`.

### 2e. Fish-present sequence (R1.5, R2.3)

These runs use session 021826 from the AquaMVS example dataset
([10.5281/zenodo.18702024](https://doi.org/10.5281/zenodo.18702024)): its temporal-median
frames `images/filtered/` (frames 1799 to 8999, 5 frames) and `masks/`. The reconstruction
config is the paper's 021826 config, which differs from the example dataset's `config.yaml`:
it uses `voxel_size` 0.0005 and `poisson_depth` 10.

<!-- TODO(release): the paper's 021826 config is not yet in any public archive; point at
     it here once the example dataset's new version ships it. -->

```bash
EX=/path/to/aquamvs-example-dataset
python scripts/make_run_dir.py runs_fish/modern_run5_filtered --config config_021826.yaml \
    --calibration $REFR --frames $EX/images/filtered --masks $EX/masks
(cd runs_fish/modern_run5_filtered && aquamvs run config.yaml)

# R2.3: coverage, repeatability and the large-error tail over the four consecutive pairs
python scripts/temporal_coverage.py runs_fish/modern_run5_filtered --json runs_fish/modern_run5_filtered/temporal_coverage.json
```

The temporal-median frames are trailing 1800-frame (60 s) medians of the raw video. R1.5
compares the median frame 1799 against the raw frame 1799, reconstructed the same way:

```bash
python scripts/median_comparison.py \
    runs_fish/modern_run5_filtered/output/frame_000000/point_cloud/fused.ply \
    runs_fish/modern_run3_raw/output/frame_000000/point_cloud/fused.ply
```

<!-- TODO(release): the raw frame-1799 images come from the session's raw video, which is
     not in a public archive yet. -->

## Other tools

- `scripts/compare_reconstructions.py`: compares two reconstruction trees frame by frame
  (depth validity, depth difference, fused point counts). Useful to confirm a re-run
  reproduces an archived one.
- `scripts/verify_dataset.py`, `scripts/verify_loader.py`: dataset integrity checks.
