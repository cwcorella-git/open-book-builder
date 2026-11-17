"""Temporary tab body until the Board and Case viewers land."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class EmptyTab(QWidget):
    def __init__(self, message: str, parent: QWidget | None = None):
        super().__init__(parent)
        label = QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(label)
