"""
AquaMVS ChArUco Corner Detection
=================================
Wraps the AquaCal detector for the known board (12x9, 60mm, DICT_5X5_100)
and provides per-camera, per-frame detection over the validation set.

Detection runs on UNDISTORTED images only — those images share the same pixel
grid as the per-camera depth maps, so pixel (u,v) coordinates returned here
are directly usable for depth lookups in Plan 02-02.

Key functions
-------------
build_board_geometry(board_spec) -> BoardGeometry
    Construct a BoardGeometry from the loader's BoardSpec.

depth_bearing_cameras(ds) -> list[str]
    Return the 12 cameras that have depth maps (excludes e3v8250), sorted.

detect_corners(ds, frame, camera, board=None) -> Detection | None
    Detect subpixel ChArUco corners in one undistorted image.

detect_validation_set(ds, board=None) -> dict[tuple[int, str], Detection]
    Run detection over all 8 validation frames x 12 depth cameras.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allow running from the repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: F401 — imported for type completeness; used via aquacal

from aquacal.config.schema import BoardConfig, Detection
from aquacal.core.board import BoardGeometry
from aquacal.io.detection import detect_charuco

from analysis.loader import GroundTruthDataset, FrameInfo, NO_DEPTH_CAMERAS, BoardSpec

logger = logging.getLogger(__name__)


# ── Board construction ────────────────────────────────────────────────────────

def build_board_geometry(board_spec: BoardSpec) -> BoardGeometry:
    """
    Construct a BoardGeometry from the loader's BoardSpec.

    Maps BoardSpec fields to BoardConfig:
      squares_x, squares_y, square_size, marker_size straight across;
      dict_name -> dictionary; legacy_pattern=False.
    """
    config = BoardConfig(
        squares_x=board_spec.squares_x,
        squares_y=board_spec.squares_y,
        square_size=board_spec.square_size,
        marker_size=board_spec.marker_size,
        dictionary=board_spec.dict_name,
        legacy_pattern=False,
    )
    return BoardGeometry(config)


# ── Camera helpers ────────────────────────────────────────────────────────────

def depth_bearing_cameras(ds: GroundTruthDataset) -> list[str]:
    """
    Return the 12 cameras that carry depth maps, sorted alphabetically.

    Excludes NO_DEPTH_CAMERAS (e3v8250 — the auxiliary fisheye witness view).
    """
    return sorted(c for c in ds.calibration().cameras if c not in NO_DEPTH_CAMERAS)


# ── Single-image detection ────────────────────────────────────────────────────

def detect_corners(
    ds: GroundTruthDataset,
    frame: FrameInfo,
    camera: str,
    board: BoardGeometry | None = None,
) -> Detection | None:
    """
    Detect subpixel ChArUco corners in the undistorted image for one
    (frame, camera) pair.

    Parameters
    ----------
    ds:      GroundTruthDataset instance.
    frame:   FrameInfo for the target frame.
    camera:  Camera name string.
    board:   Pre-built BoardGeometry (built once per call if None).

    Returns
    -------
    Detection with corner_ids (N,) and corners_2d (N,2), or None if the
    image is missing or no corners were found.

    Notes
    -----
    - Images are UNDISTORTED, so dist_coeffs is NOT passed to detect_charuco.
      The CharucoDetector handles subpixel corner refinement internally.
    - Never reads from frames/ (raw images).
    """
    if board is None:
        board = build_board_geometry(ds.board_spec())

    img_path = ds.undistorted_image_path(frame, camera)
    if not img_path.exists():
        logger.debug(
            "detect_corners: image not found — frame=%d camera=%s path=%s",
            frame.output_idx, camera, img_path,
        )
        return None

    image = cv2.imread(str(img_path))
    if image is None:
        logger.debug(
            "detect_corners: cv2.imread returned None — frame=%d camera=%s",
            frame.output_idx, camera,
        )
        return None

    # detect_charuco handles subpixel corner refinement internally via
    # cv2.aruco.CharucoDetector. No dist_coeffs passed (images are undistorted).
    detection = detect_charuco(image, board)

    if detection is None:
        logger.debug(
            "detect_corners: no corners — frame=%d camera=%s", frame.output_idx, camera
        )
    else:
        logger.debug(
            "detect_corners: %d corners — frame=%d camera=%s",
            detection.num_corners, frame.output_idx, camera,
        )

    return detection


# ── Batch detection ───────────────────────────────────────────────────────────

def detect_validation_set(
    ds: GroundTruthDataset,
    board: BoardGeometry | None = None,
) -> dict[tuple[int, str], Detection]:
    """
    Run detection over all 8 validation frames x 12 depth-bearing cameras.

    Builds the board once and reuses it across all (frame, camera) pairs.
    Entries with no detection (None result) are omitted from the returned dict.

    Returns
    -------
    dict keyed by (frame.output_idx, camera) -> Detection
    """
    if board is None:
        board = build_board_geometry(ds.board_spec())

    cameras = depth_bearing_cameras(ds)
    frames = ds.validation_frames()

    results: dict[tuple[int, str], Detection] = {}
    for frame in frames:
        for camera in cameras:
            det = detect_corners(ds, frame, camera, board=board)
            if det is not None:
                results[(frame.output_idx, camera)] = det

    logger.debug(
        "detect_validation_set: %d/%d detections across %d frames x %d cameras",
        len(results), len(frames) * len(cameras), len(frames), len(cameras),
    )
    return results
