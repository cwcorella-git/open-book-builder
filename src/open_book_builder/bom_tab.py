"""BOM tab: filterable parts table, detail pane, cost footer, Digi-Key export."""
from __future__ import annotations

from urllib.parse import quote

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QSpinBox, QSplitter, QStackedLayout, QTableWidget,
    QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget,
)

from .dataset import BOARD_LABELS, BomLine, Dataset
from .digikey_csv import build_digikey_csv

COLUMNS = ["Board", "Refs", "Description", "Part", "Qty", "Total", "Cost", "Line"]
NUMERIC = {4, 5, 6, 7}


def usd(value: float | None) -> str:
    return "n/a" if value is None else f"${value:,.2f}"


def plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


class BomTab(QWidget):
    cost_changed = Signal(str)

    def __init__(self, dataset: Dataset, parent: QWidget | None = None):
        super().__init__(parent)
        self.dataset = dataset
        self.rows: list[BomLine] = []

        self.board_box = QComboBox()
        self.board_box.addItem("All boards", "all")
        for key, label in BOARD_LABELS.items():
            self.board_box.addItem(label, key)
        self.board_box.setToolTip("Show the parts for one board, or for both.")

        self.qty_box = QSpinBox()
        self.qty_box.setRange(1, 999)
        self.qty_box.setToolTip("Number of readers to buy parts for. Quantities and totals scale with it.")

        self.optional_box = QCheckBox("Include optional parts")
        self.optional_box.setChecked(True)
        self.optional_box.setToolTip("Optional parts are the expansion connectors and their resistors.")

        self.export_button = QPushButton("Export Digi-Key CSV...")
        self.export_button.setToolTip(
            "Save a CSV for the Digi-Key BOM Manager. Parts without a Digi-Key number are left out."
        )

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        for text, widget in (("Board:", self.board_box), ("Readers:", self.qty_box)):
            controls.addWidget(QLabel(text))
            controls.addWidget(widget)
        controls.addWidget(self.optional_box)
        controls.addStretch(1)
        controls.addWidget(self.export_button)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumWidth(420)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideRight)
        self.table.horizontalHeader().setMinimumSectionSize(48)

        self.detail = QTextBrowser()
        self.detail.setOpenExternalLinks(True)
        self.detail.setMinimumWidth(220)

        self.empty = QLabel("No parts match. Choose All boards, or turn on Include optional parts.")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setWordWrap(True)

        splitter = QSplitter()
        splitter.addWidget(self.table)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([760, 240])

        self.content = QWidget()
        stack = QStackedLayout(self.content)
        stack.addWidget(splitter)
        stack.addWidget(self.empty)
        self.stack = stack

        self.footer = QLabel()
        self.note = QLabel("The C2 driver module has no price here. Ask the board house for a quote.")
        self.note.setToolTip("The subtotal covers the C1 board parts and the display only.")
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addWidget(self.footer)
        footer.addStretch(1)
        footer.addWidget(self.note)

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.content, 1)
        layout.addLayout(footer)

        self.board_box.currentIndexChanged.connect(self.refresh)
        self.qty_box.valueChanged.connect(self.refresh)
        self.optional_box.toggled.connect(self.refresh)
        self.table.itemSelectionChanged.connect(self.show_detail)
        self.export_button.clicked.connect(self.export_csv)
        self.refresh()

    # -- data ---------------------------------------------------------------
    def visible_lines(self) -> list[BomLine]:
        board = self.board_box.currentData()
        return [
            line for line in self.dataset.bom
            if (board == "all" or line.board == board)
            and (self.optional_box.isChecked() or not line.optional)
        ]

    def refresh(self) -> None:
        multiplier = self.qty_box.value()
        self.rows = self.visible_lines()
        self.table.setRowCount(len(self.rows))
        for r, line in enumerate(self.rows):
            total_qty = line.qty * multiplier
            line_total = None if line.unit_cost_usd is None else line.unit_cost_usd * total_qty
            cells = [
                BOARD_LABELS[line.board], ", ".join(line.refs), line.description + (" (optional)" if line.optional and "OPTIONAL" not in line.description.upper() else ""),
                line.mpn, str(line.qty), str(total_qty), usd(line.unit_cost_usd), usd(line_total),
            ]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                if c in NUMERIC:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, c, item)
        header = self.table.horizontalHeader()
        for c in range(len(COLUMNS)):
            header.setSectionResizeMode(c, QHeaderView.Stretch if c == 2 else QHeaderView.Interactive if c in (1, 3) else QHeaderView.ResizeToContents)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(3, 150)
        self.stack.setCurrentIndex(0 if self.rows else 1)
        self.update_footer()
        if self.rows:
            self.table.selectRow(0)
        else:
            self.detail.clear()

    def update_footer(self) -> None:
        per_unit = self.dataset.per_unit_usd
        multiplier = self.qty_box.value()
        text = f"Per reader: {usd(per_unit)}"
        if multiplier > 1:
            text += f".  For {plural(multiplier, 'reader')}: {usd(per_unit * multiplier)}"
        self.footer.setText(text + ".")
        self.cost_changed.emit(f"Cost: {usd(per_unit)} per reader")

    def show_detail(self) -> None:
        r = self.table.currentRow()
        if r < 0 or r >= len(self.rows):
            self.detail.clear()
            return
        line = self.rows[r]
        links = []
        if line.digikey_pn:
            links.append(f'<a href="https://www.digikey.com/en/products/result?keywords={quote(line.digikey_pn)}">Digi-Key {line.digikey_pn}</a>')
        if line.mouser_pn:
            links.append(f'<a href="https://www.mouser.com/ProductDetail/{quote(line.mouser_pn)}">Mouser {line.mouser_pn}</a>')
        if line.lcsc_pn:
            links.append(f'<a href="https://www.lcsc.com/product-detail/{quote(line.lcsc_pn)}.html">LCSC {line.lcsc_pn}</a>')
        if line.datasheet_url:
            links.append(f'<a href="{line.datasheet_url}">Datasheet</a>')
        fields = [
            ("Board", BOARD_LABELS[line.board]), ("Part", line.mpn),
            ("Manufacturer", line.manufacturer), ("Footprint", line.footprint),
            ("Per reader", str(line.qty)), ("Unit cost", usd(line.unit_cost_usd)),
        ]
        rows = "".join(f"<tr><td><b>{k}:</b>&nbsp;</td><td>{v}</td></tr>" for k, v in fields if v)
        self.detail.setHtml(
            f"<h3>{', '.join(line.refs) or 'No reference'}</h3><p>{line.function or line.description}</p>"
            f"<table>{rows}</table><p>{'<br>'.join(links) or 'No supplier links for this part.'}</p>"
        )

    # -- export -------------------------------------------------------------
    def export_csv(self) -> None:
        result = build_digikey_csv(self.dataset.bom, self.qty_box.value(), self.optional_box.isChecked())
        path, _ = QFileDialog.getSaveFileName(self, "Export Digi-Key CSV", "open-book-digikey-bom.csv", "CSV files (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(result.csv)
        except OSError as error:
            QMessageBox.critical(self, "Export Digi-Key CSV", f"Could not save:\n\n{error}")
            return
        message = f"Saved {plural(result.included_count, 'part line')}."
        if result.skipped:
            message += f"\n\n{plural(len(result.skipped), 'line')} left out (no Digi-Key number, or optional and turned off)."
        QMessageBox.information(self, "Export Digi-Key CSV", message)
