from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from cvsandbox.core.operation import OperationSpec, Parameter
from cvsandbox.core.pipeline import Pipeline
from cvsandbox.ui.node_graph_view import (
    NODE_GAP,
    NODE_WIDTH,
    SCENE_MARGIN,
    NodeGraphView,
    _layout_x,
    format_duration,
)


def _spec(spec_id: str, name: str, category: str = "Test") -> OperationSpec:
    return OperationSpec(
        id=spec_id,
        name=name,
        category=category,
        description="",
        parameters=(Parameter(name="x", kind="int", default=0, min=0, max=10),),
        func=lambda image, x: image,
    )


@pytest.fixture
def view(qapp: QApplication) -> NodeGraphView:
    pipeline = Pipeline()
    pipeline.add(_spec("test.a", "Alpha"))
    pipeline.add(_spec("test.b", "Beta"))
    pipeline.add(_spec("test.c", "Gamma"))
    widget = NodeGraphView(pipeline)
    widget.resize(800, 200)
    return widget


# --------------------------------------------------------------- format_duration


def test_format_duration_microseconds() -> None:
    assert format_duration(0.000_25) == "250 µs"


def test_format_duration_milliseconds() -> None:
    assert format_duration(0.012_3) == "12.3 ms"


def test_format_duration_seconds() -> None:
    assert format_duration(1.234) == "1.23 s"


# -------------------------------------------------------------------- structure


def test_refresh_builds_node_per_pipeline_entry(view: NodeGraphView) -> None:
    assert len(view._nodes) == 3
    assert [n.title for n in view._nodes] == ["Alpha", "Beta", "Gamma"]


def test_refresh_lays_out_horizontally(view: NodeGraphView) -> None:
    xs = [n.pos().x() for n in view._nodes]
    assert xs == [_layout_x(0), _layout_x(1), _layout_x(2)]
    # Spacing is exactly NODE_WIDTH + NODE_GAP between neighbours.
    assert xs[1] - xs[0] == NODE_WIDTH + NODE_GAP


def test_refresh_creates_one_edge_between_each_consecutive_pair(view: NodeGraphView) -> None:
    assert len(view._edges) == 2  # 3 nodes -> 2 edges


def test_empty_pipeline_has_no_nodes_and_no_edges(qapp: QApplication) -> None:
    empty = NodeGraphView(Pipeline())
    assert empty._nodes == []
    assert empty._edges == []


# -------------------------------------------------------------------- selection


def test_select_emits_signal_and_marks_node(view: NodeGraphView, qapp: QApplication) -> None:
    received: list[int] = []
    view.selection_changed.connect(received.append)
    view.select(1)
    qapp.processEvents()
    assert received == [1]
    assert view._nodes[1].selected is True
    assert view._nodes[0].selected is False


def test_clicking_node_body_emits_selection(view: NodeGraphView, qapp: QApplication) -> None:
    received: list[int] = []
    view.selection_changed.connect(received.append)
    view._nodes[2].body_clicked.emit(2)
    qapp.processEvents()
    assert received == [2]
    assert view._nodes[2].selected is True


# ---------------------------------------------------------------- enabled chip


def test_toggle_chip_flips_enabled_state(view: NodeGraphView, qapp: QApplication) -> None:
    fired: list[None] = []
    view.pipeline_changed.connect(lambda: fired.append(None))

    view._nodes[1].enabled = False  # simulate user clicking the chip
    view._nodes[1].enable_toggled.emit(1)
    qapp.processEvents()

    assert view._pipeline.nodes[1].enabled is False
    assert len(fired) == 1


# ---------------------------------------------------------------- remove chip


def test_remove_chip_drops_node_and_refreshes(view: NodeGraphView, qapp: QApplication) -> None:
    fired: list[None] = []
    view.pipeline_changed.connect(lambda: fired.append(None))

    view._nodes[1].remove_requested.emit(1)
    qapp.processEvents()

    assert len(view._pipeline.nodes) == 2
    assert [n.spec.name for n in view._pipeline.nodes] == ["Alpha", "Gamma"]
    assert len(view._nodes) == 2
    assert len(view._edges) == 1
    assert fired == [None]


# ---------------------------------------------------------------- drag reorder


def _drag_node(view: NodeGraphView, index: int, new_x: float) -> None:
    """Move the node to a new x-position and trigger the drag-release path."""
    view._nodes[index].setPos(QPointF(new_x, SCENE_MARGIN))
    view._nodes[index].drag_released.emit(index)


def test_drag_reorders_pipeline_by_x_position(view: NodeGraphView, qapp: QApplication) -> None:
    fired: list[None] = []
    view.pipeline_changed.connect(lambda: fired.append(None))

    # Move Alpha (index 0) past Gamma (index 2) by setting a very large x.
    _drag_node(view, 0, _layout_x(2) + 200)
    qapp.processEvents()

    assert [n.spec.name for n in view._pipeline.nodes] == ["Beta", "Gamma", "Alpha"]
    assert fired == [None]
    # After reorder, the visual nodes are re-laid-out from scratch.
    assert [n.title for n in view._nodes] == ["Beta", "Gamma", "Alpha"]


def test_drag_without_reorder_snaps_node_back_to_slot(view: NodeGraphView) -> None:
    original_x = view._nodes[1].pos().x()
    # Nudge Beta a little but not past its neighbours.
    view._nodes[1].setPos(QPointF(original_x + 10, SCENE_MARGIN))
    view._nodes[1].drag_released.emit(1)
    assert view._nodes[1].pos().x() == _layout_x(1)


def test_drag_remaps_timings(view: NodeGraphView, qapp: QApplication) -> None:
    view.set_timings([0.001, 0.002, 0.003])
    _drag_node(view, 0, _layout_x(2) + 200)
    qapp.processEvents()
    # Order is now [Beta, Gamma, Alpha]; timings should follow accordingly.
    assert view._nodes[0].timing == pytest.approx(0.002)
    assert view._nodes[1].timing == pytest.approx(0.003)
    assert view._nodes[2].timing == pytest.approx(0.001)


# --------------------------------------------------------------------- timings


def test_set_timings_updates_each_node(view: NodeGraphView) -> None:
    view.set_timings([0.001, None, 0.010])
    assert view._nodes[0].timing == pytest.approx(0.001)
    assert view._nodes[1].timing is None
    assert view._nodes[2].timing == pytest.approx(0.010)


def test_clear_timings_resets_all(view: NodeGraphView) -> None:
    view.set_timings([0.001, 0.002, 0.003])
    view.clear_timings()
    assert all(n.timing is None for n in view._nodes)


def test_refresh_preserves_last_known_timings(view: NodeGraphView) -> None:
    view.set_timings([0.001, 0.002, 0.003])
    view.refresh()
    assert view._nodes[0].timing == pytest.approx(0.001)
    assert view._nodes[2].timing == pytest.approx(0.003)
