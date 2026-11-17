"""Assembly tab: ordered build steps with saved progress."""
from __future__ import annotations

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QSplitter, QTextBrowser, QVBoxLayout, QWidget,
)

from .dataset import BOARD_LABELS, AssemblyStep, Dataset

PHASE_LABELS = {
    "smd-passives": "Surface-mount: resistors and capacitors",
    "smd-ics": "Surface-mount: chips",
    "smd-mechanical": "Surface-mount: connectors",
    "tht": "Through-hole parts",
    "modules": "Pre-built modules",
    "mechanical": "Mechanical assembly",
    "flash-firmware": "Software setup",
}
SETTINGS_KEY = "assembly/completed"


def load_completed(settings: QSettings) -> set[str]:
    value = settings.value(SETTINGS_KEY, [])
    if isinstance(value, str):
        value = [value]
    return set(value or [])


class AssemblyTab(QWidget):
    progress_changed = Signal(str)
    show_on_board = Signal(str, list)  # board id and component refs of the selected step

    def __init__(self, dataset: Dataset, settings: QSettings, parent: QWidget | None = None):
        super().__init__(parent)
        self.steps: list[AssemblyStep] = dataset.assembly
        self.settings = settings
        self.completed = load_completed(settings)

        self.list = QListWidget()
        self.list.setMinimumWidth(260)
        self.list.setWordWrap(True)
        self.detail = QTextBrowser()
        self.detail.setMinimumWidth(260)
        self.toggle_button = QPushButton("Mark as Done")
        self.toggle_button.setToolTip("Record this step as finished. Progress is saved on this computer.")
        self.board_button = QPushButton("Show on Board")
        self.board_button.setToolTip("Open the Board tab with this step's parts highlighted.")
        self.reset_button = QPushButton("Reset Progress")
        self.reset_button.setToolTip("Mark every step as not done.")
        self.summary = QLabel()

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.addWidget(self.toggle_button)
        buttons.addWidget(self.board_button)
        buttons.addWidget(self.reset_button)
        buttons.addStretch(1)
        buttons.addWidget(self.summary)

        splitter = QSplitter()
        splitter.addWidget(self.list)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([400, 600])
        layout = QVBoxLayout(self)
        layout.addWidget(splitter, 1)
        layout.addLayout(buttons)

        if not self.steps:
            self.list.hide()
            self.detail.setPlainText("No assembly steps yet.")
            self.toggle_button.setEnabled(False)
            self.toggle_button.setToolTip("There are no steps to mark.")
            self.reset_button.setEnabled(False)
            self.board_button.setEnabled(False)
            self.board_button.setToolTip("There are no steps to show.")

        self.list.currentRowChanged.connect(self.show_step)
        self.toggle_button.clicked.connect(self.toggle_current)
        self.reset_button.clicked.connect(self.reset)
        self.board_button.clicked.connect(self.emit_show_on_board)
        self.rebuild_list()
        first = next((i for i, s in enumerate(self.steps) if s.id not in self.completed), 0)
        self.list.setCurrentRow(first)

    def state_text(self, step: AssemblyStep) -> str:
        if step.deferred:
            return "Deferred"
        return "Done" if step.id in self.completed else "Not done"

    def rebuild_list(self) -> None:
        row = self.list.currentRow()
        self.list.blockSignals(True)
        self.list.clear()
        for number, step in enumerate(self.steps, 1):
            item = QListWidgetItem(f"{number}. {step.title}  [{self.state_text(step)}]")
            if step.deferred:
                item.setToolTip("Deferred. This step is out of scope for the first batch.")
            else:
                item.setToolTip("Done. Select the step to see its details." if step.id in self.completed
                                else "Not done yet. Select the step to see its details.")
            self.list.addItem(item)
        self.list.blockSignals(False)
        self.list.setCurrentRow(row if row >= 0 else 0)
        self.update_summary()

    def update_summary(self) -> None:
        active = [s for s in self.steps if not s.deferred]
        remaining = sum(s.estimated_minutes or 0 for s in active if s.id not in self.completed)
        text = f"{len(self.completed & {s.id for s in active})} of {len(active)} done"
        self.summary.setText(f"{text}. About {remaining} min left.")
        self.progress_changed.emit(f"Assembly: {text}")

    def show_step(self, row: int) -> None:
        if row < 0 or row >= len(self.steps):
            return
        step = self.steps[row]
        self.toggle_button.setText("Mark as Not Done" if step.id in self.completed else "Mark as Done")
        has_parts = bool(step.component_refs) and not step.deferred
        self.board_button.setEnabled(has_parts)
        self.board_button.setToolTip(
            "Open the Board tab with this step's parts highlighted." if has_parts
            else "This step has no parts on the board to show.")
        self.toggle_button.setEnabled(not step.deferred)
        self.toggle_button.setToolTip("This step is deferred, so it cannot be marked." if step.deferred
                                      else "Record this step as finished. Progress is saved on this computer.")
        facts = [
            ("State", self.state_text(step)),
            ("Testing", "Untested. Nobody has built a unit with these instructions yet." if step.untested else None),
            ("Phase", PHASE_LABELS.get(step.phase, step.phase)),
            ("Board", BOARD_LABELS.get(step.board, step.board)),
            ("Time", f"about {step.estimated_minutes} min" if step.estimated_minutes else None),
            ("Parts", ", ".join(step.component_refs) or None), ("Tools", ", ".join(step.tools) or None),
        ]
        rows = "".join(f"<tr><td><b>{k}:</b>&nbsp;</td><td>{v}</td></tr>" for k, v in facts if v)
        notes = f"<p><b>Note:</b> {step.notes}</p>" if step.notes else ""
        self.detail.setHtml(f"<h3>{step.title}</h3><table>{rows}</table><p>{step.description}</p>{notes}")

    def emit_show_on_board(self) -> None:
        row = self.list.currentRow()
        if 0 <= row < len(self.steps) and self.steps[row].component_refs:
            step = self.steps[row]
            self.show_on_board.emit(step.board, list(step.component_refs))

    def save(self) -> None:
        self.settings.setValue(SETTINGS_KEY, sorted(self.completed))

    def toggle_current(self) -> None:
        row = self.list.currentRow()
        if row < 0:
            return
        if self.steps[row].deferred:
            return
        step_id = self.steps[row].id
        self.completed ^= {step_id}
        self.save()
        self.rebuild_list()
        if step_id in self.completed and row + 1 < len(self.steps):
            self.list.setCurrentRow(row + 1)
        else:
            self.show_step(self.list.currentRow())

    def reset(self) -> None:
        if not self.completed:
            return
        answer = QMessageBox.question(
            self, "Reset Progress", "Mark every step as not done?",
            QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel,
        )
        if answer == QMessageBox.Discard:
            self.completed.clear()
            self.save()
            self.rebuild_list()
            self.show_step(self.list.currentRow())
