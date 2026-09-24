"""
Verification script for analysis/loader.py.
Run from the repo root:
    python scripts/verify_loader.py
"""

import sys
sys.path.insert(0, '.')

from analysis.loader import GroundTruthDataset, DatasetConfig, BoardSpec, FrameInfo

ds = GroundTruthDataset()

# --- Calibration ---
calib = ds.calibration()
assert len(calib.cameras) == 13, f'Expected 13 cameras, got {len(calib.cameras)}'
print(f'[PASS] calibration: {len(calib.cameras)} cameras')

# --- Board spec ---
spec = ds.board_spec()
assert spec.squares_x == 12 and spec.squares_y == 9, f'Bad board spec: {spec}'
assert abs(spec.square_size - 0.06) < 1e-6, f'Bad square_size: {spec.square_size}'
assert abs(spec.marker_size - 0.045) < 1e-6, f'Bad marker_size: {spec.marker_size}'
assert spec.dict_name == 'DICT_5X5_100', f'Bad dict_name: {spec.dict_name}'
print(f'[PASS] board spec: {spec}')

# --- Validation frames ---
val = ds.validation_frames()
assert len(val) == 8, f'Expected 8 validation frames, got {len(val)}'
assert all(f.output_idx not in {0, 5} for f in val), 'Calibration overlap frame in validation set'
print(f'[PASS] validation_frames: {len(val)} frames, indices={[f.output_idx for f in val]}')

# --- All frames ---
all_f = ds.all_frames()
assert len(all_f) == 10, f'Expected 10 total frames, got {len(all_f)}'
overlap = [f for f in all_f if f.is_calibration_overlap]
assert len(overlap) == 2, f'Expected 2 calibration-overlap frames, got {len(overlap)}'
assert all(f.output_idx in {0, 5} for f in overlap), f'Wrong overlap indices: {[f.output_idx for f in overlap]}'
print(f'[PASS] all_frames: {len(all_f)} frames, {len(overlap)} calibration-overlap')

# --- e3v8250 depth map returns None ---
p = ds.depth_map_path(all_f[0], 'e3v8250')
assert p is None, f'e3v8250 depth_map_path should be None, got {p}'
arr = ds.load_depth_map(all_f[0], 'e3v8250')
assert arr is None, f'e3v8250 load_depth_map should return None, got {arr}'
print('[PASS] e3v8250 depth map returns None (no crash)')

# --- Fused cloud path exists ---
cloud = ds.fused_cloud_path(val[0])
assert cloud.exists(), f'Fused cloud missing: {cloud}'
print(f'[PASS] fused cloud path exists: {cloud}')

# --- Load a real depth map ---
real_cam = next(c for c in calib.cameras if c != 'e3v8250')
depth = ds.load_depth_map(all_f[1], real_cam)
assert depth is not None, f'Failed to load depth map for {real_cam} frame 1'
assert depth.ndim == 2, f'Expected 2D depth array, got shape {depth.shape}'
print(f'[PASS] depth map loaded for {real_cam}: shape={depth.shape} dtype={depth.dtype}')

# --- Repr ---
r = repr(ds)
assert 'GroundTruthDataset' in r
print(f'[PASS] repr: {r}')

print()
print('loader.py: all assertions passed')
