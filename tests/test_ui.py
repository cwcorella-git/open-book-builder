import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from open_book_builder.assembly_tab import AssemblyTab
from open_book_builder.bom_tab import BomTab
from open_book_builder.dataset import load_dataset
from open_book_builder.window import MainWindow

GOLDEN = Path(__file__).parent / "fixtures" / "board-dataset.golden.json"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat)


def test_bom_filters_and_totals(app):
    tab = BomTab(load_dataset(GOLDEN))
    assert tab.table.rowCount() == 24
    tab.board_box.setCurrentIndex(2)  # C2 driver
    assert all(r.board == "c2-driver" for r in tab.rows)
    tab.board_box.setCurrentIndex(0)
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


def test_window_builds(app, settings):
    win = MainWindow(load_dataset(GOLDEN), settings)
    assert win.windowTitle() == "Open Book Builder"
    assert [win.tabs.tabText(i) for i in range(4)] == ["BOM", "Assembly", "Board", "Case"]
    assert "$32.53" in win.cost_label.text()
