"""Board tab: 2D view of a board's outline, copper, pads and components."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPalette, QPen, QTransform
from PySide6.QtWidgets import (
    QStackedWidget, QStyle, QStyleOptionGraphicsItem, QCheckBox, QComboBox, QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem,
    QGraphicsRectItem, QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView, QHBoxLayout,
    QLabel, QPushButton, QSplitter, QTextBrowser, QVBoxLayout, QWidget,
)

from . import fabrication
from .mesh3d import board_mesh
from .meshview import MeshWidget
from .dataset import BOARD_LABELS, BomLine, Dataset
from .geometry import arc_path, component_rect, polygons_to_path


def blend(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(*(int(a.getRgb()[i] * (1 - t) + b.getRgb()[i] * t) for i in range(3)))


class BoardView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene):
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class ComponentItem(QGraphicsRectItem):
    """Bounding box of a component. Pads are children; selecting it shows a dashed outline."""

    def __init__(self, index: int, rect: QRectF):
        super().__init__(rect)
        self.index = index
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptedMouseButtons(Qt.LeftButton)

    def paint(self, painter, option, widget=None) -> None:
        """A selected part gets a filled, outlined highlight in the palette's highlight color."""
        if self.isSelected():
            color = (widget.palette() if widget else QPalette()).color(QPalette.Highlight)
            pen = QPen(color)
            pen.setCosmetic(True)
            pen.setWidthF(2.5)
            fill = QColor(color)
            fill.setAlpha(90)
            painter.setPen(pen)
            painter.setBrush(fill)
            painter.drawRect(self.rect())
            return
        plain = QStyleOptionGraphicsItem(option)
        plain.state &= ~QStyle.State_Selected
        super().paint(painter, plain, widget)


