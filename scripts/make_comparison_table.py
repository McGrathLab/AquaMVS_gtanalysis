"""
Build the five-column R2.1 / R2.2 / R1.4 comparison table.

Columns, left to right:
  RoMa-refractive                       the refractive reconstruction
  RoMa-pinhole                          pinhole B: re-fitted without refraction (R2.1 primary)
  RoMa-pinhole (n_water=1 only)         pinhole A: refraction switched off in refractive parameters
  RoMa-refractive, matched filter       RoMa depth maps under the shared cross-camera filter
  LightGlue-refractive, matched filter  LightGlue depth maps under the same filter (R2.2)

Each column reads the artifacts run_all.py wrote to data/analysis_output.<prefix><name>.
The matched-filter trees come from scripts/filter_depth_maps.py and the pinhole
calibrations from scripts/fit_pinhole_calibration.py + make_ablation_calibrations.py.

Usage:
    python scripts/make_comparison_table.py [--prefix modern_] [--out data/results.modern_comparison]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

COLUMNS = [
    ("RoMa-refractive", "refractive"),
    ("RoMa-pinhole", "pinhole_B"),
    ("RoMa-pinhole (n_water=1 only)", "pinhole_A"),
    ("RoMa-refractive, matched filter", "refractive_matchfilt"),
    ("LightGlue-refractive, matched filter", "lightglue_matchfilt"),
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--prefix", default="modern_",
                    help="analysis-output name prefix (default: modern_)")
    ap.add_argument("--out", default="data/results.modern_comparison",
                    help="results directory for table.{md,tex,csv}")
    args = ap.parse_args()

    columns = [(label, f"data/analysis_output.{args.prefix}{name}") for label, name in COLUMNS]
    missing = [root for _, root in columns if not (REPO / root).is_dir()]
    if missing:
        raise SystemExit(f"missing analysis outputs: {missing}")

    os.environ["AQUAMVS_GT_RESULTS"] = args.out  # read at call time by analysis._paths
    from analysis.deliverables.make_table import main as make_table

    make_table(columns=columns)


if __name__ == "__main__":
    main()
