"""Turn a parsed Gerber layer into clean polygons (shapely), ready to draw.

Dark objects are merged into one shape, clear-polarity objects are cut out of what was drawn before them, and every
pad, trace and pour ends up as polygons with holes, so drawing needs no knowledge of Gerber at all.
"""
from __future__ import annotations

import zipfile
from functools import lru_cache
from pathlib import Path

import shapely
from shapely.affinity import affine_transform
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid

from .gerber import Layer, parse_drill, parse_gerber


def _polygon(points) -> Polygon | None:
    if len(points) < 3:
        return None
    poly = Polygon(points)
    if not poly.is_valid:
        poly = make_valid(poly)
    return poly if not poly.is_empty else None


def _shifted(points, x: float, y: float):
    return [(px + x, py + y) for px, py in points]


def _flash(layer: Layer, aperture: int, x: float, y: float):
    parts_on, parts_off = [], []
    for exposure, points in layer.apertures[aperture]:
        poly = _polygon(_shifted(points, x, y))
        if poly is not None:
            (parts_on if exposure else parts_off).append(poly)
    if not parts_on:
        return None
    shape = unary_union(parts_on)
    return shape.difference(unary_union(parts_off)) if parts_off else shape


def layer_polygons(layer: Layer, transform=(1.0, 1.0, 0.0, 0.0)):
    """Merged geometry of a layer. transform is (sx, sy, tx, ty): x' = sx*x + tx and y' = sy*y + ty."""
    result = Polygon()
    run: list = []
    run_polarity = "D"

    def finish():
        nonlocal result, run
        if not run:
            return
        merged = unary_union(run)
        result = result.union(merged) if run_polarity == "D" else result.difference(merged)
        run = []

    for op in layer.ops:
        kind, polarity = op[0], op[1]
        if polarity != run_polarity:
            finish()
            run_polarity = polarity
        if kind == "flash":
            geom = _flash(layer, op[2], op[3], op[4])
        elif kind == "stroke":
            geom = LineString(op[3]).buffer(op[2] / 2, quad_segs=8) if len(set(op[3])) > 1 else None
        else:
            geom = _polygon(op[2])
        if geom is not None and not geom.is_empty:
            run.append(geom)
    finish()
    sx, sy, tx, ty = transform
    return affine_transform(result, [sx, 0, 0, sy, tx, ty])


def polygons_of(geometry) -> list[Polygon]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry]
    return [g for g in getattr(geometry, "geoms", []) if isinstance(g, Polygon)] + [
        p for g in getattr(geometry, "geoms", []) if not isinstance(g, Polygon) for p in polygons_of(g)]


@lru_cache(maxsize=32)
def read_layer(zip_path: str, member_suffix: str, transform: tuple, tolerance: float = 0.0) -> MultiPolygon:
    """Read one layer from an order zip and return its merged polygons. Cached: the first call is the slow one.

    tolerance (mm) drops points that change the outline by less than that. Silkscreen text is plotted as polygons
    with about 200,000 points on the C1; 0.01 mm keeps 98.7 percent of the area with a third of the points."""
    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.endswith(member_suffix))
        layer = parse_gerber(z.read(name).decode(errors="ignore"))
    geometry = layer_polygons(layer, transform)
    if tolerance:
        geometry = shapely.simplify(geometry, tolerance, preserve_topology=False)
        if not geometry.is_valid:
            geometry = make_valid(geometry)
    return geometry


def read_drills(zip_path: str, member_suffixes: tuple[str, ...], transform: tuple) -> list[tuple[float, float, float]]:
    sx, sy, tx, ty = transform
    hits = []
    with zipfile.ZipFile(zip_path) as z:
        for suffix in member_suffixes:
            name = next(n for n in z.namelist() if n.endswith(suffix))
            hits += [(sx * x + tx, sy * y + ty, d) for x, y, d in parse_drill(z.read(name).decode(errors="ignore"))]
    return hits
