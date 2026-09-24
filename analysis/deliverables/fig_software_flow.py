"""AquaMVS software-architecture flowchart for the SoftwareX paper.

Purpose-built (not auto-traced from the YAML pipeline spec) so the figure
reflects a direct read of the AquaMVS source and foregrounds the paper's
narrative rather than the full call graph. The story it tells:

  1. Shared inputs and a shared *refractive camera model* (cast_ray / project).
  2. The model is a primitive consumed by every operation that maps between
     2D image space and 3D world space (drawn as dashed gold connectors).
  3. Two matching front-ends DIVERGE -- LightGlue (sparse matcher)
     and RoMa v2 (dense matcher) -- and both drive dense reconstruction by
     different mechanisms (refractive plane-sweep vs. dense-warp triangulation).
  4. They MERGE at a shared fusion -> surface backend.
  5. A secondary "sparse / preview" off-ramp taps the classical keypoint
     triangulation. It is drawn only there because, in the code, RoMa's sparse
     mode reuses that same keypoint triangulation on sparse correspondences
     pulled from its warp (run_roma_sparse_path -> run_triangulation) rather
     than the full-mode-only per-pixel triangulation, so there is no distinct
     off-ramp from roma_depth; the RoMa case is noted in the caption prose.

Source anchor: papers/aquamvs/software-source-map.md (built from AquaMVS
v1.5.2, commit ef26798); the stages drawn are unchanged in AquaMVS 1.7.2.

Ported from DissertationFigures (figures/aquamvs/software_flowchart.py) so this
repository reproduces every manuscript figure. Differences from the original: text is
set in CMU Serif (Computer Modern, matching the manuscript) instead of the machine's
generic "serif", and the palette comes from analysis.deliverables._style.

Run (needs Graphviz `dot`, the `graphviz` Python package and the CMU Serif font,
e.g. Debian/Ubuntu `fonts-cmu`)::

    python -m analysis.deliverables.fig_software_flow [--out DIR] [--name aquamvs_software_flow]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import graphviz

from analysis.deliverables._artifacts import FIGURES_DIR
from analysis.deliverables import _style

# Two hues the vendored palette lacks (DissertationFigures' widened palette); kept
# local so the shared colour cycle of the other figures is unchanged.
COLORS = {**_style.COLORS, "orange": "#EE7733", "steel": "#4477AA"}
TINTS = {**_style.TINTS, "orange": "#FCEBE0", "steel": "#E3EBF2"}
FONT = "CMU Serif"

# A slightly deeper gold border than the palette default so the refractive
# primitive reads as the highlighted "star" element of the figure.
_GOLD_EDGE = "#B89A1E"


def _node(g: graphviz.Digraph, node_id: str, label: str, palette: str,
          *, shape: str = "box", penwidth: str = "1.0", **extra: str) -> None:
    """Add a node filled with the light tint and bordered with the saturated hue.

    *palette* is a key into COLORS/TINTS. Any keyword in *extra* (e.g. ``style``
    or graphviz ``color``) overrides the computed default.
    """
    attrs = {
        "label": label,
        "shape": shape,
        "style": "rounded,filled" if shape == "box" else "filled",
        "fillcolor": TINTS.get(palette, "#FFFFFF"),
        "color": COLORS.get(palette, "#000000"),
        "penwidth": penwidth,
    }
    attrs.update(extra)
    g.node(node_id, **attrs)


def build() -> graphviz.Digraph:
    """Construct the AquaMVS software flowchart.

    Deliberately high-level: the figure shows the overall process and the
    two-pathway split, not the full call graph. Refraction is conveyed by the
    labels on the geometric stages ("refractive triangulation / plane-sweep")
    rather than by a separate primitive node.
    """
    g = graphviz.Digraph(name="aquamvs_software_flow")
    g.attr(
        rankdir="TB",
        bgcolor="transparent",
        fontname=FONT,
        fontsize="10",
        nodesep="0.45",
        ranksep="0.5",
        splines="spline",
        margin="0",
    )
    g.attr("node", fontname=FONT, fontsize="10", margin="0.16,0.09")
    g.attr("edge", fontname=FONT, fontsize="9", color="#666666",
           arrowsize="0.8", penwidth="1.0")

    # ---- Inputs (note cards) + shared preprocessing ---------------------
    _node(g, "tmf", "Temporal median filter\\n(isolate static substrate)",
          "steel", style="rounded,filled,dashed")
    _node(g, "input_video", "Multi-camera\\nvideo / images", "blue", shape="note")
    _node(g, "input_calib", "Calibration parameters\\n(AquaCal)", "blue", shape="note")
    _node(g, "pre", "Undistortion & setup", "blue")
    _node(g, "dec", "matcher", "orange", shape="diamond", penwidth="1.2")

    # ---- LightGlue pathway (teal) ---------------------------------------
    _node(g, "lg_match", "Sparse matching\\n(LightGlue)", "teal")
    _node(g, "lg_tri", "Keypoint refractive\\ntriangulation", "teal")
    _node(g, "lg_sweep", "Plane-sweep densification", "teal")

    # ---- RoMa pathway (purple) ------------------------------------------
    _node(g, "roma_match", "Dense matching\\n(RoMa v2)", "purple")
    _node(g, "roma_depth", "Per-pixel refractive\\ntriangulation", "purple")

    # ---- Shared back-end (green) + output note card ---------------------
    _node(g, "depth", "Per-camera depth maps", "green")
    _node(g, "fusion", "Multi-view fusion", "green")
    _node(g, "surface", "Surface mesh\\n+ point cloud", "blue", shape="note")

    # ---- Sparse / preview off-ramp (secondary, note card) ---------------
    _node(g, "sparse", "Sparse cloud\\n(preview / comparison)",
          "gray", shape="note", style="filled,dashed")

    # ---- Rank alignment so paired stages read as parallel columns -------
    with g.subgraph() as s:
        s.attr(rank="same")
        s.node("input_video")
        s.node("input_calib")
    with g.subgraph() as s:
        s.attr(rank="same")
        s.node("lg_match")
        s.node("roma_match")
    with g.subgraph() as s:
        s.attr(rank="same")
        s.node("lg_tri")
        s.node("roma_depth")

    # ---- Main flow ------------------------------------------------------
    g.edge("tmf", "input_video", style="dashed")
    g.edge("input_video", "pre")
    g.edge("input_calib", "pre")
    g.edge("pre", "dec")
    g.edge("dec", "lg_match", label="lightglue", color=COLORS["teal"], fontcolor=COLORS["teal"])
    g.edge("dec", "roma_match", label="roma", color=COLORS["purple"], fontcolor=COLORS["purple"])

    g.edge("lg_match", "lg_tri", color=COLORS["teal"])
    g.edge("lg_tri", "lg_sweep", color=COLORS["teal"])
    g.edge("lg_sweep", "depth", color=COLORS["teal"])

    g.edge("roma_match", "roma_depth", color=COLORS["purple"])
    g.edge("roma_depth", "depth", color=COLORS["purple"])

    g.edge("depth", "fusion")
    g.edge("fusion", "surface")

    # ---- Sparse-mode off-ramp (classical keypoint triangulation only) ---
    # RoMa's sparse mode reuses THIS same keypoint triangulation on sparse
    # correspondences drawn from its warp (runner.py run_roma_sparse_path ->
    # run_triangulation), so it is not a distinct edge off roma_depth, which is
    # a full-mode-only stage; the caption notes the RoMa case in prose.
    g.edge("lg_tri", "sparse", label="sparse", style="dashed", color=COLORS["dark gray"])

    return g


def render(output_dir: Path | str, name: str,
           formats: tuple[str, ...] = ("pdf", "svg", "png")) -> list[Path]:
    """Render the flowchart to *output_dir*/<name>.{fmt}."""
    g = build()
    g.name = name
    dest = Path(output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for fmt in formats:
        g.render(filename=str(dest / name), format=fmt, cleanup=True)
        paths.append(dest / f"{name}.{fmt}")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", "--output-dir", dest="output_dir", default=str(FIGURES_DIR),
                        help="Directory for rendered files.")
    parser.add_argument("--name", default="aquamvs_software_flow", help="Base filename.")
    parser.add_argument("--formats", default="pdf,svg,png", help="Comma-separated output formats.")
    args = parser.parse_args()
    fmts = tuple(f.strip() for f in args.formats.split(",") if f.strip())
    paths = render(args.output_dir, args.name, fmts)
    for p in paths:
        print(f"wrote {p}")


if __name__ == "__main__":
    main()
