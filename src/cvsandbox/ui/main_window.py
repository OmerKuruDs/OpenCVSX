"""MainWindow — assembles the three panels and wires user actions.

Layout:
    +-----------------------------------------------------+
    | File menu                                           |
    +-----------------+---------------------+-------------+
    | OperationCatalog|     ImageView       | Parameter   |
    | (left)          |     (center)        | Panel       |
    |                 |                     | (right)     |
    +-----------------+---------------------+-------------+
    |              PipelineView (bottom)                  |
    +-----------------------------------------------------+

Live preview is debounced (~120 ms) and runs on a worker QThread so the UI
stays responsive even on large images with expensive operations. Every change
that affects pipeline output (params, ordering, enable, add/remove, new
source image) calls `_request_preview` which schedules the next run.
"""

from __future__ import annotations

import random
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from cvsandbox.core.codegen import generate_python_code
from cvsandbox.core.pipeline import Pipeline, Roi
from cvsandbox.core.registry import get_operation
from cvsandbox.core.serialization import load as load_pipeline
from cvsandbox.core.serialization import save as save_pipeline
from cvsandbox.resources import ICON_PATH
from cvsandbox.ui.code_export_dialog import CodeExportDialog
from cvsandbox.ui.histogram_panel import HistogramPanel
from cvsandbox.ui.image_tools_panel import ImageToolsPanel
from cvsandbox.ui.image_view import ImageViewWidget
from cvsandbox.ui.node_graph_view import NodeGraphView
from cvsandbox.ui.operation_catalog import OperationCatalog
from cvsandbox.ui.parameter_panel import ParameterPanel
from cvsandbox.ui.pipeline_worker import PipelineRequest, PipelineWorker

DEBOUNCE_MS = 120
PREVIEW_MAX_DIM = 1600  # longest-side cap for downscaled-preview mode


def downscale_for_preview(image: np.ndarray, max_dim: int = PREVIEW_MAX_DIM) -> np.ndarray:
    """Shrink `image` so its longest side equals `max_dim`. Returns the input
    unchanged if it is already at-or-below the cap. Uses INTER_AREA, the highest
    quality downscale interpolation in OpenCV."""
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest <= max_dim:
        return image
    scale = max_dim / longest
    new_w = max(1, round(w * scale))
    new_h = max(1, round(h * scale))
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)


