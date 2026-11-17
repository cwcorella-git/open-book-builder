"""Rotatable flat-shaded mesh view drawn with a depth buffer in numpy: no OpenGL, so it works everywhere,
including over Selkies, and can be tested without a display.

Used by the Case tab and the 3D board view."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPalette
from PySide6.QtWidgets import QWidget

FRAGMENTS_PER_CHUNK = 1_000_000  # bounds memory: each chunk handles about this many candidate pixels


def rasterize(sx: np.ndarray, sy: np.ndarray, depth: np.ndarray, shade: np.ndarray, w: int, h: int) -> np.ndarray:
    """Like rasterize_ids, but returns an (h, w) float image of the nearest triangle's shade, 0 where empty."""
    ids = rasterize_ids(sx, sy, depth, w, h)
    return np.where(ids >= 0, np.asarray(shade, dtype=np.float32)[np.maximum(ids, 0)], 0).astype(np.float32)


def rasterize_ids(sx: np.ndarray, sy: np.ndarray, depth: np.ndarray, w: int, h: int) -> np.ndarray:
    """Draw triangles with a per-pixel depth buffer, with no Python loop over triangles.

    sx, sy, depth are (n, 3). Depth is the distance away from the viewer, so smaller wins.
    Returns an (h, w) int image: the index of the nearest triangle at each pixel, -1 where empty.

    Every pixel inside each triangle's bounding box becomes a candidate, the inside test and depth are worked
    out for all candidates at once, then np.minimum.at keeps the nearest depth per pixel.
    A loop over triangles took about 180 ms for the Sprint 5 case, all on one CPU core."""
    sx, sy, depth = sx.astype(np.float32), sy.astype(np.float32), depth.astype(np.float32)
    zbuf = np.full(w * h, np.inf, dtype=np.float32)
    img = np.full(w * h, -1, dtype=np.int32)
    if not len(sx):
        return img.reshape(h, w)
    x0 = np.floor(sx.min(1)).clip(0, w - 1).astype(np.int32)
    x1 = np.ceil(sx.max(1)).clip(0, w - 1).astype(np.int32)
    y0 = np.floor(sy.min(1)).clip(0, h - 1).astype(np.int32)
    y1 = np.ceil(sy.max(1)).clip(0, h - 1).astype(np.int32)
    ax, ay, bx, by, cx, cy = sx[:, 0], sy[:, 0], sx[:, 1], sy[:, 1], sx[:, 2], sy[:, 2]
    den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    on_screen = (sx.max(1) >= 0) & (sx.min(1) <= w) & (sy.max(1) >= 0) & (sy.min(1) <= h) & (np.abs(den) > 1e-9)
    ids = np.flatnonzero(on_screen)
    if not len(ids):
        return img.reshape(h, w)
    box_w = (x1[ids] - x0[ids] + 1).astype(np.int64)
    counts = box_w * (y1[ids] - y0[ids] + 1)
    edges = np.searchsorted(np.cumsum(counts), np.arange(FRAGMENTS_PER_CHUNK, int(counts.sum()) + FRAGMENTS_PER_CHUNK,
                                                          FRAGMENTS_PER_CHUNK))
    bounds = np.unique(np.concatenate(([0], edges + 1, [len(ids)])).clip(0, len(ids)))
    for lo, hi in zip(bounds[:-1], bounds[1:]):
        g_ids, n = ids[lo:hi], counts[lo:hi]
        total = int(n.sum())
        owner = np.repeat(np.arange(len(g_ids)), n)
        local = np.arange(total) - np.repeat(np.cumsum(n) - n, n)
        px = x0[g_ids][owner] + local % box_w[lo:hi][owner]
        py = y0[g_ids][owner] + local // box_w[lo:hi][owner]
        g = g_ids[owner]
        fx, fy = px.astype(np.float32) + 0.5, py.astype(np.float32) + 0.5
        l1 = ((by[g] - cy[g]) * (fx - cx[g]) + (cx[g] - bx[g]) * (fy - cy[g])) / den[g]
        l2 = ((cy[g] - ay[g]) * (fx - cx[g]) + (ax[g] - cx[g]) * (fy - cy[g])) / den[g]
        l3 = 1 - l1 - l2
        inside = (l1 >= -1e-4) & (l2 >= -1e-4) & (l3 >= -1e-4)
        g, l1, l2, l3 = g[inside], l1[inside], l2[inside], l3[inside]
        idx = py[inside] * w + px[inside]
        z = l1 * depth[g, 0] + l2 * depth[g, 1] + l3 * depth[g, 2]
        np.minimum.at(zbuf, idx, z)
        nearest = z <= zbuf[idx]
        img[idx[nearest]] = g[nearest]
    return img.reshape(h, w)


