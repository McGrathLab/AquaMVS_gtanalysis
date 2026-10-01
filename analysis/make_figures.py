"""
Render every figure in the AquaMVS paper, under its manuscript filename.

One command, one output folder (default results/figures/), plus MANIFEST.md mapping
each manuscript figure to its file, generator and inputs. Fonts are strict by default:
without LaTeX the run fails rather than fall back to DejaVu (use --allow-font-fallback
for a quick look on a machine without LaTeX). The 3D renders need a GPU with EGL
(Linux) or a display; Fig. 1 needs Graphviz and the CMU Serif font.

Inputs (defaults are the AquaCal 2.1.0 / AquaMVS 1.7.2 runs; see README):
  board:   data/runs/modern_refractive + data/analysis_output.modern_refractive,
           data/analysis_output.modern_pinhole_B
  fish:    data/runs_fish/modern_run5_filtered (median frames 1799..8999),
           data/runs_fish/modern_run3_raw (raw frame 1799),
           data/runs_fish/modern_lg_full (LightGlue, frame 1799)

Run:
    python analysis/make_figures.py [--out results/figures] [--only fig2 figS1 ...]
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

FIGURES = {
    "fig1": "Software architecture flowchart",
    "fig2": "RoMa vs LightGlue meshes, fish-present frame 1799, oblique",
    "fig3": "Board top-down renders, four poses",
    "fig4": "Range vs lateral error; error anisotropy",
    "figS1": "Temporal repeatability, with signed drift",
    "tilt": "Pinhole penalty vs board tilt (R2.1)",
    "spatial": "Spatial consistency, refractive with pinhole overlay (R2.1)",
    "median": "What the temporal median removes (R1.5 / R1.6)",
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--out", type=Path, default=REPO / "results" / "figures")
    ap.add_argument("--only", nargs="+", choices=list(FIGURES), default=list(FIGURES))
    ap.add_argument("--allow-font-fallback", action="store_true")
    ap.add_argument("--board-run", type=Path, default=REPO / "data/runs/modern_refractive")
    ap.add_argument("--board-analysis", type=Path, default=REPO / "data/analysis_output.modern_refractive")
    ap.add_argument("--pinhole-analysis", type=Path, default=REPO / "data/analysis_output.modern_pinhole_B")
    ap.add_argument("--fish-median-run", type=Path, default=REPO / "data/runs_fish/modern_run5_filtered")
    ap.add_argument("--fish-raw-run", type=Path, default=REPO / "data/runs_fish/modern_run3_raw")
    ap.add_argument("--fish-lightglue-run", type=Path, default=REPO / "data/runs_fish/modern_lg_full")
    args = ap.parse_args()

    if not args.allow_font_fallback:
        os.environ["AQUAMVS_GT_STRICT_FONTS"] = "1"
    # Fig. 4's generators read their root from the environment at import time.
    os.environ["AQUAMVS_GT_OUT"] = str(args.board_analysis)
    # ...and Fig. 4b's camera models from the board run's calibration.
    os.environ["AQUAMVS_GT_DATA"] = str(args.board_run)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    mesh = lambda run: run / "output" / "frame_000000" / "mesh" / "surface.ply"  # noqa: E731
    rows = []

    if "fig1" in args.only:
        from analysis.deliverables import fig_software_flow
        fig_software_flow.render(out, "aquamvs_software_flow", ("pdf", "svg", "png"))
        rows.append(("Fig. 1", "aquamvs_software_flow.{pdf,svg,png}", "fig_software_flow", "none (schematic)"))

    if "fig2" in args.only:
        from analysis.deliverables import fig_pathway_meshes
        sys.argv = ["fig_pathway_meshes", "--roma", str(mesh(args.fish_median_run)),
                    "--lightglue", str(mesh(args.fish_lightglue_run)), "--out", str(out)]
        fig_pathway_meshes.main()
        rows.append(("Fig. 2 (a, b)", "roma_mesh_oblique.{pdf,png}, lightglue_full_mesh_oblique.{pdf,png}",
                     "fig_pathway_meshes", f"{mesh(args.fish_median_run)}, {mesh(args.fish_lightglue_run)}"))

    if "fig3" in args.only:
        from analysis.deliverables import fig_board_top
        sys.argv = ["fig_board_top", "--run", str(args.board_run), "--analysis",
                    str(args.board_analysis), "--out", str(out)]
        fig_board_top.main()
        rows.append(("Fig. 3 (a-d)", "aquamvs_gt_board_top_{a,b,c,d}.{pdf,png} (+ .json: frames, tilt, coverage)",
                     "fig_board_top", f"{args.board_run}, {args.board_analysis}"))

    if "fig4" in args.only:
        from analysis.deliverables import fig_anisotropy, fig_range_lateral
        from analysis.deliverables._artifacts import FIGURES_DIR
        fig_range_lateral.main()
        fig_anisotropy.main()
        for src, dst in (("range_vs_lateral", "aquamvs_gt_range_vs_lateral"),
                         ("error_anisotropy", "aquamvs_gt_error_anisotropy")):
            for ext in ("pdf", "png"):
                shutil.copyfile(FIGURES_DIR / f"{src}.{ext}", out / f"{dst}.{ext}")
        rows.append(("Fig. 4 (a, b)", "aquamvs_gt_range_vs_lateral.{pdf,png}, aquamvs_gt_error_anisotropy.{pdf,png}",
                     "fig_range_lateral, fig_anisotropy", str(args.board_analysis)))

    if "figS1" in args.only:
        from analysis.deliverables import fig_temporal_repeatability
        fig_temporal_repeatability.render(args.fish_median_run, out, "aquamvs_real_temporal_repeatability")
        rows.append(("Fig. S1", "aquamvs_real_temporal_repeatability.{svg,pdf,png}",
                     "fig_temporal_repeatability", str(args.fish_median_run)))

    if "tilt" in args.only:
        from analysis.deliverables import fig_tilt_penalty
        fig_tilt_penalty.render(args.board_analysis, args.pinhole_analysis, out, "aquamvs_gt_tilt_penalty")
        rows.append(("new (R2.1)", "aquamvs_gt_tilt_penalty.{svg,pdf,png}", "fig_tilt_penalty",
                     f"{args.board_analysis}, {args.pinhole_analysis}"))

    if "spatial" in args.only:
        from analysis.deliverables import fig_spatial_consistency
        fig_spatial_consistency.render(args.board_analysis, args.pinhole_analysis, out,
                                       "aquamvs_gt_spatial_consistency")
        rows.append(("new (R2.1)", "aquamvs_gt_spatial_consistency.{svg,pdf,png}", "fig_spatial_consistency",
                     f"{args.board_analysis}, {args.pinhole_analysis}"))

    if "median" in args.only:
        from analysis.deliverables import fig_median_demo
        fig_median_demo.render(args.fish_raw_run, args.fish_median_run, "frame_001799", None, out,
                               "aquamvs_real_median_demo")
        rows.append(("new (R1.5 / R1.6)", "aquamvs_real_median_demo.{svg,pdf,png}", "fig_median_demo",
                     f"{args.fish_raw_run}, {args.fish_median_run}"))

    if set(args.only) == set(FIGURES):
        rel = lambda s: s.replace(str(REPO) + "/", "")  # noqa: E731
        lines = ["# Manuscript figures", "",
                 "Generated by `python analysis/make_figures.py`. Every generator is in",
                 "`analysis/deliverables/`; inputs are paths in this repository.", "",
                 "| Figure | Files | Generator | Inputs |", "|---|---|---|---|"]
        lines += [f"| {a} | {b} | `{c}` | {rel(d)} |" for a, b, c, d in rows]
        (out / "MANIFEST.md").write_text("\n".join(lines) + "\n")
    print(f"\nFigures in {out}")


if __name__ == "__main__":
    main()
