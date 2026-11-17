import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from open_book_builder.board_tab import BoardTab
from open_book_builder.dataset import load_dataset
from open_book_builder.mesh3d import SLAB, THICKNESS, WALL, board_mesh, outline_polygon
from open_book_builder.meshview import MeshWidget, rasterize_ids

GOLDEN = Path(__file__).parent / "fixtures" / "board-dataset.golden.json"
COLORS = ((90, 90, 90), (200, 200, 200), (230, 230, 230))


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def dataset():
    return load_dataset(GOLDEN)


def test_outlines_close_and_keep_their_holes(dataset):
    c1 = outline_polygon(dataset.boards["c1-main"])
    assert c1.area == pytest.approx(85 * 115, rel=0.02)  # a rounded, notched 85 x 115 mm board
    assert len(c1.interiors) == 4  # the four mounting holes
    c2 = outline_polygon(dataset.boards["c2-driver"])
    assert c2.area == pytest.approx(17.272 * 23.876, rel=0.01) and len(c2.interiors) == 3


def test_board_mesh_stacks_parts_on_the_right_faces(dataset):
    board = dataset.boards["c1-main"]
    tris, colors, groups = board_mesh(board, *COLORS)
    assert tris.shape[1:] == (3, 3) and len(colors) == len(groups) == len(tris)
    assert set(groups.tolist()) >= {SLAB, WALL} | set(range(len(board["components"])))
    for index, comp in enumerate(board["components"]):
        z = tris[groups == index][:, :, 2]
        if comp["side"] == "top":
            assert z.min() == pytest.approx(THICKNESS) and z.max() == pytest.approx(THICKNESS + comp["footprintBbox"]["height3d"])
        else:
            assert z.max() == pytest.approx(0.0) and z.min() == pytest.approx(-comp["footprintBbox"]["height3d"])
    x, y = tris[:, :, 0], tris[:, :, 1]
    assert x.min() >= -0.5 and x.max() <= 85.5  # the 85 mm board, a part may overhang a little
    assert -115.5 <= y.min() and y.max() <= 0.5


def test_nearer_triangle_wins_in_the_id_buffer():
    sx = np.array([[0, 20, 0], [0, 20, 0]], dtype=float)
    sy = np.array([[0, 0, 20], [0, 0, 20]], dtype=float)
    near, far = np.full(3, 1.0), np.full(3, 5.0)
    ids = rasterize_ids(sx, sy, np.array([far, near]), 24, 24)
    assert ids[5, 5] == 1 and ids[22, 22] == -1


def test_clicking_a_part_picks_its_group(app, dataset):
    tab = BoardTab(dataset)
    tab.view_box.setCurrentIndex(1)  # 3D, looking at the top
    tab.resize(1000, 640)
    tab.show()
    app.processEvents()
    widget = tab.view3d
    widget.grab()
    ref_to_index = {c["ref"]: i for i, c in enumerate(tab.components)}
    target = ref_to_index["B3"]  # a front button, on the top
    ys, xs = np.nonzero(widget.groups[np.maximum(widget._ids, 0)] == target)
    assert len(xs)
    point = QPointF(xs.mean() / widget._ids_scale, ys.mean() / widget._ids_scale)
    assert widget.group_at(point) == target
    assert widget.group_at(QPointF(2, 2)) == -1  # empty space
    tab.on_pick3d(target)
    assert "B3" in tab.detail.toPlainText() and widget.highlight_group == target
    tab.on_pick3d(-1)
    assert widget.highlight_group is None


def test_side_choice_sets_the_3d_camera(app, dataset):
    tab = BoardTab(dataset)
    tab.view_box.setCurrentIndex(1)
    assert tab.view3d.pitch > 0
    tab.side_box.setCurrentIndex(1)
    assert tab.view3d.pitch < 0
    tab.view_box.setCurrentIndex(0)  # back to 2D
    assert tab.stack.currentIndex() == 0


def test_both_boards_draw_in_3d(app, dataset):
    tab = BoardTab(dataset)
    tab.view_box.setCurrentIndex(1)
    for board in range(2):
        tab.board_box.setCurrentIndex(board)
        image = tab.view3d._render(1.0)
        assert not image.isNull() and tab.view3d._ids is not None and (tab.view3d._ids >= 0).any()
