import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from open_book_builder.board_tab import BoardTab, ComponentItem
from open_book_builder.dataset import load_dataset
from open_book_builder.geometry import arc_path

GOLDEN = Path(__file__).parent / "fixtures" / "board-dataset.golden.json"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_arc_stays_on_circle(app):
    p = arc_path((0.0, 3.0), (0.87868, 0.87868), (3.0, 0.0))
    r = [(p.pointAtPercent(t / 20).x(), p.pointAtPercent(t / 20).y()) for t in range(21)]
    cx, cy = 3.0, 3.0
    assert all(abs(((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 - 3.0) < 0.01 for x, y in r)
    b = p.boundingRect()
    assert b.width() < 3.2 and b.height() < 3.2  # the short corner arc, not the long way round


def test_board_draws_both_boards_and_sides(app):
    tab = BoardTab(load_dataset(GOLDEN))
    for board in range(2):
        for side in range(2):
            tab.board_box.setCurrentIndex(board)
            tab.side_box.setCurrentIndex(side)
            tab.traces_box.setChecked(True)
            drawn = [i for i in tab.scene.items() if isinstance(i, ComponentItem)]
            expected = sum(c["side"] == tab.side_box.currentData() for c in tab.components)
            assert len(drawn) == expected


def test_fabrication_files_replace_the_design_pads_when_ready(app):
    tab = BoardTab(load_dataset(GOLDEN))
    tab.wait_for_fabrication()
    tab.traces_box.setChecked(True)
    for board in range(2):
        for side in range(2):
            tab.board_box.setCurrentIndex(board)
            tab.side_box.setCurrentIndex(side)
            kinds = [type(i).__name__ for i in tab.scene.items()]
            assert kinds.count("QGraphicsPathItem") >= 3  # edge, copper (two layers), drills, silkscreen
            pads = [i for i in tab.scene.items() if i.parentItem() is not None and isinstance(i.parentItem(), ComponentItem)]
            assert pads == []  # the Gerber copper already contains every pad
    tab.source_box.setCurrentIndex(1)  # design file
    assert any(isinstance(i.parentItem(), ComponentItem) for i in tab.scene.items() if i.parentItem() is not None)


def test_selecting_component_shows_bom_detail(app):
    tab = BoardTab(load_dataset(GOLDEN))
    tab.side_box.setCurrentIndex(1)
    item = next(i for i in tab.scene.items() if isinstance(i, ComponentItem))
    item.setSelected(True)
    assert tab.components[item.index]["ref"] in tab.detail.toPlainText()
