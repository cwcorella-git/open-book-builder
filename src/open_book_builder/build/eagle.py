"""EAGLE 9.x .brd parser for the C2 driver board (port of eagle.rs)."""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path

from .f32 import f32
from .footprint_heights import height3d_for_eagle
from .net_category import pick_dominant


def _num(el, key, default=None):
    value = el.get(key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _int(el, key, default=0):
    value = el.get(key)
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def quarter_turn(rot: str | None) -> bool:
    """True when an element's rot attribute (R90, R270, MR90, SR270 ...) turns it a quarter turn."""
    if not rot:
        return False
    digits = "".join(ch for ch in rot if ch.isdigit())
    return bool(digits) and int(digits) % 180 == 90


def decode_rot(rot: str | None) -> tuple[bool, float]:
    if not rot:
        return False, 0.0
    mirror = rot.startswith("M")
    rest = rot[1:] if mirror else rot
    rest = rest[1:] if rest.startswith("R") else rest
    try:
        return mirror, float(rest)
    except ValueError:
        return mirror, 0.0


def net_category_from_class(cls: str | None) -> str:
    return {"1": "power", "2": "ground"}.get(cls or "", "other")


def curve_mid(p1, p2, curve_deg):
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    chord = math.hypot(dx, dy)
    if chord < 1e-6:
        return None
    sagitta = (chord / 2.0) * math.tan(math.radians(curve_deg) / 4.0)
    px, py = -dy / chord, dx / chord
    return ((p1[0] + p2[0]) * 0.5 + px * sagitta, (p1[1] + p2[1]) * 0.5 + py * sagitta)


def _new_silk():
    return {"lines": [], "arcs": [], "circles": []}


def _push_wire_as_silk(start, end, curve, dest):
    mid = None if abs(curve) < 0.01 else curve_mid(start, end, curve)
    if mid is None:
        dest["lines"].append({"start": start, "end": end})
    else:
        dest["arcs"].append({"start": start, "mid": mid, "end": end})


class _Package:
    def __init__(self, name):
        self.name = name
        self.smds, self.pads, self.fab_wires = [], [], []
        self.silk_top, self.silk_bottom = _new_silk(), _new_silk()


def _package_bbox(pkg: _Package, package_name: str) -> dict:
    h3 = height3d_for_eagle(package_name)
    xs0, xs1, ys0, ys1 = [], [], [], []
    for s in pkg.smds:
        hx, hy = abs(s["dx"]) * 0.5, abs(s["dy"]) * 0.5
        xs0.append(s["x"] - hx); xs1.append(s["x"] + hx); ys0.append(s["y"] - hy); ys1.append(s["y"] + hy)
    for p in pkg.pads:
        r = p["diameter"] * 0.5
        xs0.append(p["x"] - r); xs1.append(p["x"] + r); ys0.append(p["y"] - r); ys1.append(p["y"] + r)
    if not xs0:
        for x1, y1, x2, y2 in pkg.fab_wires:
            xs0 += [x1, x2]; xs1 += [x1, x2]; ys0 += [y1, y2]; ys1 += [y1, y2]
    if not xs0:
        return {"width": 1.0, "height": 1.0, "height3d": h3}
    return {"width": f32(max(max(xs1) - min(xs0), 0.5)), "height": f32(max(max(ys1) - min(ys0), 0.5)), "height3d": h3}


def eagle_point(p, origin, rot_deg: float, mirror: bool):
    """Package-local point to board coordinates in EAGLE's own frame (y up).

    A mirrored element (rot starting with M, placed on the bottom) is mirrored in x and then turned the
    other way: checked against the pad flashes in the C2-02 and C2-03 order Gerbers, where this matches all 59 SMD
    pads and the simpler 'mirror then rotate the same way' matches only 30 to 57 of them."""
    x, y = p
    th = math.radians(rot_deg)
    c, s = math.cos(th), math.sin(th)
    if mirror:
        return (origin[0] - x * c + y * s, origin[1] + x * s + y * c)
    return (origin[0] + x * c - y * s, origin[1] + x * s + y * c)


def _build_pads(pkg: _Package, element: str, pad_net: dict, mirror: bool = False) -> list[dict]:
    """Pads in the view's convention: y down, local to the component, turned by the component's stored
    rotation (which is the element's angle, reversed when mirrored)."""
    sign = -1.0 if mirror else 1.0  # mirrored elements flip x here and are turned the other way
    pads = []
    for s in pkg.smds:
        pad = {"number": s["name"], "x": f32(sign * s["x"]), "y": f32(-s["y"]), "shape": "rect",
               "size": [f32(abs(s["dx"])), f32(abs(s["dy"]))], "throughHole": False}
        if (element, s["name"]) in pad_net:
            pad["netName"] = pad_net[(element, s["name"])]
        pads.append(pad)
    for p in pkg.pads:
        pad = {"number": p["name"], "x": f32(sign * p["x"]), "y": f32(-p["y"]), "shape": "circle",
               "size": [f32(p["diameter"]), f32(p["diameter"])], "throughHole": True}
        if (element, p["name"]) in pad_net:
            pad["netName"] = pad_net[(element, p["name"])]
        pads.append(pad)
    return pads


def _emit_layer_silk(local, origin, rot, mirror, layer_is_top, top, bottom):
    dest = top if (layer_is_top ^ mirror) else bottom
    tf = lambda p: eagle_point(p, origin, rot, mirror)
    for ln in local["lines"]:
        dest["lines"].append({"start": tf(ln["start"]), "end": tf(ln["end"])})
    for arc in local["arcs"]:
        dest["arcs"].append({"start": tf(arc["start"]), "mid": tf(arc["mid"]), "end": tf(arc["end"])})
    for c in local["circles"]:
        dest["circles"].append({"center": tf(c["center"]), "radius": c["radius"]})


def _fix_silk(layer: dict, height: float) -> dict:
    """Round every number in a silk layer to f32 for output, turning EAGLE's y-up into the view's y-down."""
    pt = lambda p: [f32(p[0]), f32(height - p[1])]
    return {
        "lines": [{"start": pt(l["start"]), "end": pt(l["end"])} for l in layer["lines"]],
        "arcs": [{"start": pt(a["start"]), "mid": pt(a["mid"]), "end": pt(a["end"])} for a in layer["arcs"]],
        "circles": [{"center": pt(c["center"]), "radius": f32(c["radius"])} for c in layer["circles"]],
    }


def load_c2_board(brd_path: Path, bom: list[dict]) -> dict:
    root = ET.parse(brd_path).getroot()
    packages: dict[tuple[str, str], _Package] = {}
    outline_wires, holes, elements, nets, traces, vias = [], [], [], [], [], []
    silk_top, silk_bottom = _new_silk(), _new_silk()

    def walk(node, in_plain=False, in_elements=False, library=None, package=None, signal=None):
        tag = node.tag
        if tag == "plain":
            in_plain = True
        elif tag == "elements":
            in_elements = True
        elif tag == "library":
            library = node.get("name", "")
        elif tag == "package":
            package = _Package(node.get("name", ""))
        elif tag == "signal":
            signal = {"name": node.get("name", ""), "category": net_category_from_class(node.get("class")),
                      "connectedPads": []}
        elif tag == "element" and in_elements:
            elements.append({"name": node.get("name", ""), "library": node.get("library", ""),
                             "package": node.get("package", ""), "x": _num(node, "x", 0.0),
                             "y": _num(node, "y", 0.0), "rot": node.get("rot")})
        elif tag == "wire" and in_plain:
            layer = _int(node, "layer")
            p1 = (_num(node, "x1", 0.0), _num(node, "y1", 0.0))
            p2 = (_num(node, "x2", 0.0), _num(node, "y2", 0.0))
            if layer == 20:
                outline_wires.append(p1 + p2)
            elif layer in (21, 22):
                _push_wire_as_silk(p1, p2, _num(node, "curve", 0.0), silk_top if layer == 21 else silk_bottom)
        elif tag == "circle" and in_plain:
            layer, radius = _int(node, "layer"), _num(node, "radius", 0.0)
            if layer in (21, 22) and radius > 0:
                (silk_top if layer == 21 else silk_bottom)["circles"].append(
                    {"center": (_num(node, "x", 0.0), _num(node, "y", 0.0)), "radius": radius})
        elif tag == "wire" and package is not None:
            layer = _int(node, "layer")
            p1 = (_num(node, "x1", 0.0), _num(node, "y1", 0.0))
            p2 = (_num(node, "x2", 0.0), _num(node, "y2", 0.0))
            if layer == 51:
                package.fab_wires.append(p1 + p2)
            elif layer in (21, 22):
                _push_wire_as_silk(p1, p2, _num(node, "curve", 0.0), package.silk_top if layer == 21 else package.silk_bottom)
        elif tag == "circle" and package is not None:
            layer, radius = _int(node, "layer"), _num(node, "radius", 0.0)
            if layer in (21, 22) and radius > 0:
                (package.silk_top if layer == 21 else package.silk_bottom)["circles"].append(
                    {"center": (_num(node, "x", 0.0), _num(node, "y", 0.0)), "radius": radius})
        elif tag == "hole" and in_plain:
            holes.append({"x": f32(_num(node, "x", 0.0)), "y": f32(_num(node, "y", 0.0)),
                          "diameter": f32(_num(node, "drill", 1.0))})
        elif tag == "smd" and package is not None:
            dx, dy = _num(node, "dx", 0.0), _num(node, "dy", 0.0)
            if quarter_turn(node.get("rot")):
                dx, dy = dy, dx  # the pad is turned a quarter turn inside its package
            package.smds.append({"name": node.get("name", ""), "x": _num(node, "x", 0.0), "y": _num(node, "y", 0.0),
                                 "dx": dx, "dy": dy})
        elif tag == "pad" and package is not None:
            diameter = _num(node, "diameter")
            if diameter is None and _num(node, "drill") is not None:
                diameter = _num(node, "drill") * 2.0
            package.pads.append({"name": node.get("name", ""), "x": _num(node, "x", 0.0), "y": _num(node, "y", 0.0),
                                 "diameter": 1.5 if diameter is None else diameter})
        elif tag == "contactref" and signal is not None:
            signal["connectedPads"].append({"ref": node.get("element", ""), "pad": node.get("pad", ""),
                                            "board": "c2-driver"})
        elif tag == "wire" and signal is not None:
            copper = {1: "f-cu", 16: "b-cu"}.get(_int(node, "layer"))
            if copper:
                traces.append({"start": [f32(_num(node, "x1", 0.0)), f32(_num(node, "y1", 0.0))],
                               "end": [f32(_num(node, "x2", 0.0)), f32(_num(node, "y2", 0.0))],
                               "width": f32(_num(node, "width", 0.25)), "layer": copper, "netName": signal["name"]})
        elif tag == "via" and signal is not None:
            diameter = _num(node, "diameter")
            if diameter is None and _num(node, "drill") is not None:
                diameter = _num(node, "drill") * 2.0
            vias.append({"at": [f32(_num(node, "x", 0.0)), f32(_num(node, "y", 0.0))],
                         "diameter": f32(0.6 if diameter is None else diameter), "netName": signal["name"]})

        for child in node:
            walk(child, in_plain, in_elements, library, package, signal)

        if tag == "package" and package is not None and library is not None:
            packages[(library, package.name)] = package
        elif tag == "signal" and signal is not None:
            nets.append(signal)

    walk(root)

    # The virtual display is placed relative to the board's own corner, so it keeps its place if the layout moves.
    corner_x = min([w[0] for w in outline_wires] + [w[2] for w in outline_wires], default=0.0)
    corner_y = min([w[1] for w in outline_wires] + [w[3] for w in outline_wires], default=0.0)
    width = max([0.0] + [v for w in outline_wires for v in (w[0], w[2])])
    height = max([0.0] + [v for w in outline_wires for v in (w[1], w[3])])
    # EAGLE's y axis points up; the app draws y down (as KiCad does). Every y becomes height - y so the
    # board is shown the right way up, and component rotation and local pad coordinates follow (see _build_pads).
    flip = lambda y: f32(height - y)
    edges = [{"kind": "line", "points": [[f32(w[0]), flip(w[1])], [f32(w[2]), flip(w[3])]]} for w in outline_wires]
    holes = [{**h, "y": flip(h["y"])} for h in holes]
    traces = [{**t, "start": [t["start"][0], flip(t["start"][1])], "end": [t["end"][0], flip(t["end"][1])]} for t in traces]
    vias = [{**v, "at": [v["at"][0], flip(v["at"][1])]} for v in vias]

    pad_net = {(c["ref"], c["pad"]): n["name"] for n in nets for c in n["connectedPads"]}
    bom_by_ref = {r: line for line in bom for r in line["refs"]}

    components = []
    for el in elements:
        bom_line = bom_by_ref.get(el["name"])
        if bom_line is None:
            continue  # unpopulated or sub-module parts: U$2, U$3, JP1
        mirror, rotation = decode_rot(el["rot"])
        pkg = packages.get((el["library"], el["package"]))
        bbox = _package_bbox(pkg, el["package"]) if pkg else {"width": 1.0, "height": 1.0, "height3d": 1.0}
        pads = _build_pads(pkg, el["name"], pad_net, mirror) if pkg else []
        if pkg:
            origin = (el["x"], el["y"])
            _emit_layer_silk(pkg.silk_top, origin, rotation, mirror, True, silk_top, silk_bottom)
            _emit_layer_silk(pkg.silk_bottom, origin, rotation, mirror, False, silk_top, silk_bottom)
        comp = {"ref": el["name"], "bomRef": el["name"], "x": f32(el["x"]), "y": flip(el["y"]),
                "rotation": f32((-rotation) % 360 if mirror else rotation), "side": "bottom" if mirror else "top",
                "footprint": f"{el['library']}:{el['package']}", "footprintBbox": bbox, "pads": pads,
                "board": "c2-driver"}
        dominant = pick_dominant(pads)
        if dominant:
            comp["dominantCategory"] = dominant
        if bom_line.get("heroMeshId"):
            comp["heroMeshId"] = bom_line["heroMeshId"]
        components.append(comp)

    display = next((l for l in bom if "Display" in l["refs"]), None)
    if display:
        comp = {"ref": "Display", "bomRef": "Display", "x": f32(corner_x + 65.0), "y": flip(corner_y + 11.94), "rotation": 0.0, "side": "top",
                "footprint": "VIRTUAL_GDEY042T81",
                "footprintBbox": {"width": 95.0, "height": 110.0, "height3d": 1.2}, "pads": [], "board": "c2-driver"}
        if display.get("heroMeshId"):
            comp["heroMeshId"] = display["heroMeshId"]
        components.append(comp)

    return {
        "components": components,
        "outline": {"widthMm": f32(width), "heightMm": f32(height), "holes": holes, "edgeSegments": edges,
                    "silkscreenTop": _fix_silk(silk_top, height), "silkscreenBottom": _fix_silk(silk_bottom, height)},
        "nets": nets, "traces": traces, "vias": vias,
    }
