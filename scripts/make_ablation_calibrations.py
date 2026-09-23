"""
Build the two pinhole-ablation calibrations (R2.1) from their AquaCal sources.

Pinhole A ("model swap"): the refractive calibration with interface.n_water set to
1.0 and nothing else changed -- refraction switched off in parameters that were
fitted with it on.

Pinhole B ("fair baseline"): AquaCal's own fit with n_water = 1.0 (camera
parameters re-fitted without refraction; produce it with
scripts/fit_pinhole_calibration.py), with one field pinned: water_z.

Why pin water_z for B: at n_water = 1 the interface bends no ray, so water_z is
unidentifiable and AquaCal leaves it wherever its solver stopped (2.1.0 drives it
to its 0.01 m lower bound, 1 cm below the reference camera), and
fit_pinhole_calibration.py registers the auxiliary camera against 0.5 m, so the
fitted file carries two different water_z values. Pinning every camera to one
value between the cameras and the scene makes the file consistent and keeps
every camera on the air side, as AquaMVS requires. It has no optical effect
(verified: water_z in 0.3-1.0 m gives identical projection validity and pixel
positions to 1e-3 px across all 13 cameras).

The consequential part of the fix is in the fit, not here: a plain
`aquacal calibrate` at n = 1 fails to register e3v8250 (see
fit_pinhole_calibration.py).

Usage:
    python scripts/make_ablation_calibrations.py \\
        --refractive <refractive calibration.json> \\
        --pinhole-fit <AquaCal n_water=1 calibration.json> \\
        --out-a <pinhole A calibration.json> --out-b <pinhole B calibration.json> \\
        [--water-z 0.5]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

PINNED_WATER_Z = 0.5  # metres; between every camera centre (z <= 0.0 m) and the scene (z >= ~1.05 m)


def _camera_centre_z(cam: dict) -> float:
    R = np.array(cam["extrinsics"]["R"], dtype=float)
    t = np.array(cam["extrinsics"]["t"], dtype=float).ravel()
    return float((-R.T @ t)[2])


def make_pinhole_a(refractive: dict) -> dict:
    out = json.loads(json.dumps(refractive))
    out["interface"]["n_water"] = 1.0
    return out


def make_pinhole_b(pinhole_fit: dict, water_z: float) -> dict:
    if pinhole_fit["interface"]["n_water"] != 1.0:
        raise ValueError("pinhole fit must have n_water == 1.0; water_z is only free at n = 1")
    lowest = max(_camera_centre_z(c) for c in pinhole_fit["cameras"].values())
    if not water_z > lowest:
        raise ValueError(f"water_z {water_z} must lie below every camera centre (lowest at z={lowest:.4f})")
    out = json.loads(json.dumps(pinhole_fit))
    for cam in out["cameras"].values():
        cam["water_z"] = water_z
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--refractive", type=Path, required=True)
    ap.add_argument("--pinhole-fit", type=Path, required=True)
    ap.add_argument("--out-a", type=Path, required=True)
    ap.add_argument("--out-b", type=Path, required=True)
    ap.add_argument("--water-z", type=float, default=PINNED_WATER_Z)
    args = ap.parse_args()

    refractive = json.loads(args.refractive.read_text())
    pinhole_fit = json.loads(args.pinhole_fit.read_text())
    fitted_wz = sorted({c["water_z"] for c in pinhole_fit["cameras"].values()})

    args.out_a.write_text(json.dumps(make_pinhole_a(refractive), indent=2))
    args.out_b.write_text(json.dumps(make_pinhole_b(pinhole_fit, args.water_z), indent=2))
    print(f"pinhole A: {args.refractive} with interface.n_water "
          f"{refractive['interface']['n_water']} -> 1.0  => {args.out_a}")
    print(f"pinhole B: {args.pinhole_fit} with water_z {fitted_wz} -> {args.water_z}  => {args.out_b}")


if __name__ == "__main__":
    main()
