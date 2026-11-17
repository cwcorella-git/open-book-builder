import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

import shutil

from open_book_builder.assembly_tab import AssemblyTab
from open_book_builder.bom_tab import BomTab
from open_book_builder.checklist_tab import ChecklistTab
from open_book_builder.config_store import ConfigStore
from open_book_builder.dataset import find_data_dir
from open_book_builder.dataset import load_dataset
from open_book_builder.window import MainWindow

GOLDEN = Path(__file__).parent / "fixtures" / "board-dataset.golden.json"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)


@pytest.fixture
def store(tmp_path):
    copy = tmp_path / "configs.json"
    shutil.copy(find_data_dir() / "configs.json", copy)
    return ConfigStore(copy)


def test_bom_filters_and_totals(app, store):
    tab = BomTab(load_dataset(GOLDEN), store)
    assert tab.table.rowCount() == 17  # module internals are hidden by default
    tab.internals_box.setChecked(True)
    assert tab.table.rowCount() == 24
    tab.board_box.setCurrentIndex(2)  # C2 driver
    assert all(r.board == "c2-driver" for r in tab.rows)
    tab.board_box.setCurrentIndex(0)
    tab.internals_box.setChecked(False)
    tab.optional_box.setChecked(False)
    assert not any(r.optional for r in tab.rows)
    tab.qty_box.setValue(10)
    assert "$325.30" in tab.footer.text()


def test_assembly_progress_persists(app, settings):
    ds = load_dataset(GOLDEN)
    tab = AssemblyTab(ds, settings)
    tab.list.setCurrentRow(0)
    tab.toggle_current()
    assert AssemblyTab(ds, settings).completed == {ds.assembly[0].id}


def test_window_builds(app, settings, store):
    win = MainWindow(load_dataset(GOLDEN), settings, store)
    assert win.windowTitle() == "Open Book Builder[*]"
    assert [win.tabs.tabText(i) for i in range(5)] == ["BOM", "Checklist", "Assembly", "Board", "Case"]
    assert "$32.53" in win.cost_label.text()


def test_spares_and_order_columns(app, store):
    tab = BomTab(load_dataset(GOLDEN), store)
    tab.qty_box.setValue(10)
    r = next(i for i, l in enumerate(tab.rows) if l.mpn == "TL1107AF180WQ")
    assert tab.table.item(r, 4).text() == "7" and tab.table.item(r, 5).text() == "5"
    assert tab.table.item(r, 6).text() == "75"  # 7 buttons x 10 readers + 5 spares
    tab.table.item(r, 5).setText("8")
    assert store.dirty and store.spare(None, "TL1107AF180WQ") == 8
    r = next(i for i, l in enumerate(tab.rows) if l.mpn == "TL1107AF180WQ")
    assert tab.table.item(r, 6).text() == "78"


def test_checklist_empty_then_filled(app, store):
    store.set_quantity("batch", 0)
    tab = ChecklistTab(load_dataset(GOLDEN), store)
    assert "has no readers yet" in tab.empty.text() and tab.stack.currentIndex() == 1
    tab.readers_box.setValue(10)
    assert store.quantity("batch") == 10 and store.dirty
    assert tab.stack.currentIndex() == 0
    items = {r["item"].split("  ")[0]: r for r in tab.rows}
    assert items["SC0915"]["order"] == 11  # 10 readers + 1 spare
    assert items["C1 main board, bare PCB"]["status"] == "open"
    assert "not a full budget" in tab.totals.text()
    assert "to get" in tab.tools_line.text()
    assert all("Inside" not in r["item"] for r in tab.rows)  # module internals never listed


def test_save_writes_json(app, store):
    store.set_quantity("batch", 3)
    store.save()
    assert ConfigStore(store.path).quantity("batch") == 3 and not store.dirty
