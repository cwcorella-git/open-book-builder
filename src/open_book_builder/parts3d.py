"""Simple multi-box bodies for the five parts the old three.js tool drew in detail (ported from hero-meshes.ts).

Each body is a list of boxes in the component's own frame: (x0, y0, x1, y1, z0, z1, role). x and y are millimetres in the
frame `component_rect` describes, and z is the height above the face the part is mounted on. Roles are "body", "detail",
"panel" and "screen"; the board view maps them to palette colors. Rounded shapes (the battery cells), the printed labels
and the screen texture of the old tool are not reproduced: cells are boxes, labels are left out.
"""
from __future__ import annotations

Box = tuple[float, float, float, float, float, float, str]


def _span(lo: float, hi: float, count: int, margin: float):
    """Centres of `count` evenly spaced nubs between lo + margin and hi - margin."""
    span = (hi - lo) - 2 * margin
    return [lo + margin + (i + 0.5) / count * span for i in range(count)]


def _nubs(rect, count: int, margin: float, nx: float, ny: float, z1: float, overhang: float) -> list[Box]:
    left, top, right, bottom = rect
    boxes: list[Box] = []
    for y in _span(top, bottom, count, margin):
        boxes.append((left - overhang, y - ny / 2, left - overhang + nx, y + ny / 2, 0.0, z1, "detail"))
        boxes.append((right + overhang - nx, y - ny / 2, right + overhang, y + ny / 2, 0.0, z1, "detail"))
    return boxes


def pi_pico(rect, height3d: float) -> list[Box]:
    left, top, right, bottom = rect
    cx = (left + right) / 2
    return [
        (left, top, right, bottom, 0.0, 1.0, "body"),
        *_nubs(rect, 20, 2.0, 2.0, 1.2, 0.6, 0.8),
        (cx - 4, top, cx + 4, top + 6, 1.0, 4.0, "detail"),  # the USB connector, on the short edge
    ]


def c2_module(rect, height3d: float) -> list[Box]:
    left, top, right, bottom = rect
    cx, cy = (left + right) / 2, (top + bottom) / 2
    chips = [(0, 6, 6, 5), (-3, -4, 3, 2), (3, -4, 3, 2), (0, -9, 4, 1.5)]
    return [
        (left, top, right, bottom, 0.0, 1.0, "body"),
        *_nubs(rect, 12, 1.5, 1.6, 1.0, 0.5, 0.65),
        *[(cx + x - w / 2, cy + y - d / 2, cx + x + w / 2, cy + y + d / 2, 1.0, 1.5, "detail") for x, y, w, d in chips],
    ]


def battery_holder(rect, height3d: float) -> list[Box]:
    left, top, right, bottom = rect
    cx, cy = (left + right) / 2, (top + bottom) / 2
    width, depth = right - left, bottom - top
    base = 2.0
    radius = min(5.25, (depth - 1.0) / 4)  # two AAA cells side by side, squeezed to fit the holder
    length = min(width - 12, 48)
    offset = depth / 2 - radius - 0.5
    boxes: list[Box] = [(left, top, right, bottom, 0.0, base, "body")]
    for sign in (-1, 1):
        y = cy + sign * offset
        boxes.append((cx - length / 2, y - radius, cx + length / 2, y + radius, base, base + 2 * radius, "detail"))
        boxes.append((cx + length / 2, y - 0.4, cx + length / 2 + 1.2, y + 0.4, base, base + 1.2, "panel"))
    return boxes


def micro_sd(rect, height3d: float) -> list[Box]:
    left, top, right, bottom = rect
    cy = (top + bottom) / 2
    housing = max(height3d, 1.5)
    slot_h = min(1.0, housing * 0.6)
    depth = (bottom - top) * 0.75
    return [
        (left, top, right, bottom, 0.0, housing, "body"),
        (left - 0.01, cy - depth / 2, left + 0.39, cy + depth / 2, housing - slot_h - 0.2, housing - 0.2, "detail"),
    ]


def display_panel(rect, height3d: float) -> list[Box]:
    left, top, right, bottom = rect
    cx, cy = (left + right) / 2, (top + bottom) / 2
    bezel = max(height3d, 1.2)
    return [
        (left, top, right, bottom, 0.0, bezel, "detail"),
        (cx - 42.5, cy - 52.5, cx + 42.5, cy + 52.5, bezel, bezel + 0.1, "screen"),
        (cx - 12, top - 2, cx + 12, top, bezel * 0.3, bezel * 0.3 + 0.3, "panel"),  # the flex cable
    ]


BUILDERS = {
    "pi-pico": pi_pico,
    "c2-module": c2_module,
    "keystone-1022": battery_holder,
    "mem2075": micro_sd,
    "gdew042t2": display_panel,
}


def body(hero_id: str | None, rect, height3d: float) -> list[Box] | None:
    """The boxes for a known part, or None so the caller draws one box from the pads."""
    build = BUILDERS.get(hero_id or "")
    return build(rect, height3d) if build else None
