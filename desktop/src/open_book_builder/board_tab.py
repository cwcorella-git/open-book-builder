"""Board tab: 2D view of a board's outline, copper, pads and components."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPalette, QPen, QTransform
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem,
    QGraphicsRectItem, QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView, QHBoxLayout,
    QLabel, QPushButton, QSplitter, QTextBrowser, QVBoxLayout, QWidget,
)

from .dataset import BOARD_LABELS, BomLine, Dataset
from .geometry import arc_path


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
        self.side_box.setToolTip("Look at the board from this side. The bottom view is mirrored, as if you turned the board over.")
        self.traces_box = QCheckBox("Show traces")
        self.traces_box.setToolTip("Copper traces and vias. Traces on the side you are viewing are bold; the other side is faint.")
        self.silk_box = QCheckBox("Show silkscreen")
        self.silk_box.setChecked(True)
        self.silk_box.setToolTip("Printed outlines and markings on the viewed side.")
        self.labels_box = QCheckBox("Show labels")
        self.labels_box.setChecked(True)
        self.labels_box.setToolTip("Reference names such as U1 or R3.")
        self.fit_button = QPushButton("Fit to Window")
        self.fit_button.setToolTip("Zoom so the whole board is visible (Ctrl+0).")

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        for text, widget in (("Board:", self.board_box), ("Side:", self.side_box)):
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
        splitter.addWidget(self.view)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 3)
        splitter.setSizes([760, 240])

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(splitter, 1)

        for signal in (self.board_box.currentIndexChanged, self.side_box.currentIndexChanged,
                       self.traces_box.toggled, self.silk_box.toggled, self.labels_box.toggled):
            signal.connect(self.redraw)
        self.fit_button.clicked.connect(self.fit)
        self.scene.selectionChanged.connect(self.on_selection)
        self.redraw()

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

        if self.traces_box.isChecked():
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

        if self.silk_box.isChecked():
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
            box = comp["footprintBbox"]
            item = ComponentItem(index, QRectF(-box["width"] / 2, -box["height"] / 2, box["width"], box["height"]))
            item.setParentItem(root)
            item.setPos(comp["x"], comp["y"])
            item.setRotation(-comp["rotation"])
            item.setPen(cosmetic(col["silk"], 1))
            item.setZValue(4)
            item.setToolTip(f"{comp['ref']}: {comp['footprint']}")
            for pad in comp["pads"]:
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

        self.scene.setSceneRect(QRectF(-4, -4, width + 8, height + 8))
        self.fit()
        self.detail.clear()

    @staticmethod
    def _pen(color: QColor, width: float) -> QPen:
        pen = QPen(color)
        pen.setCosmetic(True)
        pen.setWidthF(width)
        return pen

    def fit(self) -> None:
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

    def on_selection(self) -> None:
        picked = [i for i in self.scene.selectedItems() if isinstance(i, ComponentItem)]
        if not picked:
            self.detail.clear()
            self.selection_message.emit("")
            return
        comp = self.components[picked[0].index]
        line = self.bom_line_for(comp)
        nets = sorted({p["netName"] for p in comp["pads"] if p.get("netName")})
        part = (
            f"<p>{line.function or line.description}</p><p><b>Part:</b> {line.mpn}</p>"
            if line else "<p>This component has no entry in the parts list.</p>"
        )
        self.detail.setHtml(
            f"<h3>{comp['ref']}</h3>{part}"
            f"<p><b>Footprint:</b> {comp['footprint']}<br><b>Side:</b> {comp['side'].capitalize()}<br>"
            f"<b>Pads:</b> {len(comp['pads'])}</p>"
            f"<p><b>Nets:</b> {', '.join(nets) if nets else 'none'}</p>"
        )
        self.selection_message.emit(f"Selected: {comp['ref']}")
