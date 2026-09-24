"""
Headless Open3D mesh rendering for the manuscript's 3D figures (Figs. 2 and 3).

Viewpoints follow AquaMVS's own convention (aquamvs.visualization.scene.
compute_canonical_viewpoints: "top" and "oblique"), so renders match the pipeline's
viz/mesh_*.png. Rendering itself is done here rather than through AquaMVS because:

  - AquaMVS skips its OffscreenRenderer on Linux without $DISPLAY, although EGL
    headless works on a GPU machine (Open3D logs "EGL headless mode enabled");
  - Filament's post-processing (tone mapping) washes out vertex colours and greys
    the background, and AquaMVS does not expose the switch;
  - scale bars and axis triads need the exact camera, which `project` provides.

The mesh is drawn unlit with its vertex colours (as AquaMVS does), on white.
Needs a GPU with EGL (Linux) or a display.
"""

from __future__ import annotations

from dataclasses import dataclass

import matplotlib.patheffects as pe
import numpy as np
import open3d as o3d
from aquamvs.visualization.scene import compute_canonical_viewpoints

FOV_DEG = 60.0  # vertical field of view, as AquaMVS's renderer uses


@dataclass(frozen=True)
class Camera:
    eye: np.ndarray
    center: np.ndarray
    up: np.ndarray
    width: int
    height: int
    fov_deg: float = FOV_DEG

    def basis(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        fwd = self.center - self.eye
        fwd = fwd / np.linalg.norm(fwd)
        right = np.cross(fwd, self.up)
        right = right / np.linalg.norm(right)
        true_up = np.cross(right, fwd)
        return fwd, right, true_up

    def focal_px(self) -> float:
        return (self.height / 2.0) / np.tan(np.radians(self.fov_deg) / 2.0)

    def project(self, pts: np.ndarray) -> np.ndarray:
        """World points (N, 3) -> pixel coordinates (N, 2), origin top-left."""
        fwd, right, true_up = self.basis()
        d = np.atleast_2d(pts) - self.eye
        z = d @ fwd
        f = self.focal_px()
        u = self.width / 2.0 + f * (d @ right) / z
        v = self.height / 2.0 - f * (d @ true_up) / z
        return np.stack([u, v], axis=1)

    def unproject(self, px: tuple[float, float], at: np.ndarray) -> np.ndarray:
        """World point on the plane through *at* (normal to the view axis) seen at pixel *px*."""
        fwd, right, true_up = self.basis()
        f = self.focal_px()
        ray = fwd + ((px[0] - self.width / 2.0) / f) * right - ((px[1] - self.height / 2.0) / f) * true_up
        depth = float((np.asarray(at) - self.eye) @ fwd)
        return self.eye + ray * depth

    def mm_per_px_at(self, point: np.ndarray) -> float:
        """Image scale at a world point's depth along the view axis (perspective)."""
        fwd, _, _ = self.basis()
        return float((np.asarray(point) - self.eye) @ fwd) / self.focal_px() * 1000.0


def canonical_camera(mesh: o3d.geometry.TriangleMesh, view: str,
                     width: int, height: int) -> Camera:
    """AquaMVS's canonical 'top' or 'oblique' camera for this mesh's bounding box."""
    bb = mesh.get_axis_aligned_bounding_box()
    vp = compute_canonical_viewpoints(np.asarray(bb.min_bound), np.asarray(bb.max_bound))[view]
    return Camera(vp["eye"], vp["center"], vp["up"], width, height)


def render(geometries: list[o3d.geometry.Geometry], cam: Camera) -> np.ndarray:
    """Render unlit vertex-coloured geometry on white; returns an (H, W, 3) uint8 image."""
    r = o3d.visualization.rendering.OffscreenRenderer(cam.width, cam.height)
    r.scene.set_background(np.array([1.0, 1.0, 1.0, 1.0]))
    r.scene.view.set_post_processing(False)  # keep true vertex colours and white
    mat = o3d.visualization.rendering.MaterialRecord()
    mat.shader = "defaultUnlit"
    for i, g in enumerate(geometries):
        r.scene.add_geometry(f"g{i}", g, mat)
    r.setup_camera(cam.fov_deg, cam.center, cam.eye, cam.up)
    img = np.asarray(r.render_to_image()).copy()
    del r
    return img


def crop_box(img: np.ndarray, tol: int = 8, pad: int = 20) -> tuple[int, int, int, int]:
    """(r0, r1, c0, c1) of the non-white content, padded."""
    mask = np.any(np.abs(img.astype(np.int16) - 255) > tol, axis=2)
    rows, cols = np.where(mask.any(1))[0], np.where(mask.any(0))[0]
    if rows.size == 0:
        return 0, img.shape[0], 0, img.shape[1]
    return (max(0, rows[0] - pad), min(img.shape[0], rows[-1] + pad + 1),
            max(0, cols[0] - pad), min(img.shape[1], cols[-1] + pad + 1))


def load_mesh(path) -> o3d.geometry.TriangleMesh:
    mesh = o3d.io.read_triangle_mesh(str(path))
    if len(mesh.vertices) == 0:
        raise FileNotFoundError(f"empty or missing mesh: {path}")
    return mesh


def camera_looking(center: np.ndarray, direction: np.ndarray, up: np.ndarray,
                   distance: float, width: int, height: int, fov_deg: float) -> Camera:
    """Camera at *distance* from *center*, looking along *direction*."""
    d = np.asarray(direction, float)
    d = d / np.linalg.norm(d)
    return Camera(np.asarray(center) - distance * d, np.asarray(center, float),
                  np.asarray(up, float), width, height, fov_deg)


def draw_scale_bar(ax, cam: Camera, at: np.ndarray, length_mm: float,
                   xy_frac=(0.06, 0.06), color="black") -> None:
    """Horizontal scale bar in image space, valid at the depth of world point *at*."""
    px = length_mm / cam.mm_per_px_at(at)
    x0 = ax.get_xlim()[0] + xy_frac[0] * abs(ax.get_xlim()[1] - ax.get_xlim()[0])
    ybot = max(ax.get_ylim())
    y0 = ybot - xy_frac[1] * abs(ax.get_ylim()[1] - ax.get_ylim()[0])
    ax.plot([x0, x0 + px], [y0, y0], color=color, linewidth=2.0, solid_capstyle="butt")
    label = f"{length_mm / 10:g} cm" if length_mm >= 10 else f"{length_mm:g} mm"
    ax.text(x0 + px / 2, y0 - 0.012 * abs(ax.get_ylim()[1] - ax.get_ylim()[0]), label,
            ha="center", va="bottom", fontsize=7, color=color)


def draw_triad(ax, cam: Camera, origin: np.ndarray, length_m: float,
               labels=("X", "Y", "Z"), colors=("#CC3311", "#228833", "#004488"),
               fontsize: float = 8) -> None:
    """World X/Y/Z axes of *length_m* from *origin*, projected into the image.

    An axis within ~25 deg of the line of sight is drawn as a circled cross (pointing
    away from the viewer) or dot (towards), not as a foreshortened arrow.
    """
    halo = [pe.withStroke(linewidth=2.2, foreground="white")]
    o = cam.project(origin)[0]
    fwd, _, _ = cam.basis()
    for axis, lab, col in zip(np.eye(3), labels, colors):
        if abs(axis @ fwd) > np.cos(np.radians(25)):
            sym = r"$\otimes$" if axis @ fwd > 0 else r"$\odot$"
            ax.text(o[0], o[1], sym, ha="center", va="center", fontsize=fontsize + 3,
                    color=col, path_effects=halo)
            ax.text(o[0] + 0.012 * cam.width, o[1] + 0.012 * cam.height, lab, ha="left",
                    va="top", fontsize=fontsize, color=col, path_effects=halo)
            continue
        tip = cam.project(np.asarray(origin) + length_m * axis)[0]
        ax.annotate("", xy=tip, xytext=o,
                    arrowprops=dict(arrowstyle="-|>", color=col, lw=1.4, mutation_scale=9,
                                    path_effects=halo))
        d = (tip - o) / np.linalg.norm(tip - o)
        ax.text(*(tip + 0.018 * cam.width * d), lab, ha="center", va="center",
                fontsize=fontsize, color=col, path_effects=halo)
