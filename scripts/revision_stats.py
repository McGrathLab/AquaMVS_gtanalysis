"""
Per-frame statistics for the revision: R1.3 summary, tilt breakdown, interface sensitivity.

All three read the per-frame values run_all.py writes for the 8 held-out frames, so
every statistic is over the same frames:

  summary      mean, SD (n-1) and 95 % t-interval of the per-frame flatness RMS,
               recovered square pitch, absolute scale error and rigid inlier RMSE,
               for each analysis-output root given (R1.3).
  tilt         per-frame board tilt against scale error and rigid RMSE for each
               root, to show where refraction modelling matters (R2.1).
  sensitivity  paired per-frame differences between two roots reconstructed from the
               same frames under different calibrations (the interface-sensitivity
               check: February 2026 production vs AquaCal 2.1.0).

Usage:
    python scripts/revision_stats.py --root NAME=OUTPUT_ROOT [--root ...] \\
        [--pair A_NAME B_NAME] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.deliverables._artifacts import load_per_frame  # noqa: E402

METRICS = {
    "flatness_rms_mm": "Flatness RMS (mm)",
    "board_size_mm": "Recovered square pitch (mm)",
    "scale_error_pct": "Absolute scale error (%)",
    "rigid_rms_mm": "Rigid inlier RMSE (mm)",
}


def per_frame(root: Path) -> dict[int, dict[str, float]]:
    """frame_idx -> {tilt_deg, flatness_rms_mm, board_size_mm, scale_error_pct, rigid_rms_mm}."""
    return load_per_frame(root)


def summarise(values: list[float]) -> dict[str, float]:
    x = np.asarray(values, dtype=float)
    n = len(x)
    mean, sd = float(x.mean()), float(x.std(ddof=1))
    half = float(stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n))
    return {"n": n, "mean": mean, "sd": sd, "ci95_lo": mean - half, "ci95_hi": mean + half}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--root", action="append", required=True, metavar="NAME=OUTPUT_ROOT")
    ap.add_argument("--pair", nargs=2, metavar=("A", "B"),
                    help="two root names for the paired sensitivity comparison (B - A)")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    roots = {}
    for spec in args.root:
        name, _, path = spec.rpartition("=")
        roots[name] = per_frame(Path(path))

    result: dict = {"summary": {}, "tilt": {}, "sensitivity": None}
    for name, frames in roots.items():
        result["summary"][name] = {m: summarise([f[m] for f in frames.values()]) for m in METRICS}
        result["tilt"][name] = [
            {"frame_idx": i, "tilt_deg": f["tilt_deg"], "scale_error_pct": f["scale_error_pct"],
             "rigid_rms_mm": f["rigid_rms_mm"]}
            for i, f in sorted(frames.items(), key=lambda kv: kv[1]["tilt_deg"])
        ]

    if args.pair:
        a, b = (roots[n] for n in args.pair)
        common = sorted(set(a) & set(b))
        result["sensitivity"] = {"a": args.pair[0], "b": args.pair[1], "frames": common}
        for m in METRICS:
            d = [b[i][m] - a[i][m] for i in common]
            s = summarise(d)
            s["paired_t_p"] = float(stats.ttest_1samp(d, 0.0).pvalue)
            result["sensitivity"][m] = s

    # --- print ---
    for name, summ in result["summary"].items():
        print(f"\n== {name}: per-frame mean ± SD [95% CI], n = 8")
        for m, label in METRICS.items():
            s = summ[m]
            print(f"  {label:30s} {s['mean']:+9.3f} ± {s['sd']:.3f}  [{s['ci95_lo']:+.3f}, {s['ci95_hi']:+.3f}]")
    for name, rows in result["tilt"].items():
        print(f"\n== {name}: by tilt")
        for r in rows:
            print(f"  frame {r['frame_idx']}  tilt {r['tilt_deg']:5.1f} deg   scale {r['scale_error_pct']:+7.3f} %   rigid {r['rigid_rms_mm']:6.2f} mm")
    if result["sensitivity"]:
        s = result["sensitivity"]
        print(f"\n== paired difference {s['b']} - {s['a']} over frames {s['frames']}")
        for m, label in METRICS.items():
            q = s[m]
            print(f"  {label:30s} {q['mean']:+8.3f} ± {q['sd']:.3f}  [{q['ci95_lo']:+.3f}, {q['ci95_hi']:+.3f}]  p={q['paired_t_p']:.2f}")

    if args.json:
        args.json.write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
