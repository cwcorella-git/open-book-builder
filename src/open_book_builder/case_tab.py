"""Case tab: rotatable flat-shaded view of the case STL models."""
from __future__ import annotations

import shutil
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QImage, QPainter, QPalette
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSplitter,
    QTextBrowser, QVBoxLayout, QWidget,
)

from .dataset import find_data_dir


def load_stl(path: Path) -> np.ndarray:
    """Binary STL to an (n, 3, 3) float array of triangles."""
    raw = path.read_bytes()
    count = struct.unpack_from("<I", raw, 80)[0]
    if 84 + 50 * count != len(raw):
        raise ValueError(f"{path.name} is not a binary STL file.")
    record = np.dtype([("normal", "<3f4"), ("tri", "<9f4"), ("attr", "<u2")])
    return np.frombuffer(raw, dtype=record, count=count, offset=84)["tri"].reshape(-1, 3, 3).astype(float)


@dataclass
class Design:
    label: str
    blurb: str
    parts: list[tuple[str, tuple[float, float, float]]]  # (file name, exploded offset in mm)
    files: list[str]


DESIGNS = [
    Design(
        "Sprint 5 (two parts)",
        "Two-part case from Joey Castillo's Hackaday Prize 2023 submission, the fifth version of his parametric "
        "case. It was made for the B1 board, and its 88.6 x 118.6 mm size matches the C1 board outline. Fit "
        "around the C1 parts is untested. The parts are drawn pulled apart so you can see both. Assembly uses four M2.5 x 6 mm screws. The OpenSCAD file has an "
        "<code>abridged</code> setting for the AAA battery holder height.",
        [("sprint-5-frontplate.stl", (-25, 0, 0)), ("sprint-5-backplate.stl", (25, 0, 0))],
        ["sprint-5-frontplate.stl", "sprint-5-backplate.stl", "sprint-5.scad"],
    ),
    Design(
        "Minimal case (back cover only)",
        "Joey Castillo's single back cover from the upstream repository. It has no front bezel: the board itself "
        "is the front face, with the display and buttons showing. It uses M2.5 screws, needs no supports and is "
        "sized for a 1.0 mm board.",
        [("open-book-abridged-minimal-case.stl", (0, 0, 0))],
        ["open-book-abridged-minimal-case.stl"],
    ),
]


FRAGMENTS_PER_CHUNK = 1_000_000  # bounds memory: each chunk handles about this many candidate pixels


def rasterize(sx: np.ndarray, sy: np.ndarray, depth: np.ndarray, shade: np.ndarray, w: int, h: int) -> np.ndarray:
    """Draw triangles with a per-pixel depth buffer, with no Python loop over triangles.

    sx, sy, depth are (n, 3); shade is (n,). Depth is the distance away from the viewer, so smaller wins.
    Returns an (h, w) float image: the shade of the nearest triangle at each pixel, 0 where empty.

    Every pixel inside each triangle's bounding box becomes a candidate, the inside test and depth are worked
    out for all candidates at once, then np.minimum.at keeps the nearest depth per pixel.
    A loop over triangles took about 180 ms for the Sprint 5 case, all on one CPU core."""
    sx, sy, depth = sx.astype(np.float32), sy.astype(np.float32), depth.astype(np.float32)
    zbuf = np.full(w * h, np.inf, dtype=np.float32)
    img = np.zeros(w * h, dtype=np.float32)
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
        img[idx[nearest]] = shade[g[nearest]]
    return img.reshape(h, w)


