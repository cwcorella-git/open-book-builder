"""Reader for the RS-274X (Gerber) and Excellon subset that KiCad and EAGLE write for these boards.

Supported: coordinate format and units, circle / rectangle / obround / polygon apertures, aperture macros
(primitives 1, 4, 5, 20 and 21 with arithmetic on parameters), flashes, straight and multi-quadrant arc
draws, regions, dark and clear polarity. Anything else is counted in `Layer.unsupported`, never guessed.

The reader returns plain Python data in millimetres with y pointing up, as written in the file:
- `Layer.ops`: ("flash" | "stroke" | "region", polarity, ...) tuples, where polarity is "D" or "C".
- `Layer.apertures`: id -> list of (exposure, polygon points) in aperture-local coordinates.
"""
from __future__ import annotations

import ast
import math
import operator
import re
from dataclasses import dataclass, field

CIRCLE_SEGMENTS = 32  # points used for a full circle
ARC_STEP = math.pi / 32  # largest angle step when an arc becomes line segments


@dataclass
class Layer:
    ops: list = field(default_factory=list)
    apertures: dict = field(default_factory=dict)  # id -> list of (exposure, [(x, y), ...]) shapes
    round_widths: dict = field(default_factory=dict)  # id -> width, for circle apertures used as pens
    unsupported: dict = field(default_factory=dict)

    def note(self, what: str) -> None:
        self.unsupported[what] = self.unsupported.get(what, 0) + 1


def circle_points(cx: float, cy: float, diameter: float, rotation: float = 0.0, n: int = CIRCLE_SEGMENTS):
    r = diameter / 2
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def rect_points(cx: float, cy: float, w: float, h: float, rotation: float = 0.0):
    pts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    return [rotate(x, y, rotation, cx, cy) for x, y in pts]


def rotate(x: float, y: float, degrees: float, cx: float = 0.0, cy: float = 0.0):
    if not degrees:
        return (x + cx, y + cy)
    a = math.radians(degrees)
    return (x * math.cos(a) - y * math.sin(a) + cx, x * math.sin(a) + y * math.cos(a) + cy)


