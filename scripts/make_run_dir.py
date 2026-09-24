"""Set up an AquaMVS run directory from a source config, calibration and frames.

The shipped configs use relative, Windows-style paths (``frames\\e3v82f9``). This
writes a run directory whose config.yaml points at absolute paths inside it, so
``aquamvs run config.yaml`` works from anywhere, and changes nothing else in the
config except, optionally, the matcher:

  <run dir>/config.yaml        source config; calibration_path, output_dir, mask_dir
                               and every camera_input_map entry rewritten
  <run dir>/calibration.json   copy of --calibration
  <run dir>/frames             symlink to --frames (one subdirectory per camera)
  <run dir>/masks              symlink to --masks, if given

This is how every run behind the revision was set up (board runs from the GT
dataset's config; fish-present runs from the paper's 021826 config).

Usage:
    python scripts/make_run_dir.py <run dir> --config <source config.yaml> \
        --calibration <calibration.json> --frames <frames dir> \
        [--masks <masks dir>] [--matcher roma|lightglue]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml


def make_run_dir(
    run_dir: Path,
    config: Path,
    calibration: Path,
    frames: Path,
    masks: Path | None = None,
    matcher: str | None = None,
) -> Path:
    run_dir = run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    cfg = yaml.safe_load(config.read_text())
    cfg["calibration_path"] = str(run_dir / "calibration.json")
    cfg["output_dir"] = str(run_dir / "output")
    cfg["camera_input_map"] = {cam: str(run_dir / "frames" / cam) for cam in cfg["camera_input_map"]}
    cfg["mask_dir"] = str(run_dir / "masks")
    if matcher is not None:
        cfg["matcher_type"] = matcher

    missing = [cam for cam in cfg["camera_input_map"] if not (frames / cam).is_dir()]
    if missing:
        raise SystemExit(f"--frames {frames} has no directory for camera(s): {', '.join(missing)}")

    shutil.copyfile(calibration, run_dir / "calibration.json")
    for name, target in (("frames", frames), ("masks", masks)):
        link = run_dir / name
        if target is None:
            continue
        if link.is_symlink():
            link.unlink()
        link.symlink_to(target.resolve(), target_is_directory=True)

    out = run_dir / "config.yaml"
    with out.open("w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--config", type=Path, required=True, help="source AquaMVS config.yaml")
    ap.add_argument("--calibration", type=Path, required=True, help="calibration.json to use")
    ap.add_argument("--frames", type=Path, required=True, help="directory with one subdirectory per camera")
    ap.add_argument("--masks", type=Path, default=None, help="mask directory to link, if any")
    ap.add_argument("--matcher", choices=["roma", "lightglue"], default=None,
                    help="override matcher_type (default: keep the source config's)")
    args = ap.parse_args(argv)

    out = make_run_dir(args.run_dir, args.config, args.calibration, args.frames, args.masks, args.matcher)
    print(f"wrote {out}\n  then: cd {out.parent} && aquamvs run config.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
