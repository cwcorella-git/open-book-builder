"""Entry point: `open-book-builder`."""
from __future__ import annotations

import sys

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from .dataset import load_dataset
from .window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Open Book Builder")
    app.setOrganizationName("open-book-builder")
    window = MainWindow(load_dataset(), QSettings())
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
