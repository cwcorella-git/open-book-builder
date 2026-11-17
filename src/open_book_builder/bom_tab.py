"""BOM tab: filterable parts table with spares, detail pane, cost footer, Digi-Key export."""
from __future__ import annotations

from urllib.parse import quote

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QSpinBox, QSplitter, QStackedLayout, QTableWidget,
    QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget,
)

from .config_store import ConfigStore
from .dataset import BOARD_LABELS, BomLine, Dataset
from .digikey_csv import build_digikey_csv

COLUMNS = ["Board", "Refs", "Description", "Part", "Qty", "Spare", "Order", "Cost", "Basis"]
NUMERIC = {4, 5, 6, 7}
SPARE_COLUMN = 5
BASIS_WORDS = {"listed": "Listed", "estimate": "Estimate", "quote": "Quote", None: "None"}
BASIS_TIPS = {
    "listed": "A dated supplier listing. See the detail pane for the date and stock.",
    "estimate": "An older price with no date. Replace it with a dated listing or a quote.",
    "quote": "A quote from the supplier.",
    None: "No price is recorded for this part.",
}


def usd(value: float | None) -> str:
    return "n/a" if value is None else f"${value:,.2f}"


def plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


class BomTab(QWidget):
    cost_changed = Signal(str)

    def __init__(self, dataset: Dataset, store: ConfigStore, parent: QWidget | None = None):
        super().__init__(parent)
        self.dataset = dataset
        self.store = store
        self.rows: list[BomLine] = []
        self._filling = False

        self.board_box = QComboBox()
        self.board_box.addItem("All boards", "all")
        for key, label in BOARD_LABELS.items():
            self.board_box.addItem(label, key)
        self.board_box.setToolTip("Show the parts for one board, or for both.")

        self.qty_box = QSpinBox()
        self.qty_box.setRange(1, 999)
        self.qty_box.setToolTip("Number of readers to buy parts for. Order quantities scale with it.")

        self.optional_box = QCheckBox("Include optional parts")
        self.optional_box.setChecked(True)
        self.optional_box.setToolTip("Optional parts are the expansion connectors and their resistors.")

        self.internals_box = QCheckBox("Show module internals")
        self.internals_box.setToolTip(
            "The C2 driver is bought as a finished module. Its internal parts are listed for reference "
            "and are not ordered or exported."
        )

        self.export_button = QPushButton("Export Digi-Key CSV...")
        self.export_button.setToolTip(
            "Save a CSV for the Digi-Key BOM Manager. Parts without a Digi-Key number and parts inside the "
            "C2 module are left out."
        )

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        for text, widget in (("Board:", self.board_box), ("Readers:", self.qty_box)):
            controls.addWidget(QLabel(text))
            controls.addWidget(widget)
        controls.addWidget(self.optional_box)
        controls.addWidget(self.internals_box)
        controls.addStretch(1)
        controls.addWidget(self.export_button)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumWidth(420)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideRight)
        self.table.horizontalHeader().setMinimumSectionSize(48)
        for column, tip in {
            "Spare": "Spare parts for the whole batch. Double-click to edit. Saved with File > Save.",
            "Order": "Quantity to buy: the parts for all readers plus the spares.",
            "Basis": "Where the price comes from: Listed, Estimate, Quote or None.",
        }.items():
            self.table.horizontalHeaderItem(COLUMNS.index(column)).setToolTip(tip)

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
        self.note = QLabel("Prices cover the C1 board parts and the display. Get a quote for the C2 driver module.")
        self.note.setToolTip("The subtotal is the C1 board parts and the display. The C2 driver module is quoted by the board house.")
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addWidget(self.footer)
        footer.addStretch(1)
        footer.addWidget(self.note)

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.content, 1)
        layout.addLayout(footer)

        for signal in (self.board_box.currentIndexChanged, self.qty_box.valueChanged,
                       self.optional_box.toggled, self.internals_box.toggled):
            signal.connect(self.refresh)
        self.table.itemSelectionChanged.connect(self.show_detail)
        self.table.itemChanged.connect(self.on_item_changed)
        self.export_button.clicked.connect(self.export_csv)
        store.changed.connect(self.refresh)
        self.refresh()

    # -- data ---------------------------------------------------------------
    def visible_lines(self) -> list[BomLine]:
        board = self.board_box.currentData()
        show_internals = self.internals_box.isChecked()
        return [
            line for line in self.dataset.bom
            if (board == "all" or line.board == board)
            and (self.optional_box.isChecked() or not line.optional)
            and (show_internals or not line.route_detail)
        ]

    def refresh(self) -> None:
        multiplier = self.qty_box.value()
        selected = self.rows[self.table.currentRow()].key if 0 <= self.table.currentRow() < len(self.rows) else None
        self.rows = self.visible_lines()
        self._filling = True
        self.table.setRowCount(len(self.rows))
        for r, line in enumerate(self.rows):
            if line.route_detail:
                spare, order = "", ""
            else:
                spare_n = self.store.spare(None, line.mpn)
                spare, order = str(spare_n), str(line.qty * multiplier + spare_n)
            desc = line.description + (" (optional)" if line.optional and "OPTIONAL" not in line.description.upper() else "")
            if line.route_detail:
                desc = "Inside C2 module: " + desc
            cells = [
                BOARD_LABELS[line.board], ", ".join(line.refs), desc, line.mpn, str(line.qty), spare, order,
                usd(line.unit_cost_usd), BASIS_WORDS[line.price_status],
            ]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                if c in NUMERIC:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                flags = item.flags() & ~Qt.ItemIsEditable
                if c == SPARE_COLUMN and not line.route_detail:
                    flags |= Qt.ItemIsEditable
                    item.setToolTip("Spare parts for the whole batch. Double-click to edit.")
                item.setFlags(flags)
                if c == COLUMNS.index("Basis"):
                    item.setToolTip(BASIS_TIPS[line.price_status])
                if line.route_detail and c == SPARE_COLUMN:
                    item.setToolTip("Bought inside the C2 module, so no spares are ordered separately.")
                self.table.setItem(r, c, item)
        self._filling = False
        header = self.table.horizontalHeader()
        for c in range(len(COLUMNS)):
            header.setSectionResizeMode(
                c, QHeaderView.Stretch if c == 2 else QHeaderView.Interactive if c in (1, 3) else QHeaderView.ResizeToContents)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(3, 150)
        self.stack.setCurrentIndex(0 if self.rows else 1)
        self.update_footer()
        if self.rows:
            keys = [line.key for line in self.rows]
            self.table.selectRow(keys.index(selected) if selected in keys else 0)
        else:
            self.detail.clear()

    def on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._filling or item.column() != SPARE_COLUMN:
            return
        line = self.rows[item.row()]
        try:
            count = int(item.text())
            if count < 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Spare Parts", "Enter a whole number of spare parts, zero or more.")
            count = self.store.spare(None, line.mpn)
        self.store.set_spare(None, line.mpn, count)  # emits changed, which redraws the table

    def update_footer(self) -> None:
        per_unit = self.dataset.per_unit_usd
        multiplier = self.qty_box.value()
        text = f"Per reader: {usd(per_unit)}"
        if multiplier > 1:
            text += f".  For {plural(multiplier, 'reader')}: {usd(per_unit * multiplier)}"
        text += "."
        if self.dataset.unavailable_line_items:
            text += "  Not in stock: " + ", ".join(self.dataset.unavailable_line_items) + "."
        self.footer.setToolTip("Prices come from the dated listings in the detail pane. A part with no stock still counts here.")
        self.footer.setText(text)
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
            ("Price basis", BASIS_WORDS[line.price_status]),
        ]
        rows = "".join(f"<tr><td><b>{k}:</b>&nbsp;</td><td>{v}</td></tr>" for k, v in fields if v)
        offers = ""
        if line.offers:
            offers = "<p><b>Offers:</b></p><ul>" + "".join(
                f'<li><a href="{o["url"]}">{o["supplier"]}</a>: {usd(o["unitPriceUsd"])} ({o["basis"]}), seen {o["observed"]}, '
                f'stock: {o["stock"]}.{(" " + o["note"]) if o.get("note") else ""}</li>' for o in line.offers) + "</ul>"
        self.detail.setHtml(
            f"<h3>{', '.join(line.refs) or 'No reference'}</h3><p>{line.function or line.description}</p>"
            f"<table>{rows}</table>{offers}<p>{'<br>'.join(links) or 'No supplier links for this part.'}</p>"
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
        left_out = {"inside-module": 0, "no-digikey-pn": 0, "optional-excluded": 0}
        for s in result.skipped:
            left_out[s.reason] += 1
        if result.skipped:
            message += (
                f"\n\nLeft out: {left_out['inside-module']} inside the C2 module, "
                f"{left_out['no-digikey-pn']} without a Digi-Key number, "
                f"{left_out['optional-excluded']} optional and turned off."
            )
        QMessageBox.information(self, "Export Digi-Key CSV", message)
