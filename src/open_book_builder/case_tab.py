"""Case tab: rotatable flat-shaded view of the case STL models."""
from __future__ import annotations

import shutil
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSplitter,
    QTextBrowser, QVBoxLayout, QWidget,
)

from .dataset import find_data_dir
from .meshview import FRAGMENTS_PER_CHUNK, MeshWidget, rasterize  # noqa: F401  (re-exported for tests)


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
