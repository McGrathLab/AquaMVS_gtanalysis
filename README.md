# AquaMVS_gtanalysis

**This repository reproduces every figure and number in the AquaMVS paper.**

Its core is the ground-truth analysis that validates the geometric accuracy of the
AquaMVS underwater multi-view stereo (MVS) pipeline against independent ChArUco
calibration-board ground truth. The validation is non-circular: ground-truth corner
geometry is recovered from the calibration boards independently of the MVS reconstruction
it is used to assess. It also holds the fish-present analyses (temporal repeatability, the
temporal median, the RoMa vs LightGlue comparison) and the generators for all manuscript
figures, so it draws on two datasets: the ground-truth board dataset and the fish-present
example dataset.

## Software versions

Every number in `results/` and in the paper comes from this stack:

| Component | Version | Source |
|---|---|---|
| AquaMVS | 1.7.2 (1.7.3 reproduces it bit for bit) | PyPI |
| AquaCal | 2.1.0 | PyPI |
| RoMa v2 | 2.0.1 + GPU-memory fix | `tlancaster6/RoMaV2@29ee427` (AquaMVS's pinned prerequisite) |
| LightGlue | `edb2b83` | `cvg/LightGlue` (AquaMVS's pinned prerequisite) |
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
```

`requirements.txt` pins everything above plus the libraries this repository imports.
LightGlue and RoMa v2 install from git because they are not on PyPI. It installs AquaMVS
1.7.3, which reproduces the 1.7.2 reconstruction behind the results bit for bit; its changes
are to installation, headless rendering and CPU device handling.

**Install RoMa v2 with `--no-deps`, in the order shown.** It declares `torchvision>=0.23.0`,
and letting pip resolve that replaces the torch 2.5.1 stack with a much newer one. The
results were produced with RoMa v2 installed without its dependencies: torchvision 0.20.1
and no `fused-local-corr`. `pip check` reports those two unmet requirements; that is
expected.
Reconstruction needs a CUDA GPU. Every run here used a 12 GB card, one run at a time.
Metric computation runs on the CPU.

**Figures** (section 3) need three system packages besides the Python environment: LaTeX
with Type 1 Computer Modern, so figure text matches the manuscript; Graphviz, for Fig. 1;
and the CMU Serif font. On Debian or Ubuntu:

```bash
sudo apt install texlive-latex-extra texlive-fonts-recommended cm-super dvipng graphviz fonts-cmu
```

The 3D mesh renders (Figs. 2 and 3) use Open3D's offscreen renderer, which needs a GPU with
EGL on Linux (it works without a display) or a desktop session.

## 1. Recompute the metrics from the archived reconstructions

This is the quick path: no GPU, no reconstruction.

**Dataset:** version 2.0.0 of the ground-truth dataset,
[10.5281/zenodo.23087547](https://doi.org/10.5281/zenodo.23087547). It holds the AquaCal
2.1.0 / AquaMVS 1.7.2 reconstructions behind every result here. (The concept DOI
[10.5281/zenodo.21134748](https://doi.org/10.5281/zenodo.21134748) resolves to the latest
version. Version 1.0.0 holds the February 2026 calibration and its AquaMVS 1.5.2
reconstruction; record 10.5281/zenodo.23086263 is an accidental duplicate of 1.0.0.)

The dataset comes as separate zips. Each extracts at the repository root into this
repository's own `data/` paths, so extract the ones you need side by side:

| Zip | Size | Contents |
|---|---|---|
| `aquamvs-gt-core.zip` | 0.26 GB | input frames and config (`data/aquamvs_ground_truth_analysis/`), every run's `data/analysis_output.*` and `data/results.*`, the comparison table, fish-present readouts (`data/runs_fish/`) |
| `aquamvs-gt-run-refractive.zip` | 5.80 GB | `data/runs/modern_refractive`, the reconstruction behind the paper's results |
| `aquamvs-gt-run-pinhole_B.zip` | 6.04 GB | `data/runs/modern_pinhole_B` (R2.1) |
| `aquamvs-gt-run-lightglue.zip` | 3.95 GB | `data/runs/modern_lightglue` (R2.2) |
| `aquamvs-gt-run-matchfilt.zip` | 0.81 GB | both `*_matchfilt` runs (R2.2); needs the refractive and LightGlue zips |

Each run directory holds its calibration and config and, per frame, the parts of AquaMVS's
output that the analysis and figures read (depth maps, fused point cloud, undistorted
images, mesh). Pinhole A ships as its calibration, config and analysis outputs only; its
reconstruction is regenerated as in section 2b.

```bash
git clone https://github.com/McGrathLab/AquaMVS_gtanalysis.git
cd AquaMVS_gtanalysis
unzip /path/to/aquamvs-gt-core.zip
unzip /path/to/aquamvs-gt-run-refractive.zip
python analysis/entrypoint.py --data-root data/runs/modern_refractive   # smoke test: dataset summary
```

`analysis/run_all.py` is the single entry point for the metrics. It runs every stage in
dependency order: corner transfer, then flatness and consistency, cross-camera agreement,
scale alignment and error decomposition. It then regenerates the tables and figures. It is
deterministic, and each stage overwrites its own artifacts.

```bash
# writes data/analysis_output/ and results/; compare with the shipped data/analysis_output.modern_refractive
python analysis/run_all.py --data-root data/runs/modern_refractive
python analysis/run_all.py --data-root data/runs/modern_refractive --skip-metrics   # deliverables only
```

The other runs work the same way; section 2d has the loop that writes each run's
`data/analysis_output.<run>` and `data/results.<run>`. Run on the extracted dataset, it
reproduces the shipped tables byte for byte (checked for `modern_refractive` and
`modern_lightglue_matchfilt`).

## 2. Reproduce everything from the raw inputs

This path regenerates the calibrations, all reconstructions and every table behind the
reviewer-response results. The comparison runs are the refractive vs pinhole ablation
(R2.1), RoMa vs LightGlue (R2.2), and the temporal-median and temporal-coverage readouts
(R1.5, R2.3). Budget about an hour of CPU for the pinhole calibration fit and about 3.5
hours of GPU time for the reconstructions.

A clean environment built as above reproduces this repository's refractive reconstruction
bit for bit: identical depth maps and fused point counts.

**Inputs:**
- the GT dataset's core zip (section 1): its `frames/` and `config.yaml` (in `data/aquamvs_ground_truth_analysis/`);
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

To run the interface-sensitivity check, also analyze the February 2026 reconstruction. It
ships in version 1.0.0 of the GT dataset
([10.5281/zenodo.21134749](https://doi.org/10.5281/zenodo.21134749)), whose single
`data.zip` extracts to `data/aquamvs_ground_truth_analysis/` (check it with
`scripts/extract_verify.py`). Analyze it with `--data-root data/aquamvs_ground_truth_analysis`,
pass its output root as a further `--root`, then add `--pair <that name> refractive`.

### 2e. Fish-present sequence (R1.5, R2.2, R2.3)

These runs use session 021826 from the AquaMVS example dataset, version 1.3.0
([10.5281/zenodo.23086258](https://doi.org/10.5281/zenodo.23086258); concept
[10.5281/zenodo.18702024](https://doi.org/10.5281/zenodo.18702024)). They use its
temporal-median frames `images/filtered/` (frames 1799 to 8999, 5 frames), `masks/`, the raw
frame 1799 in `images/raw/`, and `config_paper.yaml`. That is the paper's 021826 config,
which differs from the example dataset's tutorial `config.yaml`: it uses `voxel_size` 0.0005
and `poisson_depth` 10. Each run below is identical to the published benchmark run for its
arm apart from paths.

```bash
EX=/path/to/aquamvs-example-dataset
CFG=$EX/config_paper.yaml          # the paper's 021826 config
RAW=$EX/images/raw                 # one subdirectory per camera, frame_001799.png

# RoMa, the five median frames (R2.3; RoMa arm of Fig. 2 and of the point-count comparison)
python scripts/make_run_dir.py data/runs_fish/modern_run5_filtered --config $CFG \
    --calibration $REFR --frames $EX/images/filtered --masks $EX/masks
# RoMa, the raw frame 1799 (R1.5)
python scripts/make_run_dir.py data/runs_fish/modern_run3_raw --config $CFG \
    --calibration $REFR --frames $RAW --masks $EX/masks
# LightGlue on median frame 1799: full pathway, and sparse mode (R2.2 point counts, Fig. 2)
python scripts/make_run_dir.py data/runs_fish/modern_lg_full --config $CFG --calibration $REFR \
    --frames $EX/images/filtered --masks $EX/masks --matcher lightglue --frame-stop 1
python scripts/make_run_dir.py data/runs_fish/modern_lg_sparse --config $CFG --calibration $REFR \
    --frames $EX/images/filtered --masks $EX/masks --matcher lightglue --pipeline-mode sparse --frame-stop 1

for r in modern_run5_filtered modern_run3_raw modern_lg_full modern_lg_sparse; do
    (cd data/runs_fish/$r && aquamvs run config.yaml)
done
```

Readouts:

```bash
# R2.3: coverage, repeatability, the large-error tail and the signed drift, four consecutive pairs
python scripts/temporal_coverage.py data/runs_fish/modern_run5_filtered \
    --json data/runs_fish/modern_run5_filtered/temporal_coverage.json

# R1.5: the temporal median on vs off, frame 1799
python scripts/median_comparison.py \
    data/runs_fish/modern_run5_filtered/output/frame_000000/point_cloud/fused.ply \
    data/runs_fish/modern_run3_raw/output/frame_000000/point_cloud/fused.ply
```

The fused point counts of the RoMa, LightGlue-full and LightGlue-sparse arms are in each run's
`output/frame_000000/point_cloud/` (`fused.ply`, or `sparse.ply` in sparse mode).
The temporal-median frames are trailing 1800-frame (60 s) medians of the raw video.

The GT dataset's core zip ships these readouts without the reconstructions: each fish-present
run's `config.yaml`, `run.log`, `temporal_coverage.json` / `median_comparison.json`, and every
run's fused point counts in `data/runs_fish/point_counts.json`.

## 3. Figures

Every manuscript figure, under its manuscript filename, with a `MANIFEST.md` mapping each
figure to its generator and inputs:

```bash
python analysis/make_figures.py                   # -> results/figures/
python analysis/make_figures.py --only fig3 figS1 # a subset
```

This reads the runs and analysis outputs from sections 2b to 2e, and takes about a minute
on a GPU machine. From the GT dataset alone (core plus refractive zips), the board figures
render; the fish-present figures (Figs. 2 and S1, the median figure) need the section 2e
runs. Figure text is LaTeX Computer Modern; without LaTeX the command stops,
rather than silently switch to another font (`--allow-font-fallback` for a draft). The
individual generators are in `analysis/deliverables/fig_*.py`, each runnable on its own.

## Other tools

- `scripts/compare_reconstructions.py`: compares two reconstruction trees frame by frame
  (depth validity, depth difference, fused point counts). Useful to confirm a re-run
  reproduces an archived one.
- `scripts/verify_dataset.py`, `scripts/verify_loader.py`: dataset integrity checks.
