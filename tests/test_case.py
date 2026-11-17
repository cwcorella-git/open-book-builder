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


def test_depth_buffer_nearer_triangle_wins_regardless_of_draw_order():
    import numpy as np
    from open_book_builder.case_tab import rasterize

    sx = np.array([[0, 20, 0], [0, 20, 0]], dtype=float)
    sy = np.array([[0, 0, 20], [0, 0, 20]], dtype=float)
    near, far = np.full(3, 1.0, dtype=np.float32), np.full(3, 5.0, dtype=np.float32)
    for depth, shade in ((np.array([near, far]), np.array([0.9, 0.2])), (np.array([far, near]), np.array([0.2, 0.9]))):
        img = rasterize(sx, sy, depth, shade.astype(np.float32), 24, 24)
        assert abs(img[5, 5] - 0.9) < 1e-6  # the near triangle's shade, whichever was drawn last
    assert img[22, 22] == 0  # outside both triangles