class MeshWidget(QWidget):
    """Rotatable flat-shaded mesh view. Drawn with a depth buffer, so overlapping and thin
    triangles stay in the right order. Low resolution while you drag, sharp when you stop."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.tris = np.zeros((0, 3, 3))
        self.yaw, self.pitch, self.zoom = 35.0, 25.0, 1.0
        self._last: QPointF | None = None
        self._image: QImage | None = None
        self._dirty = True
        self._moving = False
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(160)
        self._settle.timeout.connect(self._sharpen)
        self.setMinimumSize(320, 240)
        self.setCursor(Qt.OpenHandCursor)

    def set_mesh(self, tris: np.ndarray) -> None:
        self.tris = tris
        self.reset_view()

    def reset_view(self) -> None:
        self.yaw, self.pitch, self.zoom = 35.0, 25.0, 1.0
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
        self._last = event.position()

    def mouseMoveEvent(self, event) -> None:
        if self._last is not None:
            d = event.position() - self._last
            self.yaw += d.x() * 0.5
            self.pitch = max(-89.0, min(89.0, self.pitch + d.y() * 0.5))
            self._last = event.position()
            self._invalidate(moving=True)

    def mouseReleaseEvent(self, event) -> None:
        self._last = None
        self._sharpen()

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
            light = np.array([-0.4, -0.6, 0.7])
            light /= np.linalg.norm(light)
            shade = (0.25 + 0.75 * np.abs(normals @ light)).astype(np.float32)
            img = rasterize(sx, sy, tri[:, :, 1].astype(np.float32), shade, w, h)
            filled = img > 0
            colour = np.array([base.red(), base.green(), base.blue()], dtype=np.float32)
            canvas[filled] = (img[filled][:, None] * colour).astype(np.uint8)
        image = QImage(canvas.data, w, h, 3 * w, QImage.Format_RGB888)
        return image.copy()

    def paintEvent(self, event) -> None:
        if self._dirty or self._image is None:
            self._image = self._render(0.45 if self._moving else 1.0)
            self._dirty = False
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawImage(self.rect(), self._image)


class CaseTab(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.case_dir = find_data_dir() / "case"
        self.design_box = QComboBox()
        for d in DESIGNS:
            self.design_box.addItem(d.label)
        self.design_box.setToolTip("Choose a case design to look at.")
        self.reset_button = QPushButton("Reset View")
        self.reset_button.setToolTip("Return to the starting angle and zoom.")
        self.save_button = QPushButton("Save Files...")
        self.save_button.setToolTip("Copy this design's STL and OpenSCAD files to a folder you choose.")

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.addWidget(QLabel("Design:"))
        controls.addWidget(self.design_box)
        controls.addStretch(1)
        controls.addWidget(self.reset_button)
        controls.addWidget(self.save_button)

        self.mesh = MeshWidget()
        self.mesh.setToolTip("Drag to turn the model. Scroll to zoom.")
        self.detail = QTextBrowser()
        self.detail.setOpenExternalLinks(True)
        self.detail.setMinimumWidth(220)
        splitter = QSplitter()
        splitter.addWidget(self.mesh)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 3)
        splitter.setSizes([700, 300])

        self.empty = QLabel("The case files are missing. Reinstall the app, or restore data/case.")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.hide()

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(splitter, 1)
        layout.addWidget(self.empty)

        self.design_box.currentIndexChanged.connect(self.show_design)
        self.reset_button.clicked.connect(self.mesh.reset_view)
        self.save_button.clicked.connect(self.save_files)
        self.show_design()

    def show_design(self) -> None:
        design = DESIGNS[self.design_box.currentIndex()]
        try:
            meshes = []
            for name, offset in design.parts:
                tris = load_stl(self.case_dir / name)
                meshes.append((tris, tris + np.array(offset)))
        except (OSError, ValueError) as error:
            self.mesh.set_mesh(np.zeros((0, 3, 3)))
            self.detail.setHtml(f"<p>Could not load the model.</p><p>{error}</p>")
            self.save_button.setEnabled(False)
            self.save_button.setToolTip("There are no files to save.")
            return
        self.save_button.setEnabled(True)
        self.mesh.set_mesh(np.concatenate([m[1] for m in meshes]))
        sizes = "".join(
            f"<li>{name}: {np.ptp(t.reshape(-1, 3), axis=0).round(1).tolist()} mm, {len(t)} triangles</li>"
            for (name, _), (t, _) in zip(design.parts, meshes)
        )
        self.detail.setHtml(f"<h3>{design.label}</h3><p>{design.blurb}</p><p><b>Parts (size x, y, z):</b></p><ul>{sizes}</ul>")

    def save_files(self) -> None:
        design = DESIGNS[self.design_box.currentIndex()]
        folder = QFileDialog.getExistingDirectory(self, "Save Files")
        if not folder:
            return
        try:
            for name in design.files:
                shutil.copy2(self.case_dir / name, Path(folder) / name)
        except OSError as error:
            QMessageBox.critical(self, "Save Files", f"Could not save:\n\n{error}")
            return
        QMessageBox.information(self, "Save Files", f"Saved {len(design.files)} files to:\n\n{folder}")
