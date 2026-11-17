"""Where each board's order files are and how their coordinates map to the dataset's (y down) view."""
from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
import shapely

from .build.gerber_geometry import read_drills, read_layer
from .dataset import find_data_dir

FABRICATION = {
    "c1-main": {
        "zip": "OSO-BOOK-C1-05-rounded.zip",
        "copper": {"top": "-F_Cu.gbr", "bottom": "-B_Cu.gbr"},
        "silk": {"top": "-F_Silkscreen.gbr", "bottom": "-B_Silkscreen.gbr"},
        "drills": ("-PTH.drl", "-NPTH.drl"),
        "y_is_height_minus": False,  # KiCad plots y as the negative of the design's y
    },
    "c2-driver": {
        "zip": "OSO-BOOK-C2-03.zip",
        "copper": {"top": "copper_top.gbr", "bottom": "copper_bottom.gbr"},
        "silk": {"top": "silkscreen_top.gbr", "bottom": "silkscreen_bottom.gbr"},
        "drills": (".xln",),
        "y_is_height_minus": True,  # EAGLE plots with y up, in the board's own frame
    },
}

_lock = threading.Lock()  # one slow read at a time, so a background warm-up and the window never repeat work
_triangle_lock = threading.Lock()
_triangles: dict = {}
TRIANGLE_TOLERANCE = 0.05  # mm: polygons are simplified this much before the 3D view triangulates them


def zip_path(board: str) -> Path:
    return find_data_dir() / "fabrication" / FABRICATION[board]["zip"]


def available(board: str) -> bool:
    return board in FABRICATION and zip_path(board).is_file()


def transform(board: str, height_mm: float) -> tuple:
    """(sx, sy, tx, ty) taking Gerber coordinates to the dataset's y-down board coordinates."""
    return (1.0, -1.0, 0.0, height_mm) if FABRICATION[board]["y_is_height_minus"] else (1.0, -1.0, 0.0, 0.0)


def copper(board: str, side: str, height_mm: float):
    with _lock:
        return read_layer(str(zip_path(board)), FABRICATION[board]["copper"][side], transform(board, height_mm), 0.005)


def silkscreen(board: str, side: str, height_mm: float):
    with _lock:
        return read_layer(str(zip_path(board)), FABRICATION[board]["silk"][side], transform(board, height_mm), 0.01)


def drills(board: str, height_mm: float):
    with _lock:
        return read_drills(str(zip_path(board)), FABRICATION[board]["drills"], transform(board, height_mm))


def layer_triangles(kind: str, board: str, side: str, height_mm: float) -> np.ndarray:
    """Triangles (n, 3, 2) of a "copper" or "silk" layer in the dataset's coordinates, simplified for the 3D view.
    Simplifying about 200,000 silkscreen points takes seconds, so the result is cached (and the warm-up makes it)."""
    key = (kind, board, side)
    with _triangle_lock:
        if key in _triangles:
            return _triangles[key]
    geometry = (copper if kind == "copper" else silkscreen)(board, side, height_mm)
    if geometry is None or geometry.is_empty:
        triangles = np.zeros((0, 3, 2))
    else:
        mesh = shapely.constrained_delaunay_triangles(shapely.simplify(geometry, TRIANGLE_TOLERANCE))
        triangles = shapely.get_coordinates(mesh).reshape(-1, 4, 2)[:, :3]
    with _triangle_lock:
        _triangles[key] = triangles
    return triangles


def warm_up(heights: dict[str, float]) -> threading.Thread:
    """Read every layer on a background thread so the Board tab is ready by the time it is opened."""
    def work() -> None:
        for board, height in heights.items():
            if not available(board):
                continue
            for side in ("top", "bottom"):
                layer_triangles("copper", board, side, height)
                layer_triangles("silk", board, side, height)
            drills(board, height)

    thread = threading.Thread(target=work, name="fabrication-warm-up", daemon=True)
    thread.start()
    return thread
