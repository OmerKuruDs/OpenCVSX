"""NodeGraphView — visual representation of the pipeline as a horizontal
node chain.

Drop-in replacement for the QListWidget-based PipelineView. Each node is a
rounded rectangle painted on a QGraphicsScene; edges are bezier curves
connecting consecutive (enabled or disabled) nodes. Behaviours preserved
from the old view:

    * click a node     — emits `selection_changed(index)`
    * drag a node      — releases reorder the pipeline by x-position
    * toggle dot       — enables / disables that node (top-left chip)
    * X chip           — removes the node (top-right chip)
    * `set_timings`    — annotates each node with its last execution time

The underlying `Pipeline` data model is unchanged — this is a presentation
layer. A future iteration will replace the linear `Pipeline` with a true DAG
and reuse this same view with port-aware edges.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsView,
    QStyleOptionGraphicsItem,
    QWidget,
)

from cvsandbox.core.pipeline import Pipeline

NODE_WIDTH = 150
NODE_HEIGHT = 64
NODE_GAP = 56
SCENE_MARGIN = 24

CHIP_RADIUS = 7
CHIP_INSET = 8

PORT_RADIUS = 6
PORT_GAP = 14  # vertical gap between adjacent ports on the same edge

EDGE_COLOR = QColor("#5b6470")
EDGE_WIDTH = 2
PORT_FILL = QColor("#1d2129")
PORT_BORDER = QColor("#cfd6df")

DISABLED_ALPHA = 110

_CATEGORY_COLORS: dict[str, QColor] = {
    "Filtering": QColor("#3f7bd6"),
    "Threshold": QColor("#22a06b"),
    "Morphology": QColor("#b25cd0"),
    "Edge": QColor("#d6873f"),
    "Color": QColor("#d63f7b"),
    "Geometric": QColor("#3fb8d6"),
    "Analysis": QColor("#c9b542"),
}
_DEFAULT_CATEGORY_COLOR = QColor("#7d8590")


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as a short human-readable string."""
    if seconds < 1e-3:
        return f"{seconds * 1e6:.0f} µs"
    if seconds < 1.0:
        return f"{seconds * 1e3:.1f} ms"
    return f"{seconds:.2f} s"


def _category_color(category: str) -> QColor:
    return _CATEGORY_COLORS.get(category, _DEFAULT_CATEGORY_COLOR)


def _layout_x(index: int) -> float:
    return SCENE_MARGIN + index * (NODE_WIDTH + NODE_GAP)