class BoardTab(QWidget):
    selection_message = Signal(str)

    def __init__(self, dataset: Dataset, parent: QWidget | None = None):
        super().__init__(parent)
        self.dataset = dataset
        self.components: list[dict] = []

        self.board_box = QComboBox()
        for key, label in BOARD_LABELS.items():
            self.board_box.addItem(label, key)
        self.board_box.setToolTip("Choose which board to draw.")
        self.side_box = QComboBox()
        self.side_box.addItem("Top", "top")
        self.side_box.addItem("Bottom", "bottom")
        self.side_box.setToolTip("Look at the board from this side. The 2D bottom view is mirrored, as if you turned the board over. In 3D this sets where the camera starts.")
        self.view_box = QComboBox()
        self.view_box.addItem("2D", "2d")
        self.view_box.addItem("3D", "3d")
        self.view_box.setToolTip("2D is the layer view. 3D is the board as a slab with boxes for the parts: "
                                 "drag to turn it, scroll to zoom, click a part to select it.")
        self.source_box = QComboBox()
        self.source_box.addItem("Fabrication files", "fabrication")
        self.source_box.addItem("Design file", "design")
        self.source_box.setToolTip(
            "Fabrication files are the Gerbers and drills the board is made from, so pads, traces, pours and "
            "silkscreen are as ordered. The design file is the KiCad or EAGLE source the parts list comes from.")
        self.traces_box = QCheckBox("Show copper")
        self.traces_box.setToolTip("Copper on the side you are viewing is bold; the other side is faint. With the design file this is traces and vias.")
        self.silk_box = QCheckBox("Show silkscreen")
        self.silk_box.setChecked(True)
        self.silk_box.setToolTip("Printed outlines and markings on the viewed side.")
        self.labels_box = QCheckBox("Show labels")
        self.labels_box.setChecked(True)
        self.labels_box.setToolTip("Reference names such as U1 or R3.")
        self.fit_button = QPushButton("Fit to Window")
        self.fit_button.setToolTip("Zoom so the whole board is visible. In 3D it returns to the starting view.")

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        for text, widget in (("Board:", self.board_box), ("View:", self.view_box), ("Side:", self.side_box),
                             ("Layers from:", self.source_box)):
            controls.addWidget(QLabel(text))
            controls.addWidget(widget)
        for box in (self.traces_box, self.silk_box, self.labels_box):
            controls.addWidget(box)
        controls.addStretch(1)
        controls.addWidget(self.fit_button)

        self.scene = QGraphicsScene(self)
        self.view = BoardView(self.scene)
        self.detail = QTextBrowser()
        self.detail.setMinimumWidth(220)
        self.detail.setPlaceholderText("Select a component to see what it is.")
        splitter = QSplitter()
        self.view3d = MeshWidget(home=(0.0, 58.0))
        self.view3d.picked.connect(self.on_pick3d)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.view)
        self.stack.addWidget(self.view3d)
        splitter.addWidget(self.stack)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 3)
        splitter.setSizes([760, 240])

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(splitter, 1)

        for signal in (self.board_box.currentIndexChanged, self.side_box.currentIndexChanged,
                       self.source_box.currentIndexChanged, self.view_box.currentIndexChanged,
                       self.traces_box.toggled, self.silk_box.toggled, self.labels_box.toggled):
            signal.connect(self.redraw)
        self._paths: dict = {}
        self._fab_ready = False
        self._warm = fabrication.warm_up({bid: data["outline"]["heightMm"] for bid, data in dataset.boards.items()})
        self._poll = QTimer(self)  # the order files are read in the background; switch to them when they are ready
        self._poll.setInterval(250)
        self._poll.timeout.connect(self._check_fabrication)
        self._poll.start()
        self.fit_button.clicked.connect(self.fit)
        self.scene.selectionChanged.connect(self.on_selection)
        self.redraw()

    def _check_fabrication(self) -> None:
        if not self._warm.is_alive():
            self._poll.stop()
            self._fab_ready = True
            if self.source_box.currentData() == "fabrication":
                self.redraw()
                self.selection_message.emit("Fabrication files loaded.")

    def wait_for_fabrication(self) -> None:
        """Block until the order files are read. For tests and scripts."""
        self._warm.join()
        self._check_fabrication()

    # -- drawing ------------------------------------------------------------
    def palette_colors(self) -> dict[str, QColor]:
        pal = self.palette()
        text, base = pal.color(QPalette.Text), pal.color(QPalette.Base)
        return {
            "outline": text,
            "copper": pal.color(QPalette.Highlight),
            "copper_far": blend(base, pal.color(QPalette.Highlight), 0.3),
            "pad": blend(base, text, 0.55),
            "silk": blend(base, text, 0.4),
            "body": blend(base, text, 0.12),
        }

    def redraw(self) -> None:
        board = self.dataset.boards[self.board_box.currentData()]
        side = self.side_box.currentData()
        col = self.palette_colors()
        outline = board["outline"]
        width, height = outline["widthMm"], outline["heightMm"]
        board_id = self.board_box.currentData()
        in_3d = self.view_box.currentData() == "3d"
        for control in (self.source_box, self.traces_box, self.silk_box, self.labels_box):
            control.setEnabled(not in_3d)
        self.stack.setCurrentIndex(1 if in_3d else 0)
        if in_3d:
            self.show_3d(board)
            return
        wants_fab = self.source_box.currentData() == "fabrication"
        fab = wants_fab and fabrication.available(board_id) and self._fab_ready
        if wants_fab and not fabrication.available(board_id):
            self.selection_message.emit("No fabrication files for this board, so the design file is shown.")
        elif wants_fab and not self._fab_ready:
            self.selection_message.emit("Reading the fabrication files. The design file is shown until they are ready.")

        self.scene.blockSignals(True)
        self.scene.clear()
        self.scene.blockSignals(False)
        root = QGraphicsRectItem(0, 0, width, height)
        root.setPen(QPen(Qt.NoPen))
        self.scene.addItem(root)
        if side == "bottom":
            root.setTransform(QTransform(-1, 0, 0, 1, width, 0))

        cosmetic = lambda color, w=1.0: self._pen(color, w)
        # Board face and edge cuts.
        path = QPainterPath()
        for seg in outline["edgeSegments"]:
            pts = seg["points"]
            if seg["kind"] == "arc" and len(pts) == 3:
                path.addPath(arc_path(*pts))
            else:
                path.moveTo(*pts[0])
                for p in pts[1:]:
                    path.lineTo(*p)
        edge = QGraphicsPathItem(path, root)
        edge.setPen(cosmetic(col["outline"], 2))
        edge.setBrush(QBrush(col["body"]))
        edge.setZValue(0)
        for hole in outline["holes"]:
            r = hole["diameter"] / 2
            item = QGraphicsEllipseItem(hole["x"] - r, hole["y"] - r, 2 * r, 2 * r, root)
            item.setPen(cosmetic(col["outline"], 1))
            item.setBrush(QBrush(self.palette().color(QPalette.Base)))
            item.setZValue(1)

        if fab:
            self.draw_fabrication(root, board_id, side, height, col)
        if self.traces_box.isChecked() and not fab:
            near, far = ("f-cu", "b-cu") if side == "top" else ("b-cu", "f-cu")
            for seg in board["traces"]:
                line = QPainterPath(QPointF(*seg["start"]))
                line.lineTo(QPointF(*seg["end"]))
                item = QGraphicsPathItem(line, root)
                pen = QPen(col["copper"] if seg["layer"] == near else col["copper_far"])
                pen.setWidthF(seg["width"])
                pen.setCapStyle(Qt.RoundCap)
                item.setPen(pen)
                item.setZValue(2 if seg["layer"] == near else 1.5)
            for via in board["vias"]:
                r = via["diameter"] / 2
                item = QGraphicsEllipseItem(via["at"][0] - r, via["at"][1] - r, 2 * r, 2 * r, root)
                item.setPen(cosmetic(col["copper"], 1))
                item.setBrush(QBrush(self.palette().color(QPalette.Base)))
                item.setZValue(2.5)

        if self.silk_box.isChecked() and not fab:
            silk = outline["silkscreenTop" if side == "top" else "silkscreenBottom"]
            silk_path = QPainterPath()
            for ln in silk["lines"]:
                silk_path.moveTo(*ln["start"])
                silk_path.lineTo(*ln["end"])
            for arc in silk["arcs"]:
                silk_path.addPath(arc_path(arc["start"], arc["mid"], arc["end"]))
            for c in silk["circles"]:
                silk_path.addEllipse(QPointF(*c["center"]), c["radius"], c["radius"])
            item = QGraphicsPathItem(silk_path, root)
            item.setPen(cosmetic(col["silk"], 1))
            item.setZValue(3)

        self.components = board["components"]
        for index, comp in enumerate(self.components):
            if comp["side"] != side:
                continue
            left, top, right, bottom = component_rect(comp)  # follows the pads, so it need not be centred
            rect = QRectF(left, top, right - left, bottom - top)
            item = ComponentItem(index, rect)
            item.setParentItem(root)
            item.setPos(comp["x"], comp["y"])
            item.setRotation(-comp["rotation"])
            item.setPen(cosmetic(col["silk"], 1))
            item.setZValue(4)
            item.setToolTip(f"{comp['ref']}: {comp['footprint']}")
            for pad in ([] if fab else comp["pads"]):
                w, h = pad["size"]
                shape = QPainterPath()
                rect = QRectF(pad["x"] - w / 2, pad["y"] - h / 2, w, h)
                if pad["shape"] in ("circle", "oval"):
                    shape.addEllipse(rect)
                else:
                    shape.addRect(rect)
                pad_item = QGraphicsPathItem(shape, item)
                pad_item.setPen(QPen(Qt.NoPen))
                pad_item.setBrush(QBrush(col["pad"]))
                pad_item.setToolTip(f"{comp['ref']} pad {pad['number']}" + (f": {pad['netName']}" if pad.get("netName") else ""))
            if self.labels_box.isChecked():
                label = QGraphicsSimpleTextItem(comp["ref"], root)
                label.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
                label.setBrush(QBrush(col["outline"]))
                label.setPos(comp["x"], comp["y"])
                label.setZValue(5)

        self.scene.setSceneRect(edge.boundingRect().adjusted(-4, -4, 4, 4))
        self.fit()
        self.detail.clear()

    def cached_path(self, kind: str, board: str, side: str, height: float):
        key = (kind, board, side)
        if key not in self._paths:
            geometry = (fabrication.copper if kind == "copper" else fabrication.silkscreen)(board, side, height)
            self._paths[key] = polygons_to_path(geometry)
        return self._paths[key]

    def draw_fabrication(self, root, board: str, side: str, height: float, col: dict) -> None:
        """Copper, silkscreen and drills as they are in the order files."""
        far_side = "bottom" if side == "top" else "top"
        base = self.palette().color(QPalette.Base)
        if self.traces_box.isChecked():
            for layer_side, color, z in ((far_side, col["copper_far"], 1.5), (side, col["copper"], 2)):
                item = QGraphicsPathItem(self.cached_path("copper", board, layer_side, height), root)
                item.setPen(QPen(Qt.NoPen))
                item.setBrush(QBrush(color))
                item.setZValue(z)
            holes = QPainterPath()
            for x, y, d in fabrication.drills(board, height):
                holes.addEllipse(QPointF(x, y), d / 2, d / 2)
            item = QGraphicsPathItem(holes, root)
            item.setPen(QPen(Qt.NoPen))
            item.setBrush(QBrush(base))
            item.setZValue(2.6)
        if self.silk_box.isChecked():
            item = QGraphicsPathItem(self.cached_path("silk", board, side, height), root)
            item.setPen(QPen(Qt.NoPen))
            item.setBrush(QBrush(col["silk"]))
            item.setZValue(3)

    @staticmethod
    def _pen(color: QColor, width: float) -> QPen:
        pen = QPen(color)
        pen.setCosmetic(True)
        pen.setWidthF(width)
        return pen

    def fit(self) -> None:
        if self.view_box.currentData() == "3d":
            self.view3d.reset_view()
            return
        self.view.resetTransform()
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.view.transform().isIdentity():
            self.fit()

    # -- selection ----------------------------------------------------------
    def bom_line_for(self, comp: dict) -> BomLine | None:
        for line in self.dataset.bom:
            if line.board == comp["board"] and (comp["bomRef"] in line.refs or comp["ref"] in line.refs):
                return line
        return None

    def highlight(self, board: str, refs: list[str]) -> str:
        """Show a board with some components selected. Returns a sentence saying what is shown."""
        data = self.dataset.boards[board]
        wanted = set(refs)
        on_side = {"top": 0, "bottom": 0}
        for comp in data["components"]:
            if comp["ref"] in wanted:
                on_side[comp["side"]] += 1
        side = "bottom" if on_side["bottom"] > on_side["top"] else "top"
        for box, value in ((self.board_box, board), (self.side_box, side)):
            box.blockSignals(True)
            box.setCurrentIndex(box.findData(value))
            box.blockSignals(False)
        self.labels_box.setChecked(True)
        self.redraw()
        self.scene.blockSignals(True)
        shown = 0
        for item in self.scene.items():
            if isinstance(item, ComponentItem) and self.components[item.index]["ref"] in wanted:
                item.setSelected(True)
                shown += 1
        self.scene.blockSignals(False)
        self.on_selection()
        elsewhere = on_side["top" if side == "bottom" else "bottom"]
        missing = len(wanted) - on_side["top"] - on_side["bottom"]
        message = f"Showing {shown} part{'s' if shown != 1 else ''} on the {side} of the {BOARD_LABELS[board]} board."
        if elsewhere:
            message += f" {elsewhere} more {'are' if elsewhere != 1 else 'is'} on the other side."
        if missing:
            message += f" {missing} not on this board."
        self.selection_message.emit(message)
        return message

    def show_3d(self, board: dict) -> None:
        pal = self.palette()
        base, text = pal.color(QPalette.Base), pal.color(QPalette.Text)
        rgb = lambda c: (c.red(), c.green(), c.blue())
        slab = rgb(blend(base, text, 0.35))
        panel = rgb(blend(base, text, 0.12))
        part = rgb(pal.color(QPalette.Button))
        tris, colors, groups = board_mesh(board, slab, part, panel)
        self.components = board["components"]
        self.view3d.home = (0.0, 58.0) if self.side_box.currentData() == "top" else (0.0, -58.0)  # look from that side
        self.view3d.set_mesh(tris, colors, groups)
        self.detail.clear()
        self.selection_message.emit("")

    def on_pick3d(self, group: int) -> None:
        if group < 0 or group >= len(self.components):
            self.view3d.set_highlight(None)
            self.detail.clear()
            self.selection_message.emit("")
            return
        self.view3d.set_highlight(group)
        self.show_detail_for([group])

    def on_selection(self) -> None:
        picked = [i for i in self.scene.selectedItems() if isinstance(i, ComponentItem)]
        self.show_detail_for([i.index for i in picked])

    def show_detail_for(self, indices: list[int]) -> None:
        if not indices:
            self.detail.clear()
            self.selection_message.emit("")
            return
        if len(indices) > 1:
            indices = sorted(indices, key=lambda i: self.components[i]["ref"])
            rows = []
            for index in indices:
                comp = self.components[index]
                line = self.bom_line_for(comp)
                rows.append(f"<li><b>{comp['ref']}</b>: {line.description if line else 'no entry in the parts list'}"
                            f"{' (' + line.mpn + ')' if line else ''}</li>")
            self.detail.setHtml(f"<h3>{len(indices)} parts selected</h3><ul>{''.join(rows)}</ul>")
            self.selection_message.emit(f"Selected: {', '.join(self.components[i]['ref'] for i in indices)}")
            return
        comp = self.components[indices[0]]
        line = self.bom_line_for(comp)
        nets = sorted({p["netName"] for p in comp["pads"] if p.get("netName")})
        part = (
            f"<p>{line.function or line.description}</p><p><b>Part:</b> {line.mpn}</p>"
            if line else "<p>This component has no entry in the parts list.</p>"
        )
        self.detail.setHtml(
            f"<h3>{comp['ref']}</h3>{part}"
            f"<p><b>Footprint:</b> {comp['footprint']}<br><b>Side:</b> {comp['side'].capitalize()}<br>"
            f"<b>Height:</b> {comp['footprintBbox']['height3d']:g} mm<br><b>Pads:</b> {len(comp['pads'])}</p>"
            f"<p><b>Nets:</b> {', '.join(nets) if nets else 'none'}</p>"
        )
        self.selection_message.emit(f"Selected: {comp['ref']}")
