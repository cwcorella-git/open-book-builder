"""Small geometry helpers for the board view (board space: millimetres, y down)."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainterPath, QPolygonF


def arc_path(start, mid, end) -> QPainterPath:
    """Path of the circular arc through three points. Falls back to a line if collinear."""
    (x1, y1), (x2, y2), (x3, y3) = start, mid, end
    path = QPainterPath()
    path.moveTo(x1, y1)
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-9:
        path.lineTo(x3, y3)
        return path
    ux = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)) / d
    uy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)) / d
    r = math.hypot(x1 - ux, y1 - uy)
    # Qt angles: degrees, counter-clockwise, measured with y pointing up.
    a1 = math.degrees(math.atan2(-(y1 - uy), x1 - ux))
    a2 = math.degrees(math.atan2(-(y2 - uy), x2 - ux))
    a3 = math.degrees(math.atan2(-(y3 - uy), x3 - ux))
    sweep = (a3 - a1) % 360
    mid_off = (a2 - a1) % 360
    if mid_off > sweep:  # the mid point lies on the other way round
        sweep -= 360
    path.arcTo(ux - r, uy - r, 2 * r, 2 * r, a1, sweep)
    return path


def polygons_to_path(geometry) -> QPainterPath:
    """A shapely (Multi)Polygon as one painter path. Holes are inner rings; odd-even fill keeps them empty."""
    from .build.gerber_geometry import polygons_of

    path = QPainterPath()
    path.setFillRule(Qt.OddEvenFill)
    for polygon in polygons_of(geometry):
        for ring in (polygon.exterior, *polygon.interiors):
            path.addPolygon(QPolygonF([QPointF(x, y) for x, y in ring.coords]))
            path.closeSubpath()
    return path


def component_rect(comp: dict) -> tuple[float, float, float, float]:
    """Body box of a component in its own frame: (left, top, right, bottom). It follows the pads, so it is not
    centred on the origin for asymmetric parts such as the Pico or the FPC connector. Without pads it falls
    back to the stored width and height, centred."""
    pads = comp["pads"]
    if pads:
        return (min(p["x"] - p["size"][0] / 2 for p in pads), min(p["y"] - p["size"][1] / 2 for p in pads),
                max(p["x"] + p["size"][0] / 2 for p in pads), max(p["y"] + p["size"][1] / 2 for p in pads))
    box = comp["footprintBbox"]
    return (-box["width"] / 2, -box["height"] / 2, box["width"] / 2, box["height"] / 2)


def to_board(comp: dict, local_x: float, local_y: float) -> tuple[float, float]:
    """A point in a component's frame to board coordinates (y down): the component's rotation, then its position."""
    theta = math.radians(comp["rotation"])
    c, s = math.cos(theta), math.sin(theta)
    return (comp["x"] + local_x * c + local_y * s, comp["y"] - local_x * s + local_y * c)