class NodeItem(QGraphicsObject):
    """One pipeline node, rendered as a rounded rectangle with two small
    interactive chips (toggle and remove)."""

    body_clicked = Signal(int)
    enable_toggled = Signal(int)
    remove_requested = Signal(int)
    moved = Signal()
    drag_released = Signal(int)

    def __init__(
        self,
        index: int,
        title: str,
        category: str,
        enabled: bool,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self.index = index
        self.title = title
        self.category = category
        self.enabled = enabled
        self.timing: float | None = None
        self.selected = False
        self._color = _category_color(category)
        self._dragged = False
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

    # ------------------------------------------------------------------ painting

    def boundingRect(self) -> QRectF:  # noqa: N802 (Qt override)
        return QRectF(0, 0, NODE_WIDTH, NODE_HEIGHT)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.boundingRect().adjusted(0.5, 0.5, -0.5, -0.5)

        body_color = QColor(self._color)
        if not self.enabled:
            body_color.setAlpha(DISABLED_ALPHA)
        painter.setBrush(QBrush(body_color))

        border_color = QColor("#ffd866") if self.selected else QColor("#1d2129")
        border_width = 3 if self.selected else 1
        painter.setPen(QPen(border_color, border_width))
        painter.drawRoundedRect(rect, 10, 10)

        # Category strip on the left edge.
        strip = QRectF(rect.left(), rect.top(), 6, rect.height())
        accent = QColor(self._color).darker(140)
        painter.setBrush(accent)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(strip, 3, 3)

        # Title.
        painter.setPen(QColor("#ffffff"))
        title_font = QFont(painter.font())
        title_font.setBold(True)
        painter.setFont(title_font)
        title_rect = rect.adjusted(14, 6, -10, -22)
        painter.drawText(
            title_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self.title,
        )

        # Subtitle: category + timing.
        info_font = QFont(painter.font())
        info_font.setBold(False)
        info_font.setPointSize(max(7, info_font.pointSize() - 2))
        painter.setFont(info_font)
        painter.setPen(QColor("#e6e6e6"))
        info_text = self.category
        if self.timing is not None:
            info_text = f"{self.category}  ·  {format_duration(self.timing)}"
        info_rect = rect.adjusted(14, rect.height() - 22, -10, -4)
        painter.drawText(
            info_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            info_text,
        )

        # Toggle chip (top-left within the body).
        toggle_center = self._toggle_chip_center()
        painter.setPen(QPen(QColor("#1d2129"), 1))
        painter.setBrush(QColor("#cef1d2") if self.enabled else QColor("#3a3f48"))
        painter.drawEllipse(toggle_center, CHIP_RADIUS, CHIP_RADIUS)

        # Remove chip (top-right).
        remove_center = self._remove_chip_center()
        painter.setBrush(QColor("#3a3f48"))
        painter.drawEllipse(remove_center, CHIP_RADIUS, CHIP_RADIUS)
        painter.setPen(QPen(QColor("#ffffff"), 1.5))
        offset = CHIP_RADIUS - 3
        painter.drawLine(
            QPointF(remove_center.x() - offset, remove_center.y() - offset),
            QPointF(remove_center.x() + offset, remove_center.y() + offset),
        )
        painter.drawLine(
            QPointF(remove_center.x() - offset, remove_center.y() + offset),
            QPointF(remove_center.x() + offset, remove_center.y() - offset),
        )

    # ------------------------------------------------------------------ hit-tests

    def _toggle_chip_center(self) -> QPointF:
        return QPointF(NODE_WIDTH - 2 * (CHIP_INSET + CHIP_RADIUS) - 4, CHIP_INSET + CHIP_RADIUS - 2)

    def _remove_chip_center(self) -> QPointF:
        return QPointF(NODE_WIDTH - CHIP_INSET - CHIP_RADIUS, CHIP_INSET + CHIP_RADIUS - 2)

    def _hit_chip(self, point: QPointF, center: QPointF) -> bool:
        dx = point.x() - center.x()
        dy = point.y() - center.y()
        return dx * dx + dy * dy <= (CHIP_RADIUS + 2) ** 2

    # ------------------------------------------------------------------ events

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        pos = event.pos()
        if self._hit_chip(pos, self._toggle_chip_center()):
            self.enabled = not self.enabled
            self.update()
            self.enable_toggled.emit(self.index)
            event.accept()
            return
        if self._hit_chip(pos, self._remove_chip_center()):
            self.remove_requested.emit(self.index)
            event.accept()
            return
        self._dragged = False
        self.body_clicked.emit(self.index)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        self._dragged = True
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and self._dragged:
            self.drag_released.emit(self.index)
        self._dragged = False

    def itemChange(  # noqa: N802 (Qt override)
        self, change: QGraphicsItem.GraphicsItemChange, value: Any
    ) -> Any:
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.moved.emit()
        return super().itemChange(change, value)


class EdgeItem(QGraphicsPathItem):
    """Bezier connector between two NodeItems, updated whenever either end moves."""

    def __init__(self, source: NodeItem, target: NodeItem) -> None:
        super().__init__()
        self.source = source
        self.target = target
        self.setPen(QPen(EDGE_COLOR, EDGE_WIDTH))
        self.setZValue(-1)  # draw under nodes
        source.moved.connect(self.refresh)
        target.moved.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        sp = self.source.pos() + QPointF(NODE_WIDTH, NODE_HEIGHT / 2)
        tp = self.target.pos() + QPointF(0, NODE_HEIGHT / 2)
        dx = max(40, (tp.x() - sp.x()) / 2)
        c1 = QPointF(sp.x() + dx, sp.y())
        c2 = QPointF(tp.x() - dx, tp.y())
        path = QPainterPath(sp)
        path.cubicTo(c1, c2, tp)
        self.setPath(path)


class NodeGraphView(QGraphicsView):
    selection_changed = Signal(int)
    pipeline_changed = Signal()

    def __init__(self, pipeline: Pipeline, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pipeline = pipeline
        self._timings: list[float | None] = []
        self._nodes: list[NodeItem] = []
        self._edges: list[EdgeItem] = []
        self._selected_index = -1

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setBackgroundBrush(QColor("#23272e"))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumHeight(NODE_HEIGHT + 2 * SCENE_MARGIN + 16)

        self.refresh()

    # ------------------------------------------------------------------ public API

    def refresh(self) -> None:
        # Preserve current timings but trim them to the new length.
        del self._timings[len(self._pipeline.nodes):]
        previous_selected = self._selected_index
        self._scene.clear()
        self._nodes.clear()
        self._edges.clear()

        for i, node in enumerate(self._pipeline.nodes):
            item = NodeItem(i, node.spec.name, node.spec.category, node.enabled)
            item.setPos(_layout_x(i), SCENE_MARGIN)
            item.timing = self._timings[i] if i < len(self._timings) else None
            self._scene.addItem(item)
            self._nodes.append(item)

            item.body_clicked.connect(self._on_node_clicked)
            item.enable_toggled.connect(self._on_node_toggled)
            item.remove_requested.connect(self._on_node_remove_requested)
            item.drag_released.connect(self._on_node_drag_released)

        for i in range(len(self._nodes) - 1):
            edge = EdgeItem(self._nodes[i], self._nodes[i + 1])
            self._scene.addItem(edge)
            self._edges.append(edge)

        if self._nodes:
            right = _layout_x(len(self._nodes) - 1) + NODE_WIDTH + SCENE_MARGIN
            self._scene.setSceneRect(0, 0, right, NODE_HEIGHT + 2 * SCENE_MARGIN)
        else:
            self._scene.setSceneRect(0, 0, 200, NODE_HEIGHT + 2 * SCENE_MARGIN)

        new_selection = (
            previous_selected if 0 <= previous_selected < len(self._nodes) else -1
        )
        self._apply_selection(new_selection)

    def select(self, index: int) -> None:
        if not (0 <= index < len(self._nodes)):
            index = -1
        self._apply_selection(index)
        self.selection_changed.emit(index)

    def set_timings(self, timings: Sequence[float | None]) -> None:
        self._timings = list(timings)
        for i, node_item in enumerate(self._nodes):
            node_item.timing = self._timings[i] if i < len(self._timings) else None
            node_item.update()

    def clear_timings(self) -> None:
        self.set_timings([None] * len(self._pipeline.nodes))

    # ------------------------------------------------------------------ internals

    def _apply_selection(self, index: int) -> None:
        self._selected_index = index
        for i, item in enumerate(self._nodes):
            item.selected = i == index
            item.update()

    def _on_node_clicked(self, index: int) -> None:
        self._apply_selection(index)
        self.selection_changed.emit(index)

    def _on_node_toggled(self, index: int) -> None:
        if 0 <= index < len(self._pipeline.nodes):
            self._pipeline.nodes[index].enabled = self._nodes[index].enabled
            self.pipeline_changed.emit()

    def _on_node_remove_requested(self, index: int) -> None:
        if not (0 <= index < len(self._pipeline.nodes)):
            return
        self._pipeline.remove(index)
        # Drop the matching timing so subsequent renders show no stale data.
        if index < len(self._timings):
            del self._timings[index]
        new_selection = (
            self._selected_index
            if self._selected_index < index
            else self._selected_index - 1
        )
        self._selected_index = max(-1, min(new_selection, len(self._pipeline.nodes) - 1))
        self.refresh()
        self.selection_changed.emit(self._selected_index)
        self.pipeline_changed.emit()

    def _on_node_drag_released(self, index: int) -> None:
        # Recompute pipeline order from current x positions of every node.
        order = sorted(range(len(self._nodes)), key=lambda i: self._nodes[i].pos().x())
        if order == list(range(len(self._nodes))):
            # No actual reorder — snap the dragged node back onto its slot.
            self._snap_to_layout()
            return

        # Remap timings before mutating the pipeline.
        if self._timings:
            old_timings = list(self._timings)
            self._timings = [
                old_timings[idx] if 0 <= idx < len(old_timings) else None
                for idx in order
            ]
        self._pipeline.reorder(order)
        # Selection follows the moved node into its new slot.
        if self._selected_index in order:
            self._selected_index = order.index(self._selected_index)
        self.refresh()
        self.pipeline_changed.emit()

    def _snap_to_layout(self) -> None:
        for i, item in enumerate(self._nodes):
            item.setPos(_layout_x(i), SCENE_MARGIN)
