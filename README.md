<div align="center">

<img src="src/cvsandbox/resources/icon.svg" alt="cvsandbox" width="280" />

# cvsandbox

**An interactive OpenCV playground. Chain image operations, tune every parameter with live preview, and export the result as ready-to-run Python.**

[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![PySide6](https://img.shields.io/badge/PySide6-6.6%2B-41CD52)](https://doc.qt.io/qtforpython/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.9%2B-5C3EE8?logo=opencv&logoColor=white)](https://opencv.org/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-281%20passing-success)](tests/)

</div>

---

## Overview

cvsandbox is a desktop tool for **finding the right OpenCV pipeline by iterating on parameters in real time.** Load an image, stack operations (Gaussian blur → adaptive threshold → morphology → find contours, ...), tweak every parameter with auto-generated sliders, then export the entire pipeline as a self-contained Python function whose output matches the live preview byte-for-byte.

Built for engineers who currently iterate on `cv2.GaussianBlur(img, (5, 5), 0)` calls in Jupyter cells, one parameter at a time.

## Highlights

- **Live preview** with a 120 ms debounced worker thread — no UI freezes on large images.
- **27 built-in operations** across 8 categories (filtering, threshold, morphology, edge, color, geometric, analysis, composite).
- **Auto-generated UI** — every slider, spinner, and dropdown is derived from a declarative `Parameter` spec. Adding an operation does not touch UI code.
- **Pipeline persistence** — save and load pipelines as `.cvpipe.json`.
- **Code export** — emit a stand-alone `process(img)` Python function whose output is verified equal to the live pipeline.
- **Before / after compare** — toggle a side-by-side view to see exactly what the pipeline does (`Ctrl+B`).
- **Histogram panel** — per-channel intensity overlay refreshes with every preview.
- **Zoom & pan** — cursor-anchored mouse-wheel zoom, drag-to-pan, double-click to refit.
- **Per-operation timing** — each pipeline row shows how long that step took on the last preview run.
- **Export results** — `Save Processed Image…` runs the full-res pipeline and writes the result to disk; `Record Video…` (active during camera / video capture) streams each processed frame into a VideoWriter.
- **High-bit-depth inputs** — 16-bit and floating-point TIFFs / PNGs load through a normalising reader; their dynamic range is rescaled to uint8 instead of clipped, so the pipeline (and your eyes) see the actual content rather than a sheet of white.
- **In-app Operation Guide** — `Help → Operation Guide…` (or `F1`) opens a non-modal window with rich documentation for **the whole app**: an "App features" section explains every menu item, panel, and concept (Open Image, the pipeline editor, the histogram graph, ROI, downscaling, saving, batch, …), and an "Operations" section documents every op (what it does, what each parameter means, where it shines, common pairings).
- **Fast preview on huge images** — sources larger than 1600 px on their longest side are auto-downscaled for the live preview loop only; code export stays full-resolution.
- **Region of interest (ROI)** — draw a rectangle on the image (`Ctrl+R`) and the pipeline runs only inside that region; drag inside the rectangle to drop the processed crop somewhere else on the canvas. Exported code reproduces the same crop / paste-back behavior.
- **Node-graph pipeline view** — the bottom strip renders the pipeline as a horizontal chain of nodes with bezier connectors. Drag a node sideways to reorder; click the green chip to enable/disable; click the X chip to remove.

## Quick start

```bash
git clone https://github.com/OmerKuru/cvsandbox.git
cd cvsandbox
python -m venv .venv
.venv\Scripts\activate              # Windows PowerShell
# source .venv/bin/activate         # Linux / macOS
pip install -e ".[dev]"
pytest                              # 281 tests, all passing
cvsandbox                           # launch the GUI
```

To inspect the registered operation catalog without launching the UI:

```bash
cvsandbox --list
```

## Architecture

```
src/cvsandbox/
├── core/                  # Domain primitives
│   ├── operation.py       # OperationSpec + Parameter dataclasses
│   ├── pipeline.py        # Pipeline + PipelineNode
│   ├── registry.py        # Global operation registry
│   ├── codegen.py         # Pipeline → Python source generation
│   ├── serialization.py   # Load / save pipelines as JSON
│   ├── graph.py           # DAG data model + topological execution (Phase 2a)
│   ├── video.py           # VideoSource — thin wrapper over cv2.VideoCapture
│   ├── batch.py           # Folder-level pipeline application with cancellation
│   ├── image_io.py        # Robust read_image() that normalises 16-bit / float inputs
│   └── op_docs.py         # In-app help: feature topics + per-op documentation
├── operations/            # Built-in OpenCV operations (one module per category)
├── resources/             # Bundled assets (icon)
└── ui/                    # PySide6 widgets
    ├── app.py             # QApplication bootstrap
    ├── main_window.py     # Window assembly + menus + worker wiring
    ├── image_view.py      # Zoom / pan + before / after split + ROI overlays
    ├── image_tools_panel.py  # Sidebar of toggles next to the image view
    ├── histogram_panel.py
    ├── operation_catalog.py
    ├── parameter_panel.py
    ├── parameter_widgets.py
    ├── node_graph_view.py # Visual node-chain replacement for the old list view
    ├── pipeline_worker.py # Background thread for preview
    └── code_export_dialog.py
```

Each operation is a small declarative `OperationSpec`: an id, a parameter list, a pure `(image, **params) -> image` function, and a `code_export` callable that emits matching Python. Pipelines are an ordered list of nodes; each node binds a spec to concrete parameter values. The UI introspects the parameter spec to auto-build inputs — adding a new operation does not require any UI code.

## Built-in operations

| Category    | Operations                                                              |
| ----------- | ----------------------------------------------------------------------- |
| Filtering   | Gaussian Blur, Median Blur, Bilateral Filter, NL-Means Denoise          |
| Threshold   | Binary, Otsu, Adaptive                                                  |
| Morphology  | Erode, Dilate, Open, Close                                              |
| Edge        | Canny, Sobel, Laplacian                                                 |
| Color       | To Grayscale, To HSV, Invert, Extract Channel, CLAHE, HSV In-Range Mask |
| Geometric   | Resize, Rotate, Flip                                                    |
| Analysis    | Find Contours                                                           |
| Composite   | Blend, Apply Mask, Difference (multi-input — wire the second input by dragging from any node's output port) |

## Adding a new operation

See [CONTRIBUTING.md](CONTRIBUTING.md#adding-a-new-operation) for the full recipe. Short version:

1. Add a function plus `OperationSpec` in `src/cvsandbox/operations/<category>.py`.
2. Register the module in `src/cvsandbox/operations/__init__.py`.
3. Add a test in `tests/operations/`.

The catalog, parameter panel, and code exporter all pick up the new spec automatically.

## Roadmap

**v0.1 — Core scaffold.** Registry, pipeline, serialization, CI. *Done.*

**v0.2 — Interactive MVP**
- [x] PySide6 main window with image view, pipeline list, and parameter panel
- [x] Auto-generated sliders / inputs from parameter spec
- [x] Debounced preview with a worker thread
- [x] Zoom and pan in the image view
- [x] 24 built-in operations
- [x] Downscaling preview mode for very large images

**v0.3 — Power user**
- [x] Pipeline save / load (`.cvpipe.json`)
- [x] Code export to stand-alone Python
- [x] Histogram panel
- [x] Before / after split view
- [x] Per-operation timing HUD
- [x] Drag-and-drop pipeline reordering

**v1.0 and beyond**
- [x] ROI selection — pipeline operates only inside a user-drawn rectangle
- [x] Node-graph pipeline view (visual layer; underlying model still linear)
- [x] DAG core (Phase 2a) — `Graph`, port-typed `GraphNode`/`GraphEdge`, Kahn topological execution; cycle detection; branching, merging, multi-input and multi-output ops all execute correctly. `OperationSpec` carries `input_ports` and `output_ports`. Built-in ops keep single-input / single-output defaults.
- [x] DAG UI (Phase 2b) — `Pipeline` is now a thin facade over `Graph`; drag-to-connect wires an output port into any compatible input port; drag-to-disconnect lifts a connected wire so it can be re-routed or released to detach; cycles, duplicate connections, and unknown ports are silently rejected. Three new multi-input ops in the Composite category: Blend, Apply Mask, Difference.
- [x] Explicit Source node (Phase 2c) — every pipeline starts with a pinned `Source` node that emits the loaded image. Multi-input ops can drag-connect their second input directly from `Source.image` (or any other node's output) without relying on the hidden "fallback to source" rule. The Source node is non-removable, non-toggleable, and stays at the left edge of the layout.
- [x] Free node positioning + serialization v2 (Phase 2d) — drag a node anywhere to set its scene-space position; the coordinate persists on `GraphNode.position` and is restored on refresh. `.cvpipe.json` v2 stores the full graph (nodes with positions, edges with port names, ROI / paste-destination). v1 files auto-migrate on load by replaying their linear node list through `Pipeline.add`.
- [x] DAG codegen (Phase 2e) — `code_export` callables now take `(params, input_vars, output_var)` and the generator walks the graph in topological order, giving every node its own `step_N` variable. Multi-input ops resolve each port to the upstream node's output variable, so branching, merging, and fan-out all export to runnable Python whose result matches the live pipeline exactly. `_coerce_to_match` is auto-emitted whenever a composite op or ROI splice needs it.
- [x] Video / camera input (Phase 3a) — `File → Open Camera` / `File → Open Video…` streams frames through the live pipeline. A `VideoFeedController` drives a QTimer at source FPS and gates each frame on the worker being free, so heavy pipelines just slow the displayed framerate instead of queueing. All existing features (ROI, downscaling, histogram, timing HUD, multi-input nodes) operate on each frame.
- [x] Batch processing (Phase 3b) — `File → Bulk Export Dataset…` (formerly "Batch Process Folder") opens a modal that takes input / output folders, an output suffix, and an overwrite flag. The current pipeline is applied to every image in the input folder on a background thread; progress, per-file errors, and cancellation all surface live in the dialog.
- [x] Dataset gallery (Phase 3f) — `File → Open Dataset…` (`Ctrl+D`) opens a non-modal grid of thumbnails for every image in a folder; clicking a thumbnail loads that image as the live source so you can tune the pipeline per-image and `Save Image` individual results. Pairs naturally with Bulk Export for one-pipeline-fits-all runs.

## License

Apache-2.0 — see [LICENSE](LICENSE).
