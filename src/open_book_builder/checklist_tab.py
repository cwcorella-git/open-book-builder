"""Checklist tab: everything to buy or do for one configuration, with batch totals."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QSpinBox, QStackedLayout, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .bom_tab import BASIS_TIPS, usd
from .config_store import ConfigStore
from .dataset import Dataset, load_checklist, source_name

COLUMNS = ["Group", "Item", "Qty", "Spare", "Order", "Unit", "Date", "Status", "Source"]
NUMERIC = {2, 3, 4, 5}
SPARE_COLUMN = 3
GROUP_ORDER = ["Boards", "Parts", "Cards and batteries", "Fees", "Tools"]
STATUS_WORDS = {"listed": "Listed", "estimate": "Estimate", "quote": "Quote", "owned": "Owned", "open": "Open"}
STATUS_TIPS = {
    **{k: v for k, v in BASIS_TIPS.items() if k},
    "owned": "You already have this. It adds nothing to the budget.",
    "open": "No price or quote yet. Get one before you count on a total.",
}


class ChecklistTab(QWidget):
    def __init__(self, dataset: Dataset, store: ConfigStore, parent: QWidget | None = None):
        super().__init__(parent)
        self.dataset = dataset
        self.store = store
        self.extra = load_checklist()
        self.rows: list[dict] = []
        self._filling = False

        self.config_box = QComboBox()
        for cfg in store.configurations():
            self.config_box.addItem(cfg["name"], cfg["id"])
        self.config_box.setToolTip("The three configurations share one PCB design. Their features are not defined yet.")
        self.readers_box = QSpinBox()
        self.readers_box.setRange(0, 999)
        self.readers_box.setToolTip("How many readers of this configuration to build. Saved with File > Save.")
        self.optional_box = QCheckBox("Include optional parts")
        self.optional_box.setToolTip("Adds the expansion connectors and their resistors for this configuration.")

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        for text, widget in (("Configuration:", self.config_box), ("Readers:", self.readers_box)):
            controls.addWidget(QLabel(text))
            controls.addWidget(widget)
        controls.addWidget(self.optional_box)
        controls.addStretch(1)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideRight)
        for column, tip in {
            "Spare": "Spare units for this configuration. Double-click to edit. Parts start from the BOM spares.",
            "Order": "Quantity to buy or arrange: the amount for all readers plus spares.",
            "Unit": "Price for one, before shipping, tax and tariffs. n/a means no price yet.",
        }.items():
            self.table.horizontalHeaderItem(COLUMNS.index(column)).setToolTip(tip)

        self.empty = QLabel()
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setWordWrap(True)
        self.content = QWidget()
        stack = QStackedLayout(self.content)
        stack.addWidget(self.table)
        stack.addWidget(self.empty)
        self.stack = stack

        self.totals = QLabel()
        self.totals.setWordWrap(True)
        self.tools_line = QLabel()
        self.tools_line.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.content, 1)
        layout.addWidget(self.totals)
        layout.addWidget(self.tools_line)

        self.config_box.currentIndexChanged.connect(self.load_config)
        self.readers_box.valueChanged.connect(self.on_readers)
        self.optional_box.toggled.connect(self.on_optional)
        self.table.itemChanged.connect(self.on_item_changed)
        store.changed.connect(self.refresh)
        self.load_config()

    @property
    def config_id(self) -> str:
        return self.config_box.currentData()

    def load_config(self) -> None:
        self._filling = True
        self.readers_box.setValue(self.store.quantity(self.config_id))
        self.optional_box.setChecked(self.store.include_optional(self.config_id))
        self._filling = False
        self.refresh()

    def on_readers(self, value: int) -> None:
        if not self._filling:
            self.store.set_quantity(self.config_id, value)

    def on_optional(self, value: bool) -> None:
        if not self._filling:
            self.store.set_include_optional(self.config_id, value)

    # -- rows ---------------------------------------------------------------
    def build_rows(self, readers: int, optional: bool) -> list[dict]:
        rows = []
        for line in self.dataset.bom:
            if line.route_detail or (line.optional and not optional):
                continue
            is_module = line.mpn == "OSO-BOOK-C2-01"
            rows.append({
                "group": "Boards" if is_module else "Parts", "item": f"{line.mpn}  {line.description}",
                "key": line.mpn, "qty": line.qty * readers, "unit": line.unit_cost_usd,
                "date": line.offers[0]["observed"] if line.offers else "",
                "status": line.price_status or "open", "source": source_name(line),
                "tip": line.function or line.description, "editable": True, "in_stock": line.in_stock,
            })
        for item in self.extra:
            per = item["basis"] == "per reader"
            rows.append({
                "group": item["group"], "item": item["item"], "key": item["id"],
                "qty": item["quantity"] * (readers if per else 1), "unit": item["unitPriceUsd"],
                "date": item["observed"] or "", "status": item["status"], "source": item["source"],
                "tip": item["note"] or item["item"], "editable": per and item["group"] != "Tools", "in_stock": None,
            })
        rows.sort(key=lambda r: GROUP_ORDER.index(r["group"]))
        return rows

    def refresh(self) -> None:
        readers = self.readers_box.value()
        cfg = self.store.config(self.config_id)
        if readers == 0:
            self.empty.setText(f"{cfg['name']} has no readers yet. Set Readers above to see what to order.")
            self.stack.setCurrentIndex(1)
            self.rows = []
            self.totals.setText("")
            self.tools_line.setText("")
            return
        self.stack.setCurrentIndex(0)
        self.rows = self.build_rows(readers, self.optional_box.isChecked())
        self._filling = True
        self.table.setRowCount(len(self.rows))
        priced = 0.0
        open_count = 0
        no_stock = [r["key"] for r in self.rows if r["in_stock"] is False]
        tools_open, tools_owned, tools_priced = [], 0, 0.0
        for r, row in enumerate(self.rows):
            spare = self.store.spare(self.config_id, row["key"]) if row["editable"] else 0
            order = row["qty"] + spare
            row["order"] = order
            tool = row["group"] == "Tools"
            has_price = row["unit"] is not None and row["status"] in ("listed", "estimate", "quote")
            if tool:
                if row["status"] == "owned":
                    tools_owned += 1
                else:
                    tools_open.append(row["item"])
                    tools_priced += row["unit"] * order if has_price else 0.0
            elif row["status"] != "owned":
                if has_price:
                    priced += row["unit"] * order
                else:
                    open_count += 1
            cells = [row["group"], row["item"], str(row["qty"]), str(spare) if row["editable"] else "", str(order),
                     usd(row["unit"]), row["date"], STATUS_WORDS[row["status"]], row["source"]]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setToolTip(row["tip"] if c == 1 else text)
                if c in NUMERIC:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                flags = item.flags() & ~Qt.ItemIsEditable
                if c == SPARE_COLUMN and row["editable"]:
                    flags |= Qt.ItemIsEditable
                    item.setToolTip("Spare units for this configuration. Double-click to edit.")
                if c == COLUMNS.index("Status"):
                    item.setToolTip(STATUS_TIPS[row["status"]])
                item.setFlags(flags)
                self.table.setItem(r, c, item)
        self._filling = False
        header = self.table.horizontalHeader()
        for c in range(len(COLUMNS)):
            header.setSectionResizeMode(c, QHeaderView.Stretch if c == 1 else QHeaderView.ResizeToContents)
        self.totals.setText(
            f"Priced items for {readers} reader{'s' if readers != 1 else ''}, with spares: {usd(priced)}. "
            f"{open_count} item{'s' if open_count != 1 else ''} still without a price. "
            "This is not a full budget: shipping, tax, setup fees and the C2 module are open."
            + (f" Not in stock: {', '.join(no_stock)}." if no_stock else "")
        )
        self.tools_line.setText(
            f"One-time tools, kept apart from the batch: {tools_owned} owned, {len(tools_open)} to get"
            + (f" ({usd(tools_priced)} priced)." if tools_priced else ", none priced yet.")
        )

    def on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._filling or item.column() != SPARE_COLUMN:
            return
        row = self.rows[item.row()]
        try:
            count = int(item.text())
            if count < 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Spare Parts", "Enter a whole number of spare parts, zero or more.")
            count = self.store.spare(self.config_id, row["key"])
        self.store.set_spare(self.config_id, row["key"], count)
        self.refresh()
