"""
Fit the R2.1 pinhole-B calibration: AquaCal's own pipeline at n_water = 1.

Runs aquacal.calibration.pipeline.run_calibration on the given config unchanged,
except for the interface height handed to the auxiliary-camera registration step.

Why: at n_water = 1 the interface bends no ray, so Stage 3 cannot locate it and
water_z drifts to the solver's 0.01 m lower bound -- 1 cm below the reference
camera. AquaCal then registers each auxiliary camera post hoc against that
water_z, and with the interface that close the registration of e3v8250 fails
(RMS 100 px, no valid validation observations; its centre lands 190 mm off, at
z = +0.052 m, on the wrong side of the interface). Because e3v8250 is a RoMa
source for every ring camera, that one bad pose costs every ring camera about a
third of its valid depth. With the interface at 0.5 m the same registration
converges (1.29 px) to within 2 mm of the aquacal 1.4.2 pinhole fit, whose
water_z happened to stop at 0.944 m.

This script hands register_auxiliary_camera a water_z between the cameras and the
scene instead (default 0.5 m). At n = 1 that value has no optical effect -- it only
keeps the auxiliary camera on the air side. Detection, the ring-camera stages, the
board poses, validation and saving are all AquaCal's, untouched.

The saved calibration still records Stage 3's drifted water_z; pin it with
scripts/make_ablation_calibrations.py before reconstruction.

Usage:
    python scripts/fit_pinhole_calibration.py <aquacal config.yaml> [--aux-water-z 0.5]
"""

from __future__ import annotations

import argparse
import functools
from pathlib import Path

import aquacal
import aquacal.calibration.pipeline as pipeline
from aquacal.calibration.pipeline import load_config

AUX_WATER_Z = 0.5  # metres; between every camera centre (z <= 0.0 m) and the scene (z >= ~1.05 m)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("config", type=Path)
    ap.add_argument("--aux-water-z", type=float, default=AUX_WATER_Z)
    args = ap.parse_args()

    config = load_config(args.config)
    if config.n_water != 1.0:
        raise SystemExit(f"n_water is {config.n_water}; this wrapper is only for the n_water = 1 fit")
    print(f"aquacal {aquacal.__version__}; auxiliary registration water_z pinned to {args.aux_water_z} m")

    original = pipeline.register_auxiliary_camera

    @functools.wraps(original)
    def register_with_pinned_interface(*a, **kw):
        print(f"  [pinhole-B wrapper] {kw.get('camera_name')}: water_z "
              f"{kw.get('water_z')} (Stage 3, unidentifiable at n=1) -> {args.aux_water_z}")
        kw["water_z"] = args.aux_water_z
        return original(*a, **kw)

    pipeline.register_auxiliary_camera = register_with_pinned_interface
    try:
        pipeline.run_calibration(args.config)
    finally:
        pipeline.register_auxiliary_camera = original


if __name__ == "__main__":
    main()
