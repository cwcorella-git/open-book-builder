"""Main window, laid out per the voicebake UI style guide."""
from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QLabel, QMainWindow, QMessageBox, QTabWidget

from .assembly_tab import AssemblyTab
from .board_tab import BoardTab
from .bom_tab import BomTab
from .case_tab import CaseTab
from .checklist_tab import ChecklistTab
from .config_store import ConfigStore
from .dataset import Dataset


class MainWindow(QMainWindow):
    def __init__(self, dataset: Dataset, settings: QSettings, store: ConfigStore | None = None):
        super().__init__()
        self.settings = settings
        self.store = store or ConfigStore()
        self.setWindowTitle("Open Book Builder[*]")
        self.resize(1040, 700)
        self.setMinimumSize(760, 520)
        geometry = settings.value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)

        self.bom = BomTab(dataset, self.store)
        self.checklist = ChecklistTab(dataset, self.store)
        self.assembly = AssemblyTab(dataset, settings)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self.bom, "BOM")
        self.tabs.addTab(self.checklist, "Checklist")
        self.tabs.addTab(self.assembly, "Assembly")
        self.board = BoardTab(dataset)
        self.tabs.addTab(self.board, "Board")
        self.tabs.addTab(CaseTab(), "Case")
        self.setCentralWidget(self.tabs)

        self.cost_label = QLabel()
        self.cost_label.setToolTip("Parts cost for one reader: the C1 board parts and the display.")
        self.progress_label = QLabel()
        self.progress_label.setToolTip("Assembly steps you have marked as done.")
        for label in (self.cost_label, self.progress_label):
            label.setContentsMargins(8, 0, 8, 0)
            self.statusBar().addPermanentWidget(label)
        self.board.selection_message.connect(lambda m: self.statusBar().showMessage(m, 5000) if m else self.statusBar().clearMessage())
        self.assembly.show_on_board.connect(self.show_step_on_board)
        self.bom.cost_changed.connect(self.cost_label.setText)
        self.assembly.progress_changed.connect(self.progress_label.setText)
        self.bom.update_footer()
        self.assembly.update_summary()

        self.store.dirty_changed.connect(self.setWindowModified)
        self.build_menus()

    def build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        export = file_menu.addAction("&Export Digi-Key CSV...", self.bom.export_csv)
        export.setShortcut("Ctrl+E")
        self.save_action = QAction("&Save", self)
        self.save_action.setShortcut(QKeySequence.Save)
        self.save_action.setToolTip("Save spare parts and the batch plan to data/configs.json.")
        self.save_action.triggered.connect(self.save)
        file_menu.addAction(self.save_action)
        file_menu.addSeparator()
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        view_menu = self.menuBar().addMenu("&View")
        for index, name in enumerate(("&BOM", "C&hecklist", "&Assembly", "Boar&d", "&Case")):
            action = view_menu.addAction(name, lambda i=index: self.tabs.setCurrentIndex(i))
            action.setShortcut(f"Ctrl+{index + 1}")

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction("&About Open Book Builder", self.about)

    def about(self) -> None:
        QMessageBox.information(
            self, "About Open Book Builder",
            "Parts list, assembly guide, and board and case views for the Open Book e-reader.\n\n"
            "Hardware designs are by Joey Castillo (The Open Book, Oddly Specific Objects).",
        )

    def show_step_on_board(self, board: str, refs: list) -> None:
        message = self.board.highlight(board, refs)
        self.tabs.setCurrentWidget(self.board)
        self.statusBar().showMessage(message, 8000)

    def save(self) -> bool:
        try:
            self.store.save()
        except OSError as error:
            QMessageBox.critical(self, "Save", f"Could not save:\n\n{error}")
            return False
        self.statusBar().showMessage("Saved.", 5000)
        return True

    def closeEvent(self, event) -> None:
        if self.store.dirty:
            answer = QMessageBox.question(
                self, "Open Book Builder", "Save your changes to spare parts and quantities?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
            if answer == QMessageBox.Cancel or (answer == QMessageBox.Save and not self.save()):
                event.ignore()
                return
        self.settings.setValue("window/geometry", self.saveGeometry())
        super().closeEvent(event)
