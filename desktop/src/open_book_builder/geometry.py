"""Small geometry helpers for the board view (board space: millimetres, y down)."""
from __future__ import annotations

import math

from PySide6.QtGui import QPainterPath


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
