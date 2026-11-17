import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from open_book_builder.case_tab import DESIGNS, CaseTab, load_stl
from open_book_builder.dataset import find_data_dir


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_stl_triangle_counts():
    case = find_data_dir() / "case"
    assert len(load_stl(case / "open-book-abridged-minimal-case.stl")) == 2554
    assert len(load_stl(case / "sprint-5-backplate.stl")) == 2732
    assert len(load_stl(case / "sprint-5-frontplate.stl")) == 3176


def test_case_tab_loads_each_design(app):
    tab = CaseTab()
    for i in range(len(DESIGNS)):
        tab.design_box.setCurrentIndex(i)
        assert len(tab.mesh.tris) > 0
    tab.mesh.grab()  # paints without error
