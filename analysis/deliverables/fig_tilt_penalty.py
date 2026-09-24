"""
Pinhole penalty vs board tilt (R2.1).

Per-frame absolute scale error and rigid inlier RMSE against board tilt, for the
refractive reconstruction and the pinhole ablation(s). Each physical pose is placed at
the tilt recovered by the refractive run, so every arm shares one x-position per frame
(each arm recovers a slightly different tilt from its own reconstruction).

Visual message: near-normal views are within noise; the pinhole penalty grows steeply
with obliquity, which is where refraction modelling matters.

Run:
    python -m analysis.deliverables.fig_tilt_penalty \
        --refractive data/analysis_output.modern_refractive \
        --pinhole data/analysis_output.modern_pinhole_B \
        [--pinhole-a data/analysis_output.modern_pinhole_A] [--out DIR] [--name NAME]
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless backend

import matplotlib.pyplot as plt
import numpy as np

from analysis.deliverables._artifacts import FIGURES_DIR, load_per_frame
from analysis.deliverables._style import COLORS, DOUBLE_COL, dissertation_style, save_figure


def _series(frames: dict, tilt_of: dict, key: str) -> tuple[np.ndarray, np.ndarray]:
    idx = sorted(tilt_of, key=tilt_of.get)
    return np.array([tilt_of[i] for i in idx]), np.array([frames[i][key] for i in idx])


def render(refractive: Path, pinhole: Path, pinhole_a: Path | None,
           out: Path, name: str) -> list[Path]:
    ref = load_per_frame(refractive)
    arms = [("Refractive", ref, COLORS["blue"], "o", 1.0),
            ("Pinhole, re-fitted (B)", load_per_frame(pinhole), COLORS["coral"], "s", 1.0)]
    if pinhole_a is not None:
        arms.append(("Pinhole, $n_\\mathrm{water}{=}1$ only (A)", load_per_frame(pinhole_a),
                     COLORS["dark gray"], "^", 0.55))
    tilt_of = {i: f["tilt_deg"] for i, f in ref.items()}

    with dissertation_style():
        fig, (ax_s, ax_r) = plt.subplots(1, 2, figsize=(DOUBLE_COL, 2.7), constrained_layout=True)
        for label, frames, color, marker, alpha in arms:
            for ax, key in ((ax_s, "scale_error_pct"), (ax_r, "rigid_rms_mm")):
                x, y = _series(frames, tilt_of, key)
                ax.plot(x, y, color=color, marker=marker, linewidth=0.8, alpha=alpha,
                        markersize=4.5, label=label)
        ax_s.axhline(0, color="#AAAAAA", linewidth=0.6, linestyle=":", zorder=0)
        ax_s.set_ylabel("Absolute scale error (\\%)")
        ax_r.set_ylabel("Rigid inlier RMSE (mm)")
        ax_r.set_ylim(bottom=0)
        for ax, tag in ((ax_s, "(A)"), (ax_r, "(B)")):
            ax.set_xlabel("Board tilt ($^\\circ$)")
            ax.set_title(f"\\textbf{{{tag}}}", loc="left")
        ax_r.legend(loc="upper left")
        return save_figure(fig, name, output_dir=out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--refractive", type=Path, required=True)
    ap.add_argument("--pinhole", type=Path, required=True, help="pinhole B analysis-output root")
    ap.add_argument("--pinhole-a", type=Path, default=None, help="optional pinhole A root")
    ap.add_argument("--out", type=Path, default=FIGURES_DIR)
    ap.add_argument("--name", default="tilt_penalty")
    args = ap.parse_args()
    for p in render(args.refractive, args.pinhole, args.pinhole_a, args.out, args.name):
        print(f"Saved: {p}")


if __name__ == "__main__":
    main()
