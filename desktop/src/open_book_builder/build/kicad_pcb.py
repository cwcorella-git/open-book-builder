"""KiCad 6 .kicad_pcb parser for the C1 board (port of kicad_pcb.rs)."""
from __future__ import annotations

import math
import re
from pathlib import Path

from . import sexpr
from .f32 import f32
from .footprint_heights import height3d_for
from .net_category import pick_dominant
from .sexpr import find_all_tagged, find_tagged, head, positional

_STAMP = re.compile(r"\((?:tstamp|tedit) [^()]*\)")


def _layer_of(node) -> str | None:
    layer = find_tagged(node, "layer")
    args = positional(layer) if layer else []
    return args[0] if args and isinstance(args[0], str) else None


def _point(node, tag):
    p = find_tagged(node, tag)
    a = positional(p) if p else []
    if len(a) >= 2 and all(isinstance(v, (int, float)) for v in a[:2]):
        return (float(a[0]), float(a[1]))
    return None


def _parse_at(node):
    a = positional(node)
    if len(a) < 2 or not all(isinstance(v, (int, float)) for v in a[:2]):
        return None
    rot = float(a[2]) if len(a) > 2 and isinstance(a[2], (int, float)) else 0.0
    return float(a[0]), float(a[1]), rot


def _reference_of(fp) -> str | None:
    for t in find_all_tagged(fp, "fp_text"):
        a = positional(t)
        if a and isinstance(a[0], sexpr.Sym) and a[0] == "reference" and len(a) > 1 and isinstance(a[1], str):
            return a[1]
    return None


def _largest_drill(fp) -> float | None:
    best = None
    for pad in find_all_tagged(fp, "pad"):
        d = find_tagged(pad, "drill")
        a = positional(d) if d else []
        if a and isinstance(a[0], (int, float)):
            best = float(a[0]) if best is None else max(best, float(a[0]))
    return best


def _parse_pad(pad):
    a = positional(pad)
    if len(a) < 3:
        return None
    num = a[0]
    number = num if isinstance(num, str) else str(num)
    type_sym = str(a[1]) if isinstance(a[1], sexpr.Sym) else ""
    shape_sym = str(a[2]) if isinstance(a[2], sexpr.Sym) else ""
    at = find_tagged(pad, "at")
    parsed = _parse_at(at) if at else None
    size = find_tagged(pad, "size")
    sa = positional(size) if size else []
    if parsed is None or len(sa) < 2:
        return None
    net = find_tagged(pad, "net")
    na = positional(net) if net else []
    net_name = na[1] if len(na) > 1 and isinstance(na[1], str) else None
    out = {"number": number, "x": f32(parsed[0]), "y": f32(parsed[1]),
           "shape": shape_sym if shape_sym in ("rect", "roundrect", "circle", "oval") else "rect",
           "size": [f32(sa[0]), f32(sa[1])], "throughHole": type_sym in ("thru_hole", "np_thru_hole")}
    if net_name is not None:
        out["netName"] = net_name
    return out


def _bbox(pads, fp_name):
    h3 = height3d_for(fp_name)
    if not pads:
        return {"width": 1.0, "height": 1.0, "height3d": h3}
    minx = min(p["x"] - p["size"][0] * 0.5 for p in pads)
    maxx = max(p["x"] + p["size"][0] * 0.5 for p in pads)
    miny = min(p["y"] - p["size"][1] * 0.5 for p in pads)
    maxy = max(p["y"] + p["size"][1] * 0.5 for p in pads)
    return {"width": f32(max(maxx - minx, 0.5)), "height": f32(max(maxy - miny, 0.5)), "height3d": h3}


def _transform(p, origin, rot_deg, mirror):
    x, y = p
    if mirror:
        x = -x
    t = math.radians(rot_deg)
    s, c = math.sin(t), math.cos(t)
    return [f32(origin[0] + x * c - y * s), f32(origin[1] + x * s + y * c)]


def _silk_face(layer):
    return {"F.SilkS": "top", "B.SilkS": "bottom"}.get(layer)


def _new_silk():
    return {"lines": [], "arcs": [], "circles": []}


def _circle_radius(center, edge):
    return f32(math.hypot(edge[0] - center[0], edge[1] - center[1]))


def _footprint_silk(fp, origin, rotation, mirror, fp_side, silk):
    for child in fp:
        tag = head(child)
        if tag is None:
            continue
        layer = _layer_of(child)
        face = _silk_face(layer) if layer else None
        if face is None:
            continue
        dest = "top" if face == fp_side else "bottom"  # F.SilkS follows the footprint's own side
        tf = lambda p: _transform(p, origin, rotation, mirror)
        if tag == "fp_line":
            s, e = _point(child, "start"), _point(child, "end")
            if s and e:
                silk[dest]["lines"].append({"start": tf(s), "end": tf(e)})
        elif tag == "fp_arc":
            s, m, e = _point(child, "start"), _point(child, "mid"), _point(child, "end")
            if s and m and e:
                silk[dest]["arcs"].append({"start": tf(s), "mid": tf(m), "end": tf(e)})
        elif tag == "fp_circle":
            c, e = _point(child, "center"), _point(child, "end")
            if c and e:
                silk[dest]["circles"].append({"center": tf(c), "radius": _circle_radius(c, e)})


