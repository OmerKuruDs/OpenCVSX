"""ImageView — display an OpenCV image (np.ndarray) in a QGraphicsView.

OpenCV gives us BGR uint8 arrays; Qt wants RGB (or grayscale). We convert at the
boundary and keep the np.ndarray as the source of truth — the widget is a thin
view, no image state lives here beyond the current QPixmap.

Interactions:
    * mouse wheel               — zoom at cursor (cursor stays anchored)
    * left-mouse drag           — pan
    * double-click              — reset to fit-in-view

If the user has manually zoomed/panned, that state is preserved across
`set_image` calls **as long as the new image has the same dimensions** (the
common case during parameter tuning). Different dimensions or no zoom history
re-fit the view.
"""

from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QMouseEvent, QPixmap, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView, QWidget

ZOOM_STEP = 1.15
MAX_ZOOM = 40.0


class ImageViewWidget(QGraphicsView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._image_size: tuple[int, int] | None = None  # (w, h)
        self._user_zoomed = False

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setBackgroundBrush(Qt.GlobalColor.darkGray)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def clear(self) -> None:
        self._scene.clear()
        self._pixmap_item = None
        self._image_size = None
        self._user_zoomed = False
        self.resetTransform()

    def set_image(self, image: np.ndarray | None) -> None:
        if image is None:
            self.clear()
            return
        pixmap = _ndarray_to_qpixmap(image)
        new_size = (pixmap.width(), pixmap.height())
        preserve_view = self._user_zoomed and self._image_size == new_size

        self._scene.clear()
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(pixmap.rect().toRectF())
        self._image_size = new_size

        if not preserve_view:
            self._user_zoomed = False
            self._fit()

    def reset_view(self) -> None:
        self._user_zoomed = False
        self._fit()

    # ------------------------------------------------------------------ events

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 (Qt override)
        if self._pixmap_item is None:
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = ZOOM_STEP if delta > 0 else 1.0 / ZOOM_STEP
        self._apply_zoom(factor)
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self.reset_view()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        if not self._user_zoomed:
            self._fit()

    # ------------------------------------------------------------------ internals

    def _fit(self) -> None:
        if self._pixmap_item is None:
            return
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def _current_scale(self) -> float:
        # Uniform scale: m11 (== m22 for our transforms) is enough.
        return float(self.transform().m11())

    def _fit_scale(self) -> float:
        if self._pixmap_item is None or self._image_size is None:
            return 1.0
        viewport = self.viewport().size()
        if viewport.width() <= 0 or viewport.height() <= 0:
            return 1.0
        w, h = self._image_size
        return min(viewport.width() / w, viewport.height() / h)

    def _apply_zoom(self, factor: float) -> None:
        current = self._current_scale()
        target = current * factor
        min_scale = self._fit_scale()
        if target < min_scale:
            target = min_scale
            factor = target / current if current else 1.0
            self._user_zoomed = False
        elif target > MAX_ZOOM:
            factor = MAX_ZOOM / current if current else 1.0
        else:
            self._user_zoomed = True
        self.scale(factor, factor)


def _ndarray_to_qpixmap(image: np.ndarray) -> QPixmap:
    """Convert a BGR/BGRA/grayscale uint8 ndarray to a QPixmap (RGB888 / Grayscale8).

    `cv2.cvtColor` allocates a new array, so the QImage references memory we own;
    we then `.copy()` the QImage to detach it from the ndarray's lifetime.
    """
    if image.dtype != np.uint8:
        image = np.clip(image, 0, 255).astype(np.uint8)

    if image.ndim == 2:
        height, width = image.shape
        qimage = QImage(image.data, width, height, width, QImage.Format.Format_Grayscale8)
        return QPixmap.fromImage(qimage.copy())

    if image.ndim == 3:
        height, width, channels = image.shape
        if channels == 4:
            rgba = cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
            qimage = QImage(rgba.data, width, height, 4 * width, QImage.Format.Format_RGBA8888)
        else:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            qimage = QImage(rgb.data, width, height, 3 * width, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimage.copy())

    raise ValueError(f"Unsupported image shape: {image.shape}")
