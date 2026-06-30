"""
AquaMVS Ground-Truth Dataset Loader
====================================
Provides lazy, cached access to the extracted aquamvs_ground_truth_analysis dataset:
  - Calibration data (via aquamvs.calibration.load_calibration_data)
  - Board spec (parsed from calibration.json)
  - Frame metadata with held-out / calibration-overlap flagging
  - Depth map paths and arrays (returns None for e3v8250 and missing files)
  - Fused point-cloud paths (lazy — never loaded into memory)
  - Undistorted image paths

All data-access operations live here; downstream analysis modules import from this file.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from aquamvs.calibration import load_calibration_data, CalibrationData

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

DEFAULT_DATA_ROOT = Path("data/aquamvs_ground_truth_analysis")

# Output indices 0 and 5 coincide with calibration-fit frames
CALIBRATION_OVERLAP_INDICES: frozenset[int] = frozenset({0, 5})

# Camera that has frames but NO depth map .npz (auxiliary fisheye witness view)
NO_DEPTH_CAMERAS: frozenset[str] = frozenset({"e3v8250"})

# Raw video frame indices corresponding to output indices 0–9
_RAW_FRAME_INDICES: list[int] = [0, 786, 1572, 2358, 3144, 3930, 4716, 5502, 6288, 7074]


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BoardSpec:
    """ChArUco board geometry from calibration.json."""
    squares_x: int        # 12
    squares_y: int        # 9
    square_size: float    # 0.06 m
    marker_size: float    # 0.045 m
    dict_name: str        # "DICT_5X5_100"


@dataclass(frozen=True)
class DatasetConfig:
    """Configurable dataset root. Defaults to repo-relative data path."""
    data_root: Path = DEFAULT_DATA_ROOT

    def __post_init__(self) -> None:
        # Normalise to Path if a str was passed
        object.__setattr__(self, "data_root", Path(self.data_root))


@dataclass(frozen=True)
class FrameInfo:
    """Per-output-index metadata. Does NOT load data eagerly."""
    output_idx: int               # 0–9
    raw_frame_idx: int            # actual video frame number
    is_calibration_overlap: bool  # True for output indices 0 and 5


# ── Main class ────────────────────────────────────────────────────────────────

class GroundTruthDataset:
    """
    Lazy, cached interface to the AquaMVS ground-truth analysis dataset.

    Usage::

        ds = GroundTruthDataset()
        calib = ds.calibration()   # CalibrationData (13 cameras)
        spec  = ds.board_spec()    # BoardSpec(12, 9, 0.06, 0.045, "DICT_5X5_100")
        frames = ds.validation_frames()  # 8 held-out FrameInfo objects
    """

    def __init__(self, config: DatasetConfig = DatasetConfig()) -> None:
        self._config = config
        self._calib_cache: Optional[CalibrationData] = None
        self._board_spec_cache: Optional[BoardSpec] = None

    # ── Calibration ───────────────────────────────────────────────────────────

    def calibration(self) -> CalibrationData:
        """Return CalibrationData (13 cameras + interface params). Cached after first call."""
        if self._calib_cache is None:
            calib_path = self._config.data_root / "calibration.json"
            logger.debug("Loading calibration from %s", calib_path)
            self._calib_cache = load_calibration_data(str(calib_path))
            logger.debug(
                "Calibration loaded: %d cameras, water_z=%.4f",
                len(self._calib_cache.cameras),
                self._calib_cache.water_z,
            )
        else:
            logger.debug("Calibration cache hit")
        return self._calib_cache

    # ── Board spec ────────────────────────────────────────────────────────────

    def board_spec(self) -> BoardSpec:
        """Return BoardSpec parsed from calibration.json. Cached after first call."""
        if self._board_spec_cache is None:
            calib_path = self._config.data_root / "calibration.json"
            logger.debug("Parsing board spec from %s", calib_path)
            with calib_path.open() as fh:
                raw = json.load(fh)
            board = raw["board"]
            # JSON key is "dictionary"; we surface it as dict_name in the dataclass
            self._board_spec_cache = BoardSpec(
                squares_x=int(board["squares_x"]),
                squares_y=int(board["squares_y"]),
                square_size=float(board["square_size"]),
                marker_size=float(board["marker_size"]),
                dict_name=str(board["dictionary"]),
            )
            logger.debug("Board spec: %s", self._board_spec_cache)
        else:
            logger.debug("Board spec cache hit")
        return self._board_spec_cache

    # ── Frame access ──────────────────────────────────────────────────────────

    def all_frames(self) -> list[FrameInfo]:
        """Return all 10 FrameInfo objects (includes calibration-overlap frames), ordered by output_idx."""
        return [
            FrameInfo(
                output_idx=i,
                raw_frame_idx=_RAW_FRAME_INDICES[i],
                is_calibration_overlap=(i in CALIBRATION_OVERLAP_INDICES),
            )
            for i in range(10)
        ]

    def validation_frames(self) -> list[FrameInfo]:
        """Return the 8 held-out validation frames (output indices 1,2,3,4,6,7,8,9)."""
        return [f for f in self.all_frames() if f.output_idx not in CALIBRATION_OVERLAP_INDICES]

    # ── Private helpers ───────────────────────────────────────────────────────

    def _output_dir(self, frame: FrameInfo) -> Path:
        """Return the per-frame output directory path."""
        return self._config.data_root / "output" / f"frame_{frame.output_idx:06d}"

    # ── Depth maps ────────────────────────────────────────────────────────────

    def depth_map_path(self, frame: FrameInfo, camera: str) -> Optional[Path]:
        """
        Return the Path to a depth map .npz, or None if unavailable.

        Returns None for cameras in NO_DEPTH_CAMERAS (e.g. e3v8250) and for
        missing files — never raises an exception.
        """
        if camera in NO_DEPTH_CAMERAS:
            logger.debug("depth_map_path: %s has no depth map (NO_DEPTH_CAMERAS)", camera)
            return None
        path = self._output_dir(frame) / "depth_maps" / f"{camera}.npz"
        if not path.exists():
            logger.debug("depth_map_path: file not found — %s", path)
            return None
        return path

    def load_depth_map(self, frame: FrameInfo, camera: str) -> Optional[np.ndarray]:
        """
        Load and return the depth array for a given frame and camera.

        Returns None if depth_map_path() returns None or if loading fails.
        The npz contains 'depth' and 'confidence' arrays; this returns 'depth'.
        """
        path = self.depth_map_path(frame, camera)
        if path is None:
            return None
        try:
            data = np.load(path)
            depth = data["depth"]
            logger.debug(
                "Loaded depth map %s: shape=%s dtype=%s", path.name, depth.shape, depth.dtype
            )
            return depth
        except Exception:
            logger.warning("Failed to load depth map from %s", path, exc_info=True)
            return None

    # ── Point clouds ──────────────────────────────────────────────────────────

    def fused_cloud_path(self, frame: FrameInfo) -> Path:
        """
        Return the Path to the fused point cloud .ply for a frame.

        The cloud is NOT loaded into memory — callers receive a Path only.
        (~650 MB per frame; load explicitly if needed.)
        """
        return self._output_dir(frame) / "point_cloud" / "fused.ply"

    # ── Undistorted images ────────────────────────────────────────────────────

    def undistorted_image_path(self, frame: FrameInfo, camera: str) -> Path:
        """Return the path to the undistorted image for a given frame and camera."""
        return self._output_dir(frame) / "undistorted" / f"{camera}.png"

    # ── Repr ─────────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"GroundTruthDataset("
            f"data_root={self._config.data_root!r}, "
            f"frames={len(self.all_frames())}"
            f")"
        )