class MainWindow(QMainWindow):
    _execute_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("cvsandbox")
        self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.resize(1400, 900)

        self._source_image: np.ndarray | None = None
        self._preview_source: np.ndarray | None = None
        self._downscale_enabled = True
        self._pipeline = Pipeline()
        self._next_request_id = 0
        self._latest_request_id = -1

        self._image_view = ImageViewWidget(self)
        self._catalog = OperationCatalog(self)
        self._param_panel = ParameterPanel(self)
        self._histogram_panel = HistogramPanel(self)
        self._pipeline_view = NodeGraphView(self._pipeline, self)

        right_splitter = QSplitter(Qt.Orientation.Vertical, self)
        right_splitter.addWidget(self._param_panel)
        right_splitter.addWidget(self._histogram_panel)
        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 1)

        right_panel = QWidget(self)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(right_splitter)

        self._catalog.setMinimumWidth(160)
        right_panel.setMinimumWidth(280)
        self._image_view.setMinimumWidth(360)

        # Image view + Image tools sidebar live in one composite widget so the
        # sidebar tracks the image area; the splitter handles the left catalog
        # and right param/histogram column. The sidebar itself is non-resizable
        # (fixed width inside the composite).
        self._image_with_tools = QWidget(self)
        image_with_tools_layout = QHBoxLayout(self._image_with_tools)
        image_with_tools_layout.setContentsMargins(0, 0, 0, 0)
        image_with_tools_layout.setSpacing(0)
        image_with_tools_layout.addWidget(self._image_view, 1)
        # `self._tools_panel` is created in __init__ AFTER the menu builds its
        # QActions; it is parented and inserted in `_install_tools_sidebar`.

        top_splitter = QSplitter(self)
        top_splitter.addWidget(self._catalog)
        top_splitter.addWidget(self._image_with_tools)
        top_splitter.addWidget(right_panel)
        top_splitter.setStretchFactor(0, 0)
        top_splitter.setStretchFactor(1, 1)
        top_splitter.setStretchFactor(2, 0)
        top_splitter.setCollapsible(0, False)
        top_splitter.setCollapsible(1, False)
        top_splitter.setCollapsible(2, False)
        # Initial proportions for a 1400-wide window: catalog 200, image+tools
        # ~860, right column 340. Qt re-honours these against the actual width
        # when the window is first shown.
        top_splitter.setSizes([200, 860, 340])
        self._top_splitter = top_splitter

        central = QWidget(self)
        central_layout = QVBoxLayout(central)
        central_layout.addWidget(top_splitter, 5)
        central_layout.addWidget(self._pipeline_view, 1)
        self.setCentralWidget(central)

        self.setStatusBar(QStatusBar(self))
        self._build_menu()
        self._tools_panel = ImageToolsPanel(
            split_action=self._split_action,
            downscale_action=self._downscale_action,
            select_roi_action=self._select_roi_action,
            clear_roi_action=self._clear_roi_action,
            randomize_paste_action=self._randomize_paste_action,
            clear_paste_action=self._clear_paste_action,
            parent=self,
        )
        self._install_tools_sidebar()
        self._setup_worker()
        self._setup_debouncer()
        self._wire_signals()

    def _install_tools_sidebar(self) -> None:
        """Attach the ImageToolsPanel into the image composite. Called after
        the View-menu actions exist so the panel can bind to them."""
        layout = self._image_with_tools.layout()
        assert layout is not None
        layout.addWidget(self._tools_panel)

    def _build_menu(self) -> None:
        self._build_file_menu()
        self._build_view_menu()

    def _build_file_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        open_image_action = QAction("&Open Image…", self)
        open_image_action.setShortcut(QKeySequence.StandardKey.Open)
        open_image_action.triggered.connect(self._on_open)
        file_menu.addAction(open_image_action)

        file_menu.addSeparator()

        new_pipeline_action = QAction("&New Pipeline", self)
        new_pipeline_action.setShortcut(QKeySequence.StandardKey.New)
        new_pipeline_action.triggered.connect(self._on_new_pipeline)
        file_menu.addAction(new_pipeline_action)

        open_pipeline_action = QAction("Open &Pipeline…", self)
        open_pipeline_action.triggered.connect(self._on_open_pipeline)
        file_menu.addAction(open_pipeline_action)

        save_pipeline_action = QAction("&Save Pipeline As…", self)
        save_pipeline_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_pipeline_action.triggered.connect(self._on_save_pipeline)
        file_menu.addAction(save_pipeline_action)

        file_menu.addSeparator()

        export_code_action = QAction("&Export Code…", self)
        export_code_action.setShortcut("Ctrl+E")
        export_code_action.triggered.connect(self._on_export_code)
        file_menu.addAction(export_code_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _build_view_menu(self) -> None:
        view_menu = self.menuBar().addMenu("&View")

        self._split_action = QAction("&Before/After split", self)
        self._split_action.setCheckable(True)
        self._split_action.setShortcut("Ctrl+B")
        self._split_action.toggled.connect(self._image_view.set_split_enabled)
        view_menu.addAction(self._split_action)

        view_menu.addSeparator()

        self._downscale_action = QAction(
            f"&Downscale large previews (>{PREVIEW_MAX_DIM} px)", self
        )
        self._downscale_action.setCheckable(True)
        self._downscale_action.setChecked(self._downscale_enabled)
        self._downscale_action.toggled.connect(self._on_downscale_toggled)
        view_menu.addAction(self._downscale_action)

        view_menu.addSeparator()

        self._select_roi_action = QAction("Select &ROI", self)
        self._select_roi_action.setCheckable(True)
        self._select_roi_action.setShortcut("Ctrl+R")
        self._select_roi_action.toggled.connect(self._image_view.set_roi_mode)
        view_menu.addAction(self._select_roi_action)

        self._clear_roi_action = QAction("Clea&r ROI", self)
        self._clear_roi_action.triggered.connect(self._on_clear_roi)
        view_menu.addAction(self._clear_roi_action)

        self._randomize_paste_action = QAction("Randomize &paste destination", self)
        self._randomize_paste_action.setShortcut("Ctrl+Shift+R")
        self._randomize_paste_action.triggered.connect(self._on_randomize_paste)
        view_menu.addAction(self._randomize_paste_action)

        self._clear_paste_action = QAction("Clear &paste destination", self)
        self._clear_paste_action.triggered.connect(self._on_clear_paste)
        view_menu.addAction(self._clear_paste_action)

    def _setup_worker(self) -> None:
        self._worker_thread = QThread(self)
        self._worker = PipelineWorker()
        self._worker.moveToThread(self._worker_thread)
        self._execute_requested.connect(self._worker.execute)
        self._worker.result_ready.connect(self._on_worker_result)
        self._worker.failed.connect(self._on_worker_failed)
        self._worker_thread.start()

    def _setup_debouncer(self) -> None:
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self._dispatch_preview)

    def _wire_signals(self) -> None:
        self._catalog.operation_chosen.connect(self._on_operation_chosen)
        self._pipeline_view.selection_changed.connect(self._on_selection_changed)
        self._pipeline_view.pipeline_changed.connect(self._request_preview)
        self._param_panel.params_changed.connect(self._request_preview)
        self._image_view.roi_changed.connect(self._on_roi_drawn)
        self._image_view.paste_destination_changed.connect(self._on_paste_destination_dragged)

    def _on_open(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Open Image",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)",
        )
        if not path:
            return
        image = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if image is None:
            QMessageBox.warning(self, "Open failed", f"Could not read image: {path}")
            return
        self._source_image = image
        self._refresh_preview_source(path_for_status=path)

    def _refresh_preview_source(self, path_for_status: str | None = None) -> None:
        """Rebuild `_preview_source` from `_source_image`, applying downscale
        when enabled. Re-syncs the ROI overlay onto the new preview coordinate
        space and emits a fresh preview request."""
        if self._source_image is None:
            self._preview_source = None
            self._image_view.set_before(None)
            self._image_view.set_roi(None)
            self._request_preview()
            return
        self._preview_source = (
            downscale_for_preview(self._source_image)
            if self._downscale_enabled
            else self._source_image
        )
        self._image_view.set_before(self._preview_source)
        # ROI overlay lives in scene coords (== preview coords). If the preview
        # source changed scale, the overlay needs to be re-projected from the
        # canonical full-source coordinates stored on the pipeline.
        self._image_view.set_roi(self._pipeline_roi_in_preview_coords())
        self._image_view.set_paste_rect(self._pipeline_paste_rect_in_preview_coords())
        if path_for_status is not None:
            self.statusBar().showMessage(self._format_status(path_for_status))
        self._request_preview()

    def _preview_scale(self) -> tuple[float, float]:
        """(sx, sy) factors converting source-coords to preview-coords —
        i.e. `preview = source * sx`. Returns (1, 1) when there is no
        downscaling (preview source == full source)."""
        if self._source_image is None or self._preview_source is None:
            return 1.0, 1.0
        if self._preview_source is self._source_image:
            return 1.0, 1.0
        sh, sw = self._source_image.shape[:2]
        ph, pw = self._preview_source.shape[:2]
        return pw / sw, ph / sh

    def _pipeline_roi_in_preview_coords(self) -> tuple[int, int, int, int] | None:
        if self._pipeline.roi is None:
            return None
        sx, sy = self._preview_scale()
        roi = self._pipeline.roi
        return (
            round(roi.x * sx),
            round(roi.y * sy),
            round(roi.width * sx),
            round(roi.height * sy),
        )

    def _pipeline_paste_in_preview_coords(self) -> tuple[int, int] | None:
        if self._pipeline.roi_paste_to is None:
            return None
        sx, sy = self._preview_scale()
        px, py = self._pipeline.roi_paste_to
        return round(px * sx), round(py * sy)

    def _pipeline_paste_rect_in_preview_coords(self) -> tuple[int, int, int, int] | None:
        """Return the (x, y, w, h) of the paste destination in preview coords,
        suitable for the cyan overlay. None if no paste-to is set."""
        if self._pipeline.roi is None or self._pipeline.roi_paste_to is None:
            return None
        roi_preview = self._pipeline_roi_in_preview_coords()
        paste_xy = self._pipeline_paste_in_preview_coords()
        if roi_preview is None or paste_xy is None:
            return None
        _x, _y, w, h = roi_preview
        px, py = paste_xy
        return px, py, w, h

    def _format_status(self, path: str) -> str:
        assert self._source_image is not None
        sh, sw = self._source_image.shape[:2]
        if self._preview_source is None or self._preview_source is self._source_image:
            return f"Loaded {path}  ·  {sw}x{sh}"
        ph, pw = self._preview_source.shape[:2]
        return f"Loaded {path}  ·  {sw}x{sh}  ·  preview at {pw}x{ph}"

    def _on_downscale_toggled(self, enabled: bool) -> None:
        self._downscale_enabled = enabled
        self._refresh_preview_source()

    def _on_roi_drawn(self, x: int, y: int, w: int, h: int) -> None:
        """User finished drawing a rectangle in ROI mode. Incoming coords are
        in preview-source space; translate to full-source space before storing
        so code export and pipeline.execute stay correct under downscaling."""
        sx, sy = self._preview_scale()
        if sx <= 0 or sy <= 0:
            return
        fx = round(x / sx)
        fy = round(y / sy)
        fw = max(1, round(w / sx))
        fh = max(1, round(h / sy))
        self._pipeline.roi = Roi(x=fx, y=fy, width=fw, height=fh)
        # Re-sync the visual overlay from the canonical pipeline.roi so any
        # rounding stays consistent between preview and saved state.
        self._image_view.set_roi(self._pipeline_roi_in_preview_coords())
        self.statusBar().showMessage(f"ROI set: {fw}x{fh} at ({fx}, {fy})")
        # Exit ROI selection mode automatically — the user just placed one.
        self._select_roi_action.setChecked(False)
        self._request_preview()

    def _on_clear_roi(self) -> None:
        self._pipeline.roi = None
        self._pipeline.roi_paste_to = None
        self._image_view.set_roi(None)
        self._image_view.set_paste_rect(None)
        self._select_roi_action.setChecked(False)
        self.statusBar().showMessage("ROI cleared")
        self._request_preview()

    def _on_randomize_paste(self) -> None:
        roi = self._pipeline.roi
        if roi is None or self._source_image is None:
            self.statusBar().showMessage("Select an ROI first")
            return
        img_h, img_w = self._source_image.shape[:2]
        max_x = max(0, img_w - roi.width)
        max_y = max(0, img_h - roi.height)
        new_x = random.randint(0, max_x) if max_x > 0 else 0
        new_y = random.randint(0, max_y) if max_y > 0 else 0
        self._pipeline.roi_paste_to = (new_x, new_y)
        self._image_view.set_paste_rect(self._pipeline_paste_rect_in_preview_coords())
        self.statusBar().showMessage(f"Paste destination set to ({new_x}, {new_y})")
        self._request_preview()

    def _on_paste_destination_dragged(self, x: int, y: int) -> None:
        """User dragged inside the green ROI to reposition the cyan paste
        destination. Coords are in preview-source space; translate to full
        source coords before storing."""
        if self._pipeline.roi is None:
            return
        sx, sy = self._preview_scale()
        if sx <= 0 or sy <= 0:
            return
        fx = round(x / sx)
        fy = round(y / sy)
        self._pipeline.roi_paste_to = (fx, fy)
        # The image-view's overlay is already at the right place (its drag
        # handler set it eagerly); we just need to re-dispatch the preview.
        self.statusBar().showMessage(f"Paste destination: ({fx}, {fy})")
        self._request_preview()

    def _on_clear_paste(self) -> None:
        if self._pipeline.roi_paste_to is None:
            return
        self._pipeline.roi_paste_to = None
        self._image_view.set_paste_rect(None)
        self.statusBar().showMessage("Paste destination cleared")
        self._request_preview()

    def _on_new_pipeline(self) -> None:
        self._pipeline.clear()
        self._pipeline_view.refresh()
        self._param_panel.set_node(None)
        self._image_view.set_roi(None)
        self._image_view.set_paste_rect(None)
        self._request_preview()

    def _on_open_pipeline(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Open Pipeline",
            str(Path.home()),
            "Pipeline (*.cvpipe.json *.json)",
        )
        if not path:
            return
        try:
            load_pipeline(Path(path), self._pipeline)
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.warning(self, "Load failed", f"Could not load pipeline: {exc}")
            return
        self._pipeline_view.refresh()
        first_node = self._pipeline.nodes[0] if self._pipeline.nodes else None
        self._param_panel.set_node(first_node)
        if first_node is not None:
            self._pipeline_view.select(0)
        # Sync the visual ROI overlay with whatever the loaded pipeline carries.
        self._image_view.set_roi(self._pipeline_roi_in_preview_coords())
        self._image_view.set_paste_rect(self._pipeline_paste_rect_in_preview_coords())
        self.statusBar().showMessage(f"Loaded pipeline {path}")
        self._request_preview()

    def _on_save_pipeline(self) -> None:
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Save Pipeline",
            str(Path.home() / "pipeline.cvpipe.json"),
            "Pipeline (*.cvpipe.json *.json)",
        )
        if not path:
            return
        try:
            save_pipeline(self._pipeline, Path(path))
        except OSError as exc:
            QMessageBox.warning(self, "Save failed", f"Could not save pipeline: {exc}")
            return
        self.statusBar().showMessage(f"Saved pipeline to {path}")

    def _on_export_code(self) -> None:
        try:
            code = generate_python_code(self._pipeline)
        except ValueError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
            return
        dialog = CodeExportDialog(code, self)
        dialog.exec()

    def _on_operation_chosen(self, spec_id: str) -> None:
        spec = get_operation(spec_id)
        node = self._pipeline.add(spec)
        self._pipeline_view.refresh()
        self._pipeline_view.select(len(self._pipeline.nodes) - 1)
        self._param_panel.set_node(node)
        self._request_preview()

    def _on_selection_changed(self, index: int) -> None:
        if 0 <= index < len(self._pipeline.nodes):
            self._param_panel.set_node(self._pipeline.nodes[index])
        else:
            self._param_panel.set_node(None)

    def _request_preview(self) -> None:
        self._debounce.start()  # restarts if already running

    def _dispatch_preview(self) -> None:
        if self._preview_source is None:
            self._image_view.set_image(None)
            self._histogram_panel.clear()
            self._pipeline_view.clear_timings()
            return
        steps = tuple(
            (node.spec.func, dict(node.params)) for node in self._pipeline.nodes if node.enabled
        )
        self._next_request_id += 1
        self._latest_request_id = self._next_request_id
        request = PipelineRequest(
            request_id=self._next_request_id,
            image=self._preview_source,
            steps=steps,
            roi=self._pipeline_roi_in_preview_coords(),
            roi_paste_to=self._pipeline_paste_in_preview_coords(),
        )
        self._execute_requested.emit(request)

    def _on_worker_result(self, request_id: int, image: object, timings: object) -> None:
        if request_id != self._latest_request_id:
            return  # a newer request has already superseded this one
        if not isinstance(image, np.ndarray):
            return
        self._image_view.set_image(image)
        self._histogram_panel.set_image(image)
        self._apply_timings(timings)

    def _apply_timings(self, timings: object) -> None:
        """Map an enabled-only timings tuple back to per-pipeline-node timings."""
        if not isinstance(timings, tuple):
            return
        per_node: list[float | None] = []
        iterator = iter(timings)
        for node in self._pipeline.nodes:
            if node.enabled:
                per_node.append(next(iterator, None))
            else:
                per_node.append(None)
        self._pipeline_view.set_timings(per_node)

    def _on_worker_failed(self, request_id: int, message: str) -> None:
        if request_id != self._latest_request_id:
            return
        self.statusBar().showMessage(f"Pipeline error: {message}")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt override)
        self._worker_thread.quit()
        self._worker_thread.wait(2000)
        super().closeEvent(event)
