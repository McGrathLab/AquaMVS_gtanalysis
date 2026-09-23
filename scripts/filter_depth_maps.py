"""
Apply AquaMVS's cross-camera consistency filter to a run's saved depth maps.

Why this exists (R2.2): the two AquaMVS pathways save depth maps at different
stages. The RoMa path saves the output of aggregate_pairwise_depths, which has
already enforced its own multi-view consistency (median of pairwise sources,
>= min views within roma_depth_tolerance). The LightGlue/plane-sweep path saves
raw plane-sweep depths; its consistency filter (filter_all_depth_maps) runs only
at fusion and is never written back. The GT metrics read the saved depth maps,
so comparing the two pathways directly compares filtered against unfiltered
data.

This script applies the identical library filter -- aquamvs.fusion.
filter_all_depth_maps, with the run's own config.reconstruction thresholds
(depth_tolerance, min_consistent_views) -- to any run, so both pathways can be
analyzed under matched filtering. Nothing is re-implemented: the projection
models are built exactly as aquamvs.pipeline.builder.build_pipeline_context
builds them (without its side effect of writing into the output dir).

The destination is a new run tree: filtered depth_maps/ per frame, every other
per-frame entry symlinked to the source, calibration.json and config.yaml
copied, and FILTER_README.md recording thresholds and pixels kept. Point it at
run_all.py via --data-root.

Requires the aquamvs-june environment (torch; CUDA recommended).

Usage:
    python scripts/filter_depth_maps.py <source run dir> <destination run dir> [--device cuda]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import torch
from aquamvs import __version__ as AQUAMVS_VERSION
from aquamvs.calibration import compute_undistortion_maps, load_calibration_data
from aquamvs.config import PipelineConfig
from aquamvs.fusion import filter_all_depth_maps
from aquamvs.projection.refractive import RefractiveProjectionModel


def _projection_models(cfg: PipelineConfig, calib_path: Path, device: str):
    """Ring cameras + projection models, mirroring build_pipeline_context steps 1-3."""
    calib = load_calibration_data(str(calib_path))
    inputs = set(cfg.camera_input_map)
    ring = [c for c in calib.ring_cameras if c in inputs]
    active = set(ring) | {c for c in calib.auxiliary_cameras if c in inputs}
    models = {}
    for name in active:
        cam = calib.cameras[name]
        models[name] = RefractiveProjectionModel(
            K=compute_undistortion_maps(cam).K_new,
            R=cam.R,
            t=cam.t,
            water_z=calib.water_z,
            normal=calib.interface_normal,
            n_air=calib.n_air,
            n_water=calib.n_water,
        ).to(device)
    return ring, models


def filter_run(src: Path, dst: Path, device: str) -> dict:
    cfg = PipelineConfig.from_yaml(src / "config.yaml")
    rc = cfg.reconstruction
    ring, models = _projection_models(cfg, src / "calibration.json", device)

    if dst.exists():
        raise FileExistsError(f"{dst} exists; remove it first (refusing to overwrite)")
    (dst / "output").mkdir(parents=True)
    for f in ("calibration.json", "config.yaml"):
        shutil.copy2(src / f, dst / f)

    per_frame = []
    for fr in sorted((src / "output").glob("frame_*")):
        out = dst / "output" / fr.name
        out.mkdir()
        for sub in fr.iterdir():
            if sub.name != "depth_maps":
                (out / sub.name).symlink_to(sub.resolve(), target_is_directory=sub.is_dir())

        depths, confs = {}, {}
        for npz in sorted((fr / "depth_maps").glob("*.npz")):
            with np.load(npz) as z:
                depths[npz.stem] = torch.from_numpy(z["depth"]).to(device)
                confs[npz.stem] = torch.from_numpy(z["confidence"]).to(device)
        # Same reference set fusion uses: ring cameras that have a depth map.
        refs = [c for c in ring if c in depths]
        filtered = filter_all_depth_maps(refs, models, depths, confs, rc)

        (out / "depth_maps").mkdir()
        before = after = 0
        for cam, (fd, fc, _count) in filtered.items():
            before += int(torch.isfinite(depths[cam]).sum())
            after += int(torch.isfinite(fd).sum())
            np.savez_compressed(
                out / "depth_maps" / f"{cam}.npz",
                depth=fd.cpu().numpy(),
                confidence=fc.cpu().numpy(),
            )
        per_frame.append({"frame": fr.name, "cameras": len(filtered),
                          "valid_before": before, "valid_after": after})
        print(f"  {fr.name}: {len(filtered)} cameras, kept {100 * after / max(before, 1):.1f}%",
              flush=True)

    tot_b = sum(p["valid_before"] for p in per_frame)
    tot_a = sum(p["valid_after"] for p in per_frame)
    summary = {
        "source": str(src.resolve()),
        "matcher_type": cfg.matcher_type,
        "aquamvs_version": AQUAMVS_VERSION,
        "depth_tolerance_m": rc.depth_tolerance,
        "min_consistent_views": rc.min_consistent_views,
        "valid_before": tot_b,
        "valid_after": tot_a,
        "kept_fraction": tot_a / tot_b if tot_b else None,
        "per_frame": per_frame,
    }
    (dst / "filter_summary.json").write_text(json.dumps(summary, indent=2))
    (dst / "FILTER_README.md").write_text(
        f"# Cross-camera-filtered depth maps\n\n"
        f"Generated {_dt.datetime.now().isoformat(timespec='seconds')} by "
        f"`scripts/filter_depth_maps.py` (AquaMVS {AQUAMVS_VERSION}).\n\n"
        f"- Source run: `{src.resolve()}` (matcher: {cfg.matcher_type})\n"
        f"- Filter: `aquamvs.fusion.filter_all_depth_maps`, depth_tolerance "
        f"{rc.depth_tolerance} m, min_consistent_views {rc.min_consistent_views}\n"
        f"- Valid depth pixels: {tot_b:,} -> {tot_a:,} "
        f"({100 * tot_a / max(tot_b, 1):.1f}% kept)\n\n"
        f"Only `output/frame_*/depth_maps/` is new; every other per-frame entry is a "
        f"symlink into the source run. See filter_summary.json for per-frame counts.\n"
    )
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("src", type=Path, help="source run dir (has config.yaml, calibration.json, output/)")
    ap.add_argument("dst", type=Path, help="destination run dir (must not exist)")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = ap.parse_args()
    s = filter_run(args.src, args.dst, args.device)
    print(f"valid depth pixels: {s['valid_before']:,} -> {s['valid_after']:,} "
          f"({100 * s['kept_fraction']:.1f}% kept; tol {s['depth_tolerance_m']} m, "
          f">= {s['min_consistent_views']} views)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