def obround_points(w: float, h: float):
    """A stadium: the shorter side is the diameter of the two round ends."""
    r = min(w, h) / 2
    pts = []
    if w >= h:
        c = w / 2 - r
        for i in range(CIRCLE_SEGMENTS // 2 + 1):
            a = -math.pi / 2 + math.pi * i / (CIRCLE_SEGMENTS // 2)
            pts.append((c + r * math.cos(a), r * math.sin(a)))
        for i in range(CIRCLE_SEGMENTS // 2 + 1):
            a = math.pi / 2 + math.pi * i / (CIRCLE_SEGMENTS // 2)
            pts.append((-c + r * math.cos(a), r * math.sin(a)))
    else:
        c = h / 2 - r
        for i in range(CIRCLE_SEGMENTS // 2 + 1):
            a = math.pi * i / (CIRCLE_SEGMENTS // 2)
            pts.append((r * math.cos(a), c + r * math.sin(a)))
        for i in range(CIRCLE_SEGMENTS // 2 + 1):
            a = math.pi + math.pi * i / (CIRCLE_SEGMENTS // 2)
            pts.append((r * math.cos(a), -c + r * math.sin(a)))
    return pts


# -- macro parameter arithmetic ------------------------------------------------------------------
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def evaluate(expr: str, params: list[float]) -> float:
    """Evaluate a macro expression such as '$1+$1' or '1.08239X$1' (X means multiply)."""
    text = re.sub(r"\$(\d+)", lambda m: repr(params[int(m.group(1)) - 1] if int(m.group(1)) <= len(params) else 0.0), expr)
    text = re.sub(r"(?<=[\d.)])[xX](?=[\d.($-])", "*", text)

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return -walk(node.operand) if isinstance(node.op, ast.USub) else walk(node.operand)
        raise ValueError(f"unsupported macro expression: {expr!r}")

    return walk(ast.parse(text.strip(), mode="eval"))


def macro_shapes(body: list[str], params: list[float], layer: Layer):
    shapes = []
    for line in body:
        line = line.strip()
        if not line or line.startswith("0 ") or line == "0":
            continue
        parts = [p for p in line.split(",")]
        try:
            code = int(parts[0])
            v = [evaluate(p, params) for p in parts[1:]]
        except (ValueError, IndexError):
            layer.note(f"macro primitive {line[:20]!r}")
            continue
        exposure = int(v[0]) if v else 1
        if code == 1:  # circle: exposure, diameter, cx, cy, [rotation]
            cx, cy = rotate(v[2], v[3], v[4] if len(v) > 4 else 0.0)
            shapes.append((exposure, circle_points(cx, cy, v[1])))
        elif code == 4:  # outline: exposure, n, x0, y0, ... xn, yn, rotation
            n = int(v[1])
            pts = [(v[2 + 2 * i], v[3 + 2 * i]) for i in range(n + 1)]
            rot = v[2 + 2 * (n + 1)] if len(v) > 2 + 2 * (n + 1) else 0.0
            shapes.append((exposure, [rotate(x, y, rot) for x, y in pts[:-1] if True] if pts[0] == pts[-1] else [rotate(x, y, rot) for x, y in pts]))
        elif code == 5:  # regular polygon: exposure, vertices, cx, cy, diameter, rotation
            n, cx, cy, d, rot = int(v[1]), v[2], v[3], v[4], v[5] if len(v) > 5 else 0.0
            pts = [(d / 2 * math.cos(math.radians(rot) + 2 * math.pi * i / n), d / 2 * math.sin(math.radians(rot) + 2 * math.pi * i / n))
                   for i in range(n)]
            shapes.append((exposure, [(x + cx, y + cy) for x, y in pts]))
        elif code == 20:  # vector line: exposure, width, x1, y1, x2, y2, rotation
            w, x1, y1, x2, y2, rot = v[1], v[2], v[3], v[4], v[5], v[6] if len(v) > 6 else 0.0
            dx, dy = x2 - x1, y2 - y1
            length = math.hypot(dx, dy) or 1e-9
            nx, ny = -dy / length * w / 2, dx / length * w / 2
            pts = [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)]
            shapes.append((exposure, [rotate(x, y, rot) for x, y in pts]))
        elif code == 21:  # center line: exposure, width, height, cx, cy, rotation
            w, h, cx, cy, rot = v[1], v[2], v[3], v[4], v[5] if len(v) > 5 else 0.0
            pts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
            shapes.append((exposure, [rotate(x + cx, y + cy, rot) for x, y in pts]))
        else:
            layer.note(f"macro primitive code {code}")
    return shapes


# -- the parser -------------------------------------------------------------------------------------
def arc_points(x0, y0, x1, y1, i, j, clockwise: bool):
    """Points along an arc from (x0, y0) to (x1, y1) with centre at start + (i, j). Multi-quadrant mode."""
    cx, cy = x0 + i, y0 + j
    r = math.hypot(x0 - cx, y0 - cy)
    a0, a1 = math.atan2(y0 - cy, x0 - cx), math.atan2(y1 - cy, x1 - cx)
    if clockwise:
        sweep = (a0 - a1) % (2 * math.pi)
        sweep = -sweep if sweep else -2 * math.pi
    else:
        sweep = (a1 - a0) % (2 * math.pi)
        sweep = sweep if sweep else 2 * math.pi
    steps = max(2, math.ceil(abs(sweep) / ARC_STEP))
    pts = [(cx + r * math.cos(a0 + sweep * k / steps), cy + r * math.sin(a0 + sweep * k / steps)) for k in range(1, steps)]
    return pts + [(x1, y1)]


def parse_gerber(text: str) -> Layer:
    layer = Layer()
    scale, unit = 1e-4, 1.0  # decimals from FS, inches to mm
    macros: dict[str, list[str]] = {}
    aperture_defs: dict[int, tuple[str, list[float]]] = {}
    polarity, current, interp, region = "D", None, "G01", None
    x = y = 0.0
    contour: list = []
    pen_chain: list | None = None

    def number(s: str) -> float:
        return int(s) * scale * unit

    def flush_chain():
        nonlocal pen_chain
        if pen_chain and len(pen_chain) > 1 and current in layer.round_widths:
            layer.ops.append(("stroke", polarity, layer.round_widths[current], pen_chain))
        elif pen_chain and len(pen_chain) > 1:
            layer.note("stroke with a non-circular aperture")
        pen_chain = None

    # split into extended commands (between % ... %) and ordinary data blocks (ending in *)
    pos, blocks = 0, []
    while pos < len(text):
        if text[pos] == "%":
            end = text.index("%", pos + 1)
            blocks.append(("ext", text[pos + 1:end]))
            pos = end + 1
        else:
            end = text.find("*", pos)
            end = len(text) if end < 0 else end
            chunk = text[pos:end].strip()
            if chunk:
                blocks.append(("data", chunk))
            pos = end + 1
        while pos < len(text) and text[pos] in "\r\n ":
            pos += 1

    for kind, block in blocks:
        if kind == "ext":
            statements = [s.strip() for s in block.split("*") if s.strip()]
            head = statements[0] if statements else ""
            if head.startswith("FS"):
                m = re.search(r"X(\d)(\d)", head)
                scale = 10 ** -int(m.group(2))
            elif head.startswith("MO"):
                unit = 25.4 if head.startswith("MOIN") else 1.0
            elif head.startswith("AM"):
                macros[head[2:]] = statements[1:]
            elif head.startswith("ADD"):
                m = re.match(r"ADD(\d+)([A-Za-z_][\w.]*)(?:,(.*))?", head)
                name, args = m.group(2), (m.group(3) or "")
                aperture_defs[int(m.group(1))] = (name, [a for a in args.split("X")] if args else [])
            elif head.startswith("LP"):
                flush_chain()
                polarity = head[2]
            elif head.startswith(("TF", "TA", "TO", "TD", "IN", "IP", "OF", "SF", "IR", "AS", "MI")):
                pass
            elif head.startswith(("SR", "LM", "LR", "LS", "AB")):
                layer.note(head[:2])
            continue
        # data block, possibly with a G code in front
        for g in re.findall(r"G(\d+)", block):
            g = int(g)
            if g in (1, 2, 3):
                interp = f"G0{g}"
            elif g == 36:
                flush_chain()
                region, contour = [], []
            elif g == 37:
                if contour:
                    region.append(contour)
                for c in region:
                    if len(c) > 2:
                        layer.ops.append(("region", polarity, c))
                region, contour = None, []
            elif g == 74:
                layer.note("G74 single-quadrant arcs")
        body = re.sub(r"G\d+", "", block)
        if body.startswith("M"):
            continue
        m = re.fullmatch(r"D(\d+)", body)
        if m and int(m.group(1)) >= 10:
            flush_chain()
            current = int(m.group(1))
            if current not in layer.apertures and current in aperture_defs:
                name, args = aperture_defs[current]
                if name == "C":
                    d = float(args[0]) * unit
                    layer.apertures[current] = [(1, circle_points(0, 0, d))]
                    layer.round_widths[current] = d
                elif name == "R":
                    layer.apertures[current] = [(1, rect_points(0, 0, float(args[0]) * unit, float(args[1]) * unit))]
                elif name == "O":
                    layer.apertures[current] = [(1, obround_points(float(args[0]) * unit, float(args[1]) * unit))]
                elif name == "P":
                    d, n = float(args[0]) * unit, int(float(args[1]))
                    rot = float(args[2]) if len(args) > 2 else 0.0
                    layer.apertures[current] = [(1, [(d / 2 * math.cos(math.radians(rot) + 2 * math.pi * k / n),
                                                      d / 2 * math.sin(math.radians(rot) + 2 * math.pi * k / n)) for k in range(n)])]
                elif name in macros:
                    layer.apertures[current] = macro_shapes(macros[name], [float(a) for a in args], layer)
                    if unit != 1.0:
                        layer.apertures[current] = [(e, [(px * unit, py * unit) for px, py in pts]) for e, pts in layer.apertures[current]]
                else:
                    layer.note(f"aperture {name}")
            continue
        coords = dict(re.findall(r"([XYIJ])(-?\d+)", body))
        d_code = re.search(r"D0([123])$", body)
        nx = number(coords["X"]) if "X" in coords else x
        ny = number(coords["Y"]) if "Y" in coords else y
        i = number(coords["I"]) if "I" in coords else 0.0
        j = number(coords["J"]) if "J" in coords else 0.0
        op = int(d_code.group(1)) if d_code else None
        if op is None and not coords:
            continue
        if op is None:
            op = 1  # modal D01 from an earlier block
        if op == 3:  # flash
            flush_chain()
            if region is None and current in layer.apertures:
                layer.ops.append(("flash", polarity, current, nx, ny))
        elif op == 2:  # move
            if region is not None:
                if contour:
                    region.append(contour)
                contour = [(nx, ny)]
            else:
                flush_chain()
                pen_chain = [(nx, ny)]
        else:  # draw
            if interp == "G01":
                new = [(nx, ny)]
            else:
                new = arc_points(x, y, nx, ny, i, j, clockwise=(interp == "G02"))
            if region is not None:
                if not contour:
                    contour = [(x, y)]
                contour.extend(new)
            else:
                if pen_chain is None:
                    pen_chain = [(x, y)]
                pen_chain.extend(new)
        x, y = nx, ny
    flush_chain()
    return layer


# -- Excellon drill files -----------------------------------------------------------------------------
def parse_drill(text: str) -> list[tuple[float, float, float]]:
    """Drill hits as (x, y, diameter) in mm. Handles decimal coordinates and fixed-format ones."""
    unit, decimals = 1.0, 3
    tools: dict[str, float] = {}
    current = None
    hits = []
    header = True
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";") and "FORMAT" not in line:
            continue
        if header:
            if line.startswith("INCH"):
                unit = 25.4
            elif line.startswith("METRIC"):
                unit = 1.0
                m = re.search(r",\s*0*(\d*)\.(\d+)", line)
                if m:
                    decimals = len(m.group(2))
            m = re.match(r"T(\d+)C([\d.]+)", line)
            if m:
                tools[m.group(1)] = float(m.group(2)) * unit
            if line == "%" or line == "M95":
                header = False
            continue
        m = re.match(r"T(\d+)$", line)
        if m:
            current = tools.get(m.group(1)) or tools.get(str(int(m.group(1))))
            continue
        m = re.match(r"X(-?[\d.]+)Y(-?[\d.]+)", line)
        if m and current:
            def val(s: str) -> float:
                return float(s) * unit if "." in s else int(s) / 10 ** decimals * unit
            hits.append((val(m.group(1)), val(m.group(2)), current))
    return hits
