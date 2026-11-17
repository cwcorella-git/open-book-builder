"""Triangles for a 3D view of a board: an extruded slab with its holes, and a box for every component."""
from __future__ import annotations

import math

import numpy as np
import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union

from .geometry import component_rect, to_board
from .parts3d import body

THICKNESS = 1.0  # mm, both boards are 1.0 mm
SLAB, WALL = -1, -2  # group numbers for the board body; components use their index in the board's list


def arc_polyline(start, mid, end, step=math.pi / 12):
    """Points along the circular arc through three points, including both ends."""
    (x1, y1), (x2, y2), (x3, y3) = start, mid, end
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-9:
        return [start, end]
    ux = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)) / d
    uy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)) / d
    r = math.hypot(x1 - ux, y1 - uy)
    a1, a2, a3 = (math.atan2(y - uy, x - ux) for y, x in ((y1, x1), (y2, x2), (y3, x3)))
    sweep = (a3 - a1) % (2 * math.pi)
    if (a2 - a1) % (2 * math.pi) > sweep:
        sweep -= 2 * math.pi
    n = max(2, math.ceil(abs(sweep) / step))
    return [(ux + r * math.cos(a1 + sweep * k / n), uy + r * math.sin(a1 + sweep * k / n)) for k in range(n + 1)]


def outline_polygon(board: dict) -> Polygon:
    """The board's outline with its mounting holes cut out, in the dataset's y-down coordinates."""
    lines = []
    for seg in board["outline"]["edgeSegments"]:
        pts = seg["points"]
        lines.append(LineString(arc_polyline(*pts) if seg["kind"] == "arc" and len(pts) == 3 else pts))
    snapped = shapely.set_precision(unary_union(lines), 0.001)  # f32 rounding leaves tiny gaps between segments
    polygons = list(polygonize(snapped))
    if not polygons:
        raise ValueError("The board outline does not close.")
    shape = max(polygons, key=lambda p: p.area)
    for hole in board["outline"]["holes"]:
        shape = shape.difference(Point(hole["x"], hole["y"]).buffer(hole["diameter"] / 2, quad_segs=6))
    return shape


def _flat(poly: Polygon, z: float):
    tris = []
    for t in shapely.constrained_delaunay_triangles(poly).geoms:
        c = list(t.exterior.coords)[:3]
        tris.append([(x, -y, z) for x, y in c])
    return tris


def _walls(poly: Polygon):
    tris = []
    for ring in (poly.exterior, *poly.interiors):
        pts = list(ring.coords)
        for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]):
            a, b = (x1, -y1), (x2, -y2)
            tris.append([(*a, 0.0), (*b, 0.0), (*b, THICKNESS)])
            tris.append([(*a, 0.0), (*b, THICKNESS), (*a, THICKNESS)])
    return tris


def _box(corners, z0: float, z1: float):
    """12 triangles for a box whose footprint is the four corners (board coordinates, y down)."""
    pts = [(x, -y) for x, y in corners]
    lo = [(x, y, z0) for x, y in pts]
    hi = [(x, y, z1) for x, y in pts]
    tris = [[lo[0], lo[1], lo[2]], [lo[0], lo[2], lo[3]], [hi[0], hi[1], hi[2]], [hi[0], hi[2], hi[3]]]
    for i in range(4):
        j = (i + 1) % 4
        tris += [[lo[i], lo[j], hi[j]], [lo[i], hi[j], hi[i]]]
    return tris


COPPER_LIFT = 0.02  # mm, copper sits this far outside each face of the slab


def _mix(a, b, t=0.5):
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))


def _lift(triangles: np.ndarray, z: float) -> np.ndarray:
    """(n, 3, 2) layer triangles in the dataset's coordinates to (n, 3, 3) in the view's (y flipped, at height z)."""
    out = np.empty((len(triangles), 3, 3))
    out[:, :, 0] = triangles[:, :, 0]
    out[:, :, 1] = -triangles[:, :, 1]
    out[:, :, 2] = z
    return out


def build_board(board: dict, slab_color, part_color, panel_color, copper=None, copper_color=None, silk=None, silk_color=None):
    """(triangles (n, 3, 3), colors (n, 3) uint8, groups (n,), detail (n,) bool) for one board, in millimetres, z up.
    The detail mask marks the silkscreen, which the view leaves out of drag frames.

    The slab sits between z = 0 and the board thickness. Parts on the top stand on it, parts on the bottom hang
    below it. A part with a known body (parts3d) is several boxes sharing its group; any other is one box from its
    pads. `copper` maps "top" and "bottom" to (n, 3, 2) layer triangles (fabrication.layer_triangles) drawn as a
    thin layer on that face, and `silk` does the same for silkscreen, a little further out than the copper."""
    tris, colors, groups, detail = [], [], [], []

    def add(new, color, group, fine=False):
        new = np.asarray(new, dtype=np.float64).reshape(-1, 3, 3)
        tris.append(new)
        colors.append(np.tile(np.asarray(color, dtype=np.uint8), (len(new), 1)))
        groups.append(np.full(len(new), group, dtype=np.int32))
        detail.append(np.full(len(new), fine, dtype=bool))

    role_colors = {
        "body": part_color,
        "detail": _mix(part_color, slab_color),
        "panel": panel_color,
        "screen": panel_color,
    }
    outline = outline_polygon(board)
    add(_flat(outline, THICKNESS), slab_color, SLAB)
    add(_flat(outline, 0.0), slab_color, SLAB)
    add(_walls(outline), slab_color, WALL)
    for side, z in (("top", THICKNESS + COPPER_LIFT), ("bottom", -COPPER_LIFT)):
        if copper and copper.get(side) is not None:
            add(_lift(copper[side], z), copper_color or _mix(slab_color, part_color, 0.7), SLAB)
    for side, z in (("top", THICKNESS + 2 * COPPER_LIFT), ("bottom", -2 * COPPER_LIFT)):
        if silk and silk.get(side) is not None:
            add(_lift(silk[side], z), silk_color or part_color, SLAB, fine=True)
    for index, comp in enumerate(board["components"]):
        rect = component_rect(comp)
        height = comp["footprintBbox"]["height3d"]
        top_side = comp["side"] == "top"

        def put(x0, y0, x1, y1, z0, z1, color):
            corners = [to_board(comp, x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
            lo, hi = (THICKNESS + z0, THICKNESS + z1) if top_side else (-z1, -z0)
            add(_box(corners, lo, hi), color, index)

        parts = body(comp.get("heroMeshId"), rect, height)
        if parts:
            for x0, y0, x1, y1, z0, z1, role in parts:
                put(x0, y0, x1, y1, z0, z1, role_colors[role])
        else:
            virtual = comp["footprint"].startswith("VIRTUAL")
            put(*rect, 0.0, height, panel_color if virtual else part_color)
    return np.concatenate(tris), np.concatenate(colors), np.concatenate(groups), np.concatenate(detail)


def board_mesh(*args, **kwargs):
    """build_board without the detail mask: (triangles, colors, groups)."""
    return build_board(*args, **kwargs)[:3]
