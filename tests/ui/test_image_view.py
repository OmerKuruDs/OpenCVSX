from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication

from cvsandbox.ui.image_view import MAX_ZOOM, ZOOM_STEP, ImageViewWidget


def _rgb(w: int = 200, h: int = 100) -> np.ndarray:
    return np.full((h, w, 3), 80, dtype=np.uint8)


def _wheel(widget: ImageViewWidget, delta: int) -> None:
    pos = widget.viewport().rect().center()
    event = QWheelEvent(
        pos,
        widget.mapToGlobal(pos),
        QPoint(0, 0),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    widget.wheelEvent(event)


def _double_click(widget: ImageViewWidget, button: Qt.MouseButton = Qt.MouseButton.LeftButton) -> None:
    pos = widget.viewport().rect().center()
    event = QMouseEvent(
        QEvent.Type.MouseButtonDblClick,
        pos,
        widget.mapToGlobal(pos),
        button,
        button,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mouseDoubleClickEvent(event)


@pytest.fixture
def view(qapp: QApplication) -> ImageViewWidget:
    widget = ImageViewWidget()
    widget.resize(400, 300)
    widget.show()
    qapp.processEvents()
    return widget


def test_set_image_fits_view(view: ImageViewWidget) -> None:
    view.set_image(_rgb())
    assert view._user_zoomed is False
    # Fit-scale should equal current transform scale.
    assert view._current_scale() == pytest.approx(view._fit_scale(), rel=0.05)


def test_wheel_zooms_in_and_marks_user_zoomed(view: ImageViewWidget) -> None:
    view.set_image(_rgb())
    fit_scale = view._current_scale()
    _wheel(view, 120)  # one notch up
    assert view._user_zoomed is True
    assert view._current_scale() == pytest.approx(fit_scale * ZOOM_STEP, rel=1e-3)
    # fit_scale itself has the ~1% scrollbar-reservation skew; the ratio is exact.


def test_zoom_is_clamped_to_fit_minimum(view: ImageViewWidget) -> None:
    view.set_image(_rgb())
    # Zoom in once so we have headroom to zoom out.
    _wheel(view, 120)
    assert view._user_zoomed is True
    # Now spam zoom-outs; should clamp at fit_scale and clear user_zoomed.
    for _ in range(20):
        _wheel(view, -120)
    assert view._current_scale() == pytest.approx(view._fit_scale(), rel=0.05)
    assert view._user_zoomed is False


def test_zoom_is_clamped_to_max(view: ImageViewWidget) -> None:
    view.set_image(_rgb())
    for _ in range(100):
        _wheel(view, 120)
    assert view._current_scale() <= MAX_ZOOM + 1e-6


def test_double_click_resets_view(view: ImageViewWidget) -> None:
    view.set_image(_rgb())
    _wheel(view, 120)
    _wheel(view, 120)
    assert view._user_zoomed is True
    _double_click(view)
    assert view._user_zoomed is False
    assert view._current_scale() == pytest.approx(view._fit_scale(), rel=0.05)


def test_same_size_image_swap_preserves_zoom(view: ImageViewWidget) -> None:
    view.set_image(_rgb())
    _wheel(view, 120)
    scale_before = view._current_scale()
    # Simulate parameter tuning: same-size new image arrives.
    view.set_image(_rgb())
    assert view._user_zoomed is True
    assert view._current_scale() == pytest.approx(scale_before, rel=1e-3)


def test_different_size_image_swap_refits(view: ImageViewWidget) -> None:
    view.set_image(_rgb())
    _wheel(view, 120)
    assert view._user_zoomed is True
    # E.g. a Resize op produced a different shape.
    view.set_image(_rgb(w=80, h=40))
    assert view._user_zoomed is False
    assert view._current_scale() == pytest.approx(view._fit_scale(), rel=0.05)


def test_clear_resets_state(view: ImageViewWidget) -> None:
    view.set_image(_rgb())
    _wheel(view, 120)
    view.set_image(None)
    assert view._pixmap_item is None
    assert view._image_size is None
    assert view._user_zoomed is False