def _pt(p):
    return [f32(p[0]), f32(p[1])]


def load_c1_board(pcb_path: Path, c1_bom: list[dict]) -> dict:
    text = _STAMP.sub("", pcb_path.read_text(encoding="utf-8"))
    root = sexpr.parse(text)
    if head(root) != "kicad_pcb":
        raise ValueError(f"expected (kicad_pcb ...), got {head(root)!r}")

    bom_by_ref = {r: line for line in c1_bom if line["board"] == "c1-main" for r in line["refs"]}
    components, holes, edges, traces, vias = [], [], [], [], []
    silk = {"top": _new_silk(), "bottom": _new_silk()}

    for child in positional(root):
        tag = head(child)
        if tag == "footprint":
            _classify_footprint(child, bom_by_ref, components, holes, silk)
        elif tag in ("gr_line", "gr_arc"):
            layer = _layer_of(child)
            if layer == "Edge.Cuts":
                if tag == "gr_line":
                    s, e = _point(child, "start"), _point(child, "end")
                    if s and e:
                        edges.append({"kind": "line", "points": [_pt(s), _pt(e)]})
                else:
                    s, m, e = _point(child, "start"), _point(child, "mid"), _point(child, "end")
                    if s and m and e:
                        edges.append({"kind": "arc", "points": [_pt(s), _pt(m), _pt(e)]})
            elif layer and _silk_face(layer):
                face = _silk_face(layer)
                if tag == "gr_line":
                    s, e = _point(child, "start"), _point(child, "end")
                    if s and e:
                        silk[face]["lines"].append({"start": _pt(s), "end": _pt(e)})
                else:
                    s, m, e = _point(child, "start"), _point(child, "mid"), _point(child, "end")
                    if s and m and e:
                        silk[face]["arcs"].append({"start": _pt(s), "mid": _pt(m), "end": _pt(e)})
        elif tag == "gr_circle":
            layer = _layer_of(child)
            face = _silk_face(layer) if layer else None
            c, e = _point(child, "center"), _point(child, "end")
            if face and c and e:
                silk[face]["circles"].append({"center": _pt(c), "radius": _circle_radius(c, e)})
        elif tag == "segment":
            layer = _layer_of(child)
            copper = {"F.Cu": "f-cu", "B.Cu": "b-cu"}.get(layer)
            s, e = _point(child, "start"), _point(child, "end")
            if copper and s and e:
                w = find_tagged(child, "width")
                wa = positional(w) if w else []
                net = find_tagged(child, "net")
                na = positional(net) if net else []
                seg = {"start": _pt(s), "end": _pt(e), "layer": copper,
                       "width": f32(wa[0]) if wa and isinstance(wa[0], (int, float)) else 0.25}
                if len(na) > 1 and isinstance(na[1], str):
                    seg["netName"] = na[1]
                traces.append(seg)
        elif tag == "via":
            at = _point(child, "at")
            if at:
                size = find_tagged(child, "size")
                sa = positional(size) if size else []
                net = find_tagged(child, "net")
                na = positional(net) if net else []
                via = {"at": _pt(at), "diameter": f32(sa[0]) if sa and isinstance(sa[0], (int, float)) else 0.6}
                if len(na) > 1 and isinstance(na[1], str):
                    via["netName"] = na[1]
                vias.append(via)

    width = max([0.0] + [p[0] for e in edges for p in e["points"]])
    height = max([0.0] + [p[1] for e in edges for p in e["points"]])
    return {
        "components": components,
        "outline": {"widthMm": f32(width), "heightMm": f32(height), "holes": holes, "edgeSegments": edges,
                    "silkscreenTop": silk["top"], "silkscreenBottom": silk["bottom"]},
        "nets": [], "traces": traces, "vias": vias,
    }


def _classify_footprint(fp, bom_by_ref, components, holes, silk):
    args = positional(fp)
    if not args or not isinstance(args[0], str):
        return
    fp_name = args[0]
    side = "bottom" if (_layer_of(fp) or "F.Cu") == "B.Cu" else "top"
    at = find_tagged(fp, "at")
    parsed = _parse_at(at) if at else None
    if parsed is None:
        return
    x, y, rotation = parsed
    ref = _reference_of(fp) or ""
    if fp_name.startswith("MountingHole"):
        holes.append({"x": f32(x), "y": f32(y), "diameter": f32(_largest_drill(fp) or 2.5)})
        return
    bom_line = bom_by_ref.get(ref)
    if bom_line is None:
        return  # artwork and placeholders (REF**, G***)
    _footprint_silk(fp, (x, y), rotation, side == "bottom", side, silk)
    pads = [p for p in (_parse_pad(p) for p in find_all_tagged(fp, "pad")) if p]
    comp = {"ref": ref, "bomRef": ref, "x": f32(x), "y": f32(y), "rotation": f32(rotation), "side": side,
            "footprint": fp_name, "footprintBbox": _bbox(pads, fp_name), "pads": pads, "board": "c1-main"}
    dominant = pick_dominant(pads)
    if dominant:
        comp["dominantCategory"] = dominant
    if bom_line.get("heroMeshId"):
        comp["heroMeshId"] = bom_line["heroMeshId"]
    components.append(comp)
