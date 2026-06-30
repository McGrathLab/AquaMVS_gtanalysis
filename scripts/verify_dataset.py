"""
verify_dataset.py — Quick post-extraction sanity check for the AquaMVS ground-truth dataset.

Stdlib only. Run after extract_verify.py completes successfully.
"""
from pathlib import Path

root = Path('data/aquamvs_ground_truth_analysis')
assert root.exists(), f'data root missing: {root}'
assert (root / 'calibration.json').stat().st_size > 0, 'calibration.json empty'
assert (root / 'config.yaml').stat().st_size > 0, 'config.yaml empty'
frame_dirs = sorted((root / 'output').glob('frame_0000*'))
assert len(frame_dirs) == 10, f'Expected 10 output dirs, got {len(frame_dirs)}'
npz = list((frame_dirs[0] / 'depth_maps').glob('*.npz'))
assert len(npz) == 12, f'Expected 12 npz in frame_000000, got {len(npz)}'
assert (frame_dirs[0] / 'point_cloud' / 'fused.ply').stat().st_size > 0, 'fused.ply empty'
zip_path = Path('C:/Users/tucke/Downloads/aquamvs_ground_truth_analysis.zip')
assert not zip_path.exists(), f'Zip still present at {zip_path}'
print('DATASET VERIFIED — all checks passed')