class MeshWidget(QWidget):
    """Rotatable flat-shaded mesh view. Drawn with a depth buffer, so overlapping and thin triangles stay in the
    right order. Low resolution while you drag, sharp when you stop.

    Optional per-triangle base colors and group numbers let a mesh hold several parts. A click on a part emits
    `picked` with its group number (-1 for empty space or an unnamed part); the picked group can be highlighted."""

    picked = Signal(int)

    def __init__(self, parent: QWidget | None = None, home: tuple[float, float] = (35.0, 25.0)):
        super().__init__(parent)
        self.tris = np.zeros((0, 3, 3))
        self.colors: np.ndarray | None = None  # (n, 3) uint8 base color per triangle
        self.groups: np.ndarray | None = None  # (n,) int group per triangle, -1 for none
        self.highlight_group: int | None = None
        self.home = home
        self.yaw, self.pitch = home
        self.zoom = 1.0
        self._last: QPointF | None = None
        self._pressed_at: QPointF | None = None
        self._image: QImage | None = None
        self._ids: np.ndarray | None = None
        self._ids_scale = 1.0
        self._dirty = True
        self._moving = False
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(160)
        self._settle.timeout.connect(self._sharpen)
        self.setMinimumSize(320, 240)
        self.setCursor(Qt.OpenHandCursor)

    def set_mesh(self, tris: np.ndarray, colors: np.ndarray | None = None, groups: np.ndarray | None = None) -> None:
        self.tris, self.colors, self.groups = tris, colors, groups
        self.highlight_group = None
        self.reset_view()

    def set_highlight(self, group: int | None) -> None:
        self.highlight_group = group
        self._invalidate(moving=False)

    def reset_view(self) -> None:
        self.yaw, self.pitch = self.home
        self.zoom = 1.0
        self._invalidate(moving=False)

    def _invalidate(self, moving: bool) -> None:
        self._dirty = True
        self._moving = moving
        if moving:
            self._settle.start()
        self.update()

    def _sharpen(self) -> None:
        self._moving = False
        self._dirty = True
        self.update()

    def mousePressEvent(self, event) -> None:
        self._last = self._pressed_at = event.position()

    def mouseMoveEvent(self, event) -> None:
        if self._last is not None:
            d = event.position() - self._last
            self.yaw += d.x() * 0.5
            self.pitch = max(-89.0, min(89.0, self.pitch + d.y() * 0.5))
            self._last = event.position()
            self._invalidate(moving=True)

    def mouseReleaseEvent(self, event) -> None:
        click = (self._pressed_at is not None
                 and (event.position() - self._pressed_at).manhattanLength() < 4)
        self._last = None
        if click:
            self.picked.emit(self.group_at(event.position()))
        self._sharpen()

    def group_at(self, position: QPointF) -> int:
        """Group number of the part under a widget position, from the last drawn frame; -1 if none."""
        if self._ids is None or self.groups is None:
            return -1
        x, y = int(position.x() * self._ids_scale), int(position.y() * self._ids_scale)
        if not (0 <= y < self._ids.shape[0] and 0 <= x < self._ids.shape[1]):
            return -1
        tri = self._ids[y, x]
        return int(self.groups[tri]) if tri >= 0 else -1

    def wheelEvent(self, event) -> None:
        self.zoom = max(0.2, min(8.0, self.zoom * (1.12 if event.angleDelta().y() > 0 else 1 / 1.12)))
        self._invalidate(moving=True)

    def resizeEvent(self, event) -> None:
        self._dirty = True
        super().resizeEvent(event)

    def _render(self, scale: float) -> QImage:
        w, h = max(1, int(self.width() * scale)), max(1, int(self.height() * scale))
        pal = self.palette()
        base, back = pal.color(QPalette.Button), pal.color(QPalette.Base)
        canvas = np.empty((h, w, 3), dtype=np.uint8)
        canvas[:] = (back.red(), back.green(), back.blue())
        self._ids, self._ids_scale = None, scale
        if len(self.tris):
            pts = self.tris.reshape(-1, 3)
            pts = pts - (pts.min(0) + pts.max(0)) / 2
            radius = np.linalg.norm(pts, axis=1).max() or 1.0
            yaw, pitch = np.radians(self.yaw), np.radians(self.pitch)
            rz = np.array([[np.cos(yaw), -np.sin(yaw), 0], [np.sin(yaw), np.cos(yaw), 0], [0, 0, 1]])
            rx = np.array([[1, 0, 0], [0, np.cos(pitch), -np.sin(pitch)], [0, np.sin(pitch), np.cos(pitch)]])
            tri = (pts @ rz.T @ rx.T).reshape(-1, 3, 3)
            k = self.zoom * min(w, h) * 0.45 / radius
            sx = w / 2 + tri[:, :, 0] * k
            sy = h / 2 - tri[:, :, 2] * k
            normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
            length = np.linalg.norm(normals, axis=1)
            length[length == 0] = 1.0
            normals /= length[:, None]
            # The light's depth part follows the side the camera is on, so a flat face is as bright from below as from above.
            light = np.array([-0.4, 0.6 if self.pitch < 0 else -0.6, 0.7])
            light /= np.linalg.norm(light)
            shade = (0.25 + 0.75 * np.abs(normals @ light)).astype(np.float32)
            ids = rasterize_ids(sx, sy, tri[:, :, 1].astype(np.float32), w, h)
            self._ids = ids
            filled = ids >= 0
            if self.colors is not None:
                colours = self.colors.astype(np.float32).copy()
            else:
                colours = np.tile(np.array([base.red(), base.green(), base.blue()], dtype=np.float32), (len(self.tris), 1))
            if self.highlight_group is not None and self.groups is not None:
                hi = pal.color(QPalette.Highlight)
                colours[self.groups == self.highlight_group] = (hi.red(), hi.green(), hi.blue())
            canvas[filled] = (shade[ids[filled]][:, None] * colours[ids[filled]]).astype(np.uint8)
        image = QImage(canvas.data, w, h, 3 * w, QImage.Format_RGB888)
        return image.copy()

    def paintEvent(self, event) -> None:
        if self._dirty or self._image is None:
            self._image = self._render(0.45 if self._moving else 1.0)
            self._dirty = False
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawImage(self.rect(), self._image)
