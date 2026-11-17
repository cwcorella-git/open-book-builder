import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from open_book_builder.board_tab import BoardTab
from open_book_builder.dataset import load_dataset
from open_book_builder.geometry import component_rect, to_board
from open_book_builder.mesh3d import COPPER_LIFT, SLAB, THICKNESS, WALL, board_mesh, outline_polygon
from open_book_builder.parts3d import BUILDERS, body
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
        parts = body(comp.get("heroMeshId"), component_rect(comp), comp["footprintBbox"]["height3d"])
        height = max(b[5] for b in parts) if parts else comp["footprintBbox"]["height3d"]
        if comp["side"] == "top":
            assert z.min() == pytest.approx(THICKNESS) and z.max() == pytest.approx(THICKNESS + height)
        else:
            assert abs(z.max()) < 1e-9 and z.min() == pytest.approx(-height)
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


HERO_IDS = {"pi-pico": "U1", "c2-module": "U2", "keystone-1022": "BT1", "mem2075": "U3"}


def test_hero_parts_are_several_boxes_inside_their_footprint(dataset):
    board = dataset.boards["c1-main"]
    tris, _, groups = board_mesh(board, *COLORS)
    for hero, ref in HERO_IDS.items():
        index = next(i for i, c in enumerate(board["components"]) if c["ref"] == ref)
        comp = board["components"][index]
        assert comp["heroMeshId"] == hero
        assert (groups == index).sum() > 12  # more than the single box it used to be
        left, top, right, bottom = component_rect(comp)
        corners = [to_board(comp, x, y) for x, y in ((left, top), (right, top), (right, bottom), (left, bottom))]
        xs, ys = [c[0] for c in corners], [-c[1] for c in corners]
        mine = tris[groups == index]
        # nubs and the SD slot reach a little past the pad rectangle, nothing else does
        assert mine[:, :, 0].min() >= min(xs) - 1.0 and mine[:, :, 0].max() <= max(xs) + 1.0
        assert mine[:, :, 1].min() >= min(ys) - 1.0 and mine[:, :, 1].max() <= max(ys) + 1.0


def test_every_part_body_is_well_formed():
    for hero, build in BUILDERS.items():
        boxes = build((-10.0, -20.0, 10.0, 20.0), 1.5)
        assert boxes
        for x0, y0, x1, y1, z0, z1, role in boxes:
            assert x1 > x0 and y1 > y0 and z1 > z0 >= 0 and role in {"body", "detail", "panel", "screen"}, hero


def test_display_panel_on_the_c2_has_a_screen_and_flex(dataset):
    board = dataset.boards["c2-driver"]
    index = next(i for i, c in enumerate(board["components"]) if c["ref"] == "Display")
    _, _, groups = board_mesh(board, *COLORS)
    assert (groups == index).sum() == 3 * 12


def test_copper_lies_on_each_face_of_the_slab(dataset):
    from open_book_builder import fabrication

    board = dataset.boards["c2-driver"]
    height = board["outline"]["heightMm"]
    copper = {side: fabrication.copper("c2-driver", side, height) for side in ("top", "bottom")}
    plain, _, _ = board_mesh(board, *COLORS)
    with_copper, colors, groups = board_mesh(board, *COLORS, copper, (200, 120, 40))
    added = with_copper[(colors == (200, 120, 40)).all(axis=1)]
    assert len(added) > 1000 and len(with_copper) - len(plain) == len(added)
    z = added[:, :, 2]
    assert set(np.round(np.unique(z), 3)) == {round(THICKNESS + COPPER_LIFT, 3), round(-COPPER_LIFT, 3)}
    assert (groups[(colors == (200, 120, 40)).all(axis=1)] == SLAB).all()  # a click on copper picks nothing


def test_triangle_budget_with_copper(dataset):
    from open_book_builder import fabrication

    for key, limit in (("c1-main", 25000), ("c2-driver", 8000)):
        board = dataset.boards[key]
        height = board["outline"]["heightMm"]
        copper = {side: fabrication.copper(key, side, height) for side in ("top", "bottom")}
        tris, _, _ = board_mesh(board, *COLORS, copper, (200, 120, 40))
        assert len(tris) < limit, (key, len(tris))


def test_flat_face_is_as_bright_from_below_as_from_above(app, dataset):
    tab = BoardTab(dataset)
    tab.view_box.setCurrentIndex(1)
    tab.board_box.setCurrentIndex(0)
    tab.traces_box.setChecked(False)  # leave the slab bare so one colour is measured
    means = []
    for side in range(2):
        tab.side_box.setCurrentIndex(side)
        image = tab.view3d._render(0.5)
        ids = tab.view3d._ids
        slab = tab.view3d.groups[np.maximum(ids, 0)] == SLAB
        slab &= ids >= 0
        pixels = np.array([[image.pixelColor(x, y).red() for x in range(image.width())] for y in range(image.height())])
        means.append(pixels[slab].mean())
    assert abs(means[0] - means[1]) / max(means) < 0.1, means
