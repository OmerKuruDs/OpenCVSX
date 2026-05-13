"""Long-form documentation for the in-app help panel.

Two dictionaries:

* `FEATURE_DOCS` — entries for the app itself (menu items, panels, concepts).
* `OP_DOCS` — entries for every registered operation.

Each entry is HTML (Qt's QTextBrowser subset — `<h2>`, `<h3>`, `<p>`, `<ul>`,
`<li>`, `<b>`, `<i>`, `<code>`). Content is intentionally beginner-friendly:
what the thing does, when to reach for it, and which other features it
composes well with. Keep entries focused — the on-screen panel is for
orientation, not a textbook.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureTopic:
    key: str
    title: str
    body: str


FEATURE_TOPICS: tuple[FeatureTopic, ...] = (
    FeatureTopic(
        key="getting_started",
        title="Getting started",
        body="""
<h2>Getting started</h2>
<p>cvsandbox is an interactive playground for OpenCV pipelines. The typical
workflow is:</p>
<ul>
  <li><b>1. Load something to look at.</b> Use <code>File &rarr; Open
      Image</code>, <code>Open Camera</code>, or <code>Open Video</code> —
      or the matching buttons in the action bar below the image.</li>
  <li><b>2. Add operations.</b> Click an op in the left catalog. It joins
      the bottom node-graph strip, automatically wired to the previous step.</li>
  <li><b>3. Tune the parameters.</b> Click a node and edit its sliders /
      dropdowns in the right panel. The image and histogram update live.</li>
  <li><b>4. Save the result.</b> The teal <b>Save Image</b> button below the
      image writes the full-resolution output to disk. For live capture,
      <b>Record Video</b> streams each processed frame to an mp4 / avi.</li>
</ul>
<p>Two further power features live alongside: <b>Export Code</b> emits a
self-contained Python function reproducing the pipeline, and <b>Batch
Process Folder</b> applies it to every image in a folder.</p>
""",
    ),
    FeatureTopic(
        key="opening_files",
        title="Opening images, video, and camera",
        body="""
<h2>Opening files</h2>
<h3>Open Image</h3>
<p>Loads a single image file. Supported formats include PNG, JPG, BMP,
TIFF, and WebP — anything OpenCV's <code>imread</code> understands.</p>
<p><b>16-bit and floating-point TIFFs</b> are handled specially: their
dynamic range is rescaled to uint8 instead of clipped, so high-bit-depth
microscopy / scanner / HDR exports display correctly instead of saturating
to white.</p>
<h3>Open Camera</h3>
<p>Starts streaming from the default webcam (device index 0). Each frame
flows through the live pipeline; histograms and timing update in real time.
Use <b>Stop Capture</b> to release the device.</p>
<h3>Open Video</h3>
<p>Plays back a video file (mp4, mov, avi, mkv, webm). The frame rate is
gated by the heaviest step in the pipeline — if the pipeline takes 80 ms,
the display tops out near 12 fps regardless of the source's native rate.
This keeps the worker thread from queueing endless backlog.</p>
""",
    ),
    FeatureTopic(
        key="pipeline_editor",
        title="The pipeline / node graph",
        body="""
<h2>Pipeline editor</h2>
<p>The strip at the bottom of the window is your pipeline rendered as a
node graph. Under the hood it is a true DAG (directed acyclic graph), so
each op can in principle take inputs from multiple upstream nodes and feed
multiple downstream consumers. For most workflows the chain you build by
clicking operations is enough.</p>
<h3>Anatomy of a node</h3>
<ul>
  <li><b>Title</b> — the op name. The coloured strip on the left encodes
      its category.</li>
  <li><b>Ports</b> — circles on the left (inputs) and right (output). The
      first node automatically wires from the Source; multi-input ops have
      one circle per port, stacked vertically.</li>
  <li><b>Green / grey chip</b> (top-right region) toggles the node on or
      off; a disabled node passes its input through untouched.</li>
  <li><b>X chip</b> removes the node from the pipeline.</li>
  <li><b>Timing badge</b> beneath the title shows how long the last preview
      run spent on that step.</li>
</ul>
<h3>Wiring extra connections</h3>
<p>Drag from an output port onto another node's input port to add an edge —
useful for feeding a Blend / Apply Mask / Difference op's second input.
Drag from a connected input port to detach or re-route. The system rejects
edges that would form cycles, duplicate connections, or use unknown ports.</p>
<h3>Repositioning</h3>
<p>Drag a node body to move it anywhere on the canvas. The position
persists through refreshes and round-trips through <b>Save Pipeline</b>.
The Source node is also free to move.</p>
""",
    ),
    FeatureTopic(
        key="image_view",
        title="Image view (zoom, pan, split)",
        body="""
<h2>Image view</h2>
<p>The big central panel where the pipeline output is rendered.</p>
<h3>Zoom and pan</h3>
<ul>
  <li><b>Mouse wheel</b> zooms in / out at the cursor location.</li>
  <li><b>Left-drag</b> pans.</li>
  <li><b>Double-click</b> resets to fit-in-view.</li>
</ul>
<p>The view remembers your zoom across parameter changes as long as the
output shape stays the same — only operations that change image dimensions
(e.g. Resize) reset the fit.</p>
<h3>Before / After split (Ctrl+B)</h3>
<p>Toggle a side-by-side comparison: the original image on the left, the
pipeline output on the right. Heights are normalised; mixed grayscale and
BGR pairs are unified into BGR for a sensible display. Tools that overlay
on a single image (ROI rectangle, paste-destination rectangle) are hidden
in split mode because the composite has different coordinates.</p>
""",
    ),
    FeatureTopic(
        key="histogram",
        title="Histogram panel",
        body="""
<h2>Histogram panel</h2>
<p>The small graph at the bottom-right shows the <b>distribution of pixel
intensities</b> in the current pipeline output. X axis is 0-255; Y axis is
how many pixels hit each value (normalised so the tallest bar reaches the
top).</p>
<h3>How to read it</h3>
<ul>
  <li><b>Pile on the left</b> &rarr; image is dark; shadow detail likely
      hidden.</li>
  <li><b>Pile on the right</b> &rarr; image is bright; highlights may be
      clipped (lost detail).</li>
  <li><b>Narrow central spike</b> &rarr; low contrast (fog / haze).</li>
  <li><b>Wide, even spread</b> &rarr; rich tonal range.</li>
  <li><b>Two sharp bars at 0 and 255 only</b> &rarr; healthy binary output
      (Canny, Otsu, In-Range Mask).</li>
</ul>
<h3>Channel overlays</h3>
<p>Single-channel inputs show one grey curve. BGR inputs draw three
translucent curves (blue, green, red) over the same axis so you can spot
colour imbalances — a sun-tinted photo would show the red peak far to the
right of the blue peak.</p>
<h3>Practical use</h3>
<p>Pick threshold values by looking for valleys in the histogram between
two peaks. When tuning CLAHE, watch the histogram broaden as contrast
amplifies. After Canny, confirm the output really is binary (two spikes,
nothing in between) — anything else means the chain isn't producing a clean
edge map.</p>
""",
    ),
    FeatureTopic(
        key="tools_panel",
        title="Image tools sidebar",
        body="""
<h2>Image tools sidebar</h2>
<p>The narrow column of grouped buttons immediately right of the image
mirrors the View menu. Buttons stay in sync with menu state — toggling one
updates the other.</p>
<h3>View</h3>
<ul>
  <li><b>Before/After split</b> (Ctrl+B) — see the original and the
      pipeline output side by side.</li>
  <li><b>Downscale large previews</b> — resize inputs longer than 1600 px
      for the preview loop. See the "Downscaling preview mode" topic.</li>
</ul>
<h3>ROI</h3>
<ul>
  <li><b>Select ROI</b> (Ctrl+R) — enter draw mode and rubber-band a
      rectangle.</li>
  <li><b>Clear ROI</b> — drop the region; pipeline goes back to operating
      on the full image.</li>
</ul>
<h3>Paste destination</h3>
<ul>
  <li><b>Randomize paste destination</b> (Ctrl+Shift+R) — drop the
      processed ROI crop onto a random spot inside the image.</li>
  <li><b>Clear paste destination</b> — splice the processed crop back at
      the ROI's own position (default).</li>
</ul>
""",
    ),
    FeatureTopic(
        key="roi",
        title="Region of interest (ROI)",
        body="""
<h2>Region of interest</h2>
<p>Run the pipeline only inside a user-drawn rectangle, leaving the rest of
the image untouched. Useful for tuning a chain against one area before
deciding to apply it globally, or for compositing transformations into a
specific patch.</p>
<h3>Drawing</h3>
<p>Activate <b>Select ROI</b> (Ctrl+R) — the cursor becomes a cross. Click
and drag on the image to rubber-band a rectangle; release to commit. A
green dashed outline marks the region. The pipeline immediately switches
to ROI-only mode and updates the preview.</p>
<h3>Cut and paste somewhere else</h3>
<p>Once an ROI is drawn, dragging inside the green rectangle does
<i>not</i> move the source — it sets the <b>paste destination</b>. A cyan
dotted rectangle follows your cursor; releasing it drops the processed
crop at that spot. The original ROI area stays as-is, so you can stamp
the result wherever you like (or run the menu's "Randomize paste
destination" for a quick random placement).</p>
<h3>Channel and shape mismatches</h3>
<p>If the pipeline produces grayscale output while the source is BGR (or
vice-versa), the channel layout is automatically coerced so the splice
succeeds. Pipelines that change image dimensions (e.g. Resize) skip the
splice and leave the source untouched — the preview shows the original
image so it's obvious the ROI couldn't be applied.</p>
""",
    ),
    FeatureTopic(
        key="downscale_preview",
        title="Downscaling preview mode",
        body="""
<h2>Downscaling preview mode</h2>
<p>Live preview redraws on every parameter change. For high-resolution
inputs (4K photographs, drone footage) that becomes painful — a single
Bilateral pass on a 4032 x 3024 image can take seconds.</p>
<p>The View sidebar's <b>Downscale large previews</b> toggle (on by
default) resizes any source whose longest side exceeds <b>1600 pixels</b>
down to 1600 with INTER_AREA before running the pipeline. The original
full-resolution image is preserved internally and used by:</p>
<ul>
  <li><b>Save Processed Image</b> — output is full-res, regardless of the
      preview setting.</li>
  <li><b>Batch Process Folder</b> — processes whatever the input files are
      natively.</li>
  <li><b>Export Code</b> — generates a function that works on any size.</li>
</ul>
<p>Disable the toggle when you need to inspect very fine detail in the
preview. Re-enable it when the pipeline gets sluggish.</p>
""",
    ),
    FeatureTopic(
        key="timing",
        title="Per-operation timing",
        body="""
<h2>Per-operation timing</h2>
<p>Each node in the bottom strip shows how long the last preview run spent
on that step (e.g. <code>12.4 ms</code>). Disabled or never-executed nodes
show no timing.</p>
<p>Use this to spot bottlenecks: if a Gaussian Blur is taking 200 ms while
everything else is under 10 ms, you have a candidate for a smaller kernel
or for moving it after a downscaling step. The timing is measured by the
preview worker thread, so the numbers include only the op's own work — not
Qt repaints or histogram updates.</p>
""",
    ),
    FeatureTopic(
        key="save_image",
        title="Save Processed Image",
        body="""
<h2>Save Processed Image (Ctrl+S)</h2>
<p>Runs the pipeline on the <b>full-resolution</b> source and writes the
result to disk. The output format follows the chosen extension — PNG keeps
exact pixel values, JPG compresses, TIFF preserves precision (though
cvsandbox writes 8-bit content), BMP / WebP are also supported.</p>
<p>This is the right button when you want to commit the version you've
just tuned. It always uses the original loaded image, so even with
<b>Downscale large previews</b> active you still get a full-res output.</p>
<p>ROI, paste destinations, and multi-input wires are all respected —
whatever you see in the preview is what gets saved (just at native
resolution).</p>
""",
    ),
    FeatureTopic(
        key="record_video",
        title="Record Video",
        body="""
<h2>Record Video</h2>
<p>Only meaningful while a camera or video file is active. Pick a path
(.mp4 or .avi) and the app starts writing every processed frame to a
VideoWriter behind the scenes.</p>
<ul>
  <li>FPS is taken from the source (or 30 fps fallback for cameras that
      don't report).</li>
  <li>The codec is chosen from the file extension — mp4v for .mp4, MJPG
      for .avi.</li>
  <li>Frames that change shape mid-recording (a Resize op flipped, for
      example) are coerced back to the initial size so the writer keeps
      a valid stream.</li>
</ul>
<p><b>Stop Recording</b> finalises the file. The recorder also closes
automatically when the capture ends or the app is closed.</p>
""",
    ),
    FeatureTopic(
        key="save_load_pipeline",
        title="Save and load pipelines",
        body="""
<h2>Save and load pipelines</h2>
<p>Pipelines round-trip through <code>.cvpipe.json</code> files
(<b>File &rarr; Save Pipeline As</b>, <b>Open Pipeline</b>). The serialised
format stores:</p>
<ul>
  <li>Every node — its id, op id, parameters, enabled state, and on-canvas
      position.</li>
  <li>Every edge — full port-aware connections, so multi-input wires
      round-trip too.</li>
  <li>ROI rectangle and paste-destination if either is set.</li>
</ul>
<p>Older v1 files (linear chain only) are auto-migrated on load by
replaying their nodes through the chain builder. You don't have to do
anything to read legacy saves.</p>
""",
    ),
    FeatureTopic(
        key="export_code",
        title="Export Code",
        body="""
<h2>Export Code (Ctrl+E)</h2>
<p>Generates a stand-alone Python function that reproduces the pipeline.
The function takes a single argument (a BGR uint8 ndarray) and returns the
processed result.</p>
<p>The generator walks the graph in topological order. Every node gets its
own <code>step_N</code> variable, so branching and multi-input ops resolve
correctly. The output is verified to match the live pipeline byte-for-byte
in the test suite — what you see is what you get when you copy the code
into your own project.</p>
<p>If the pipeline includes a ROI or composite ops, the generated code
also embeds a <code>_coerce_to_match</code> helper so channel-changing
steps splice back into the source cleanly.</p>
""",
    ),
    FeatureTopic(
        key="dataset_gallery",
        title="Dataset tab",
        body="""
<h2>Dataset tab</h2>
<p>The main window has two tabs at the top — <b>Editor</b> (the default,
with image / panels / pipeline) and <b>Dataset</b>. Switching to the
Dataset tab loads a thumbnail grid of every image in a chosen folder;
click any thumbnail and the app flips back to the Editor with that image
loaded as the active source.</p>
<p><b>File &rarr; Open Dataset…</b> (Ctrl+D) or the matching button in
the action bar jumps to the Dataset tab directly and prompts for a folder
on the first visit.</p>
<h3>Typical workflows</h3>
<ul>
  <li><b>Per-image tuning.</b> Pick a folder, click an image, tweak the
      pipeline for that specific case, hit <b>Save Image</b>, then switch
      back to the Dataset tab and pick the next thumbnail. The previously
      active image stays highlighted so you don't lose your place.</li>
  <li><b>Quick A/B browsing.</b> Compare how the same pipeline behaves on
      a representative set of inputs by clicking through them.</li>
  <li><b>Combine with Bulk Export.</b> Tune the pipeline on a few
      representative images, then run <b>Bulk Export Dataset</b> to apply
      the final settings to the whole folder at once.</li>
</ul>
""",
    ),
    FeatureTopic(
        key="batch",
        title="Bulk Export Dataset",
        body="""
<h2>Bulk Export Dataset</h2>
<p><b>File &rarr; Bulk Export Dataset…</b> opens a modal that applies the
current pipeline to every image in a folder, on a worker thread so the UI
stays responsive.</p>
<h3>Options</h3>
<ul>
  <li><b>Input folder</b> — every PNG / JPG / BMP / TIFF / WebP directly
      inside it is processed.</li>
  <li><b>Output folder</b> — created on demand.</li>
  <li><b>Filename suffix</b> — defaults to <code>_processed</code>; the
      output file becomes <code>{stem}{suffix}{ext}</code>.</li>
  <li><b>Overwrite existing files</b> — off by default so accidental
      reruns don't trample previous results.</li>
</ul>
<p>Errors on individual files don't kill the batch; the dialog shows the
first few failures at the end. <b>Cancel</b> stops between files (the
in-progress one is not interrupted mid-write).</p>
""",
    ),
)


OP_DOCS: dict[str, str] = {
    # ------------------------------------------------------------------ Source
    "source.image": """
<h2>Source</h2>
<p><i>source.image · always present, cannot be removed</i></p>
<p>The original image as loaded from disk or streamed from a camera / video.
The Source is the start of every pipeline. Each new op you add auto-wires from
the previous chain node, but the very first op connects from this Source.</p>
<h3>Where it shines</h3>
<ul>
  <li>Wiring its output into a multi-input op's second input (e.g. Blend's
      <code>b</code> port or Apply Mask's <code>mask</code> port) so the op
      can reference the untouched original alongside the processed chain.</li>
  <li>Cross-checking what a pipeline is changing: feed Source plus the
      end of the chain into <b>Difference</b> to see exactly which pixels
      moved.</li>
</ul>
""",
    # --------------------------------------------------------------- Filtering
    "filtering.gaussian_blur": """
<h2>Gaussian Blur</h2>
<p><i>filtering.gaussian_blur · category: Filtering</i></p>
<p>Smooths an image by convolving with a Gaussian kernel — each output pixel
is the weighted average of its neighbours, with weights falling off in the
shape of a bell curve. The result keeps overall brightness and shape but
loses fine detail and high-frequency noise.</p>
<h3>Parameters</h3>
<ul>
  <li><b>Kernel size</b> — odd integer (e.g. 3, 5, 7…). Larger means more
      blur and slower compute. Practical range: 3-31.</li>
  <li><b>Sigma X</b> — Gaussian standard deviation. <code>0</code> lets
      OpenCV derive a sensible value from the kernel size.</li>
</ul>
<h3>Where it shines</h3>
<ul>
  <li>Pre-processing before edge detection so noise doesn't create fake
      edges. Try <b>Gaussian Blur → Canny</b>.</li>
  <li>Removing Gaussian (sensor) noise from photos.</li>
  <li>Faking a depth-of-field / soft background look with a large kernel.</li>
</ul>
""",
    "filtering.median_blur": """
<h2>Median Blur</h2>
<p><i>filtering.median_blur · category: Filtering</i></p>
<p>Replaces each pixel with the <b>median</b> of its neighbourhood. Because
the median ignores extreme values, salt-and-pepper noise vanishes while
edges stay crisp.</p>
<h3>Parameters</h3>
<ul>
  <li><b>Kernel size</b> — odd integer; bigger means stronger denoising
      and more loss of texture.</li>
</ul>
<h3>Where it shines</h3>
<ul>
  <li>Scanned documents with dust speckles.</li>
  <li>Old photos with isolated white/black pixel noise.</li>
  <li>Drone footage with sensor-dead pixels.</li>
</ul>
""",
    "filtering.bilateral": """
<h2>Bilateral Filter</h2>
<p><i>filtering.bilateral · category: Filtering</i></p>
<p>Edge-preserving smoothing. Like Gaussian Blur, but the weight of each
neighbour also depends on how similar its colour is — so pixels across a
strong edge contribute less. The result: smooth interiors with sharp
boundaries.</p>
<h3>Parameters</h3>
<ul>
  <li><b>Diameter</b> — pixel neighbourhood. 5 is fast, 9 is balanced,
      larger gets slow.</li>
  <li><b>Sigma color</b> — colour distance tolerance. Higher means more
      smoothing across colour edges (less edge preservation).</li>
  <li><b>Sigma space</b> — spatial distance tolerance. Higher means
      farther pixels can still influence each other.</li>
</ul>
<h3>Where it shines</h3>
<ul>
  <li>Portrait skin smoothing without softening eyes / hair.</li>
  <li>Cartoon / illustration look: <b>Bilateral → Canny</b> drawn on top
      of the bilateral output.</li>
  <li>Denoising when you must keep object outlines crisp.</li>
</ul>
""",
    "filtering.nl_means": """
<h2>NL-Means Denoise</h2>
<p><i>filtering.nl_means · category: Filtering</i></p>
<p>Non-local means: for each patch, find similar-looking patches elsewhere
in the image and average them together. Very slow but produces the cleanest
result for Gaussian sensor noise.</p>
<h3>Parameters</h3>
<ul>
  <li><b>Strength (h)</b> — filter strength. Higher cleans more but
      smudges fine detail.</li>
  <li><b>Template size</b> — odd, the patch we compare. 7 is typical.</li>
  <li><b>Search size</b> — odd, area scanned for similar patches.
      Larger gets dramatically slower.</li>
</ul>
<h3>Where it shines</h3>
<ul>
  <li>High-ISO photographs.</li>
  <li>Astronomy / microscopy where Gaussian noise dominates.</li>
  <li>Pre-processing before contour detection on noisy frames.</li>
</ul>
<p><i>Tip:</i> turn on <b>Downscale large previews</b> while tuning — this
op is the slowest in the catalog.</p>
""",
    # ---------------------------------------------------------------- Threshold
    "threshold.binary": """
<h2>Binary Threshold</h2>
<p><i>threshold.binary · category: Threshold</i></p>
<p>Splits pixels into two groups: above <code>thresh</code> become
<code>maxval</code> (typically 255), the rest become 0. Input is forced to
grayscale because thresholding is per-pixel-intensity.</p>
<h3>Parameters</h3>
<ul>
  <li><b>Threshold</b> — cutoff value (0-255).</li>
  <li><b>Max value</b> — what bright pixels become.</li>
  <li><b>Invert</b> — flip foreground / background.</li>
</ul>
<h3>Where it shines</h3>
<ul>
  <li>Extracting bright objects from a dark background (or vice-versa).</li>
  <li>OCR pre-processing on uniformly lit text.</li>
  <li>Producing masks for <b>Apply Mask</b>.</li>
</ul>
<p>Watch the <b>Histogram</b> panel as you drag the slider — pick a value
that sits in a valley between two peaks.</p>
""",
    "threshold.otsu": """
<h2>Otsu Threshold</h2>
<p><i>threshold.otsu · category: Threshold</i></p>
<p>Picks the binary threshold automatically by analysing the image
histogram — it finds the cutoff that best separates the two dominant
brightness groups (bimodal assumption).</p>
<h3>Where it shines</h3>
<ul>
  <li>Documents and printed pages.</li>
  <li>Backlit objects on a uniform background.</li>
  <li>Any time the histogram has two distinct peaks.</li>
</ul>
<p>If your histogram has a single broad hump or many peaks, reach for
<b>Adaptive Threshold</b> instead.</p>
""",
    "threshold.adaptive": """
<h2>Adaptive Threshold</h2>
<p><i>threshold.adaptive · category: Threshold</i></p>
<p>Computes a separate threshold for each small neighbourhood. Robust to
uneven lighting — the bright side of a page and the shadowed side both get
their own correct cutoff.</p>
<h3>Parameters</h3>
<ul>
  <li><b>Method</b> — Mean (faster) or Gaussian-weighted (smoother).</li>
  <li><b>Block size</b> — odd, ≥3. Neighbourhood used per pixel.</li>
  <li><b>C</b> — constant subtracted from the local mean. Higher
      <code>C</code> = stricter cutoff (less foreground).</li>
</ul>
<h3>Where it shines</h3>
<ul>
  <li>Pages photographed under a desk lamp (one side bright).</li>
  <li>Whiteboards with glare.</li>
  <li>Astrophotography where the sky brightness varies.</li>
</ul>
""",
    # --------------------------------------------------------------- Morphology
    "morphology.erode": """
<h2>Erode</h2>
<p><i>morphology.erode · category: Morphology</i></p>
<p>Shrinks bright regions by removing pixels at their boundaries. Equivalent
to "for each pixel, take the minimum of its neighbourhood". Disconnects
thin bridges and removes small bright noise.</p>
<h3>Parameters</h3>
<ul>
  <li><b>Kernel shape</b> — Rectangle, Ellipse, or Cross.</li>
  <li><b>Kernel size</b> — odd integer; bigger removes more.</li>
  <li><b>Iterations</b> — apply N times in a row.</li>
</ul>
<h3>Where it shines</h3>
<ul>
  <li>Cleaning up thresholded masks (kill speckles).</li>
  <li>Separating objects that touch by a thin neck.</li>
</ul>
""",
    "morphology.dilate": """
<h2>Dilate</h2>
<p><i>morphology.dilate · category: Morphology</i></p>
<p>Grows bright regions outward — the opposite of erode. Equivalent to
"for each pixel, take the maximum of its neighbourhood". Closes thin gaps
and connects nearby objects.</p>
<h3>Where it shines</h3>
<ul>
  <li>Thickening detected edges so they're easier to trace.</li>
  <li>Joining fragments of a partially-detected object.</li>
  <li>Building a permissive mask that engulfs the target region.</li>
</ul>
""",
    "morphology.open": """
<h2>Open</h2>
<p><i>morphology.open · category: Morphology</i></p>
<p>Erode then dilate. The first pass removes small bright noise; the second
pass restores the surviving objects to roughly their original size. The net
effect: <b>keep big bright shapes, drop small ones</b>.</p>
<h3>Where it shines</h3>
<ul>
  <li>Removing speckle noise from a thresholded mask without shrinking
      the real objects.</li>
  <li>Cleaning up OCR'd text — punctuation specks vanish, letters survive.</li>
</ul>
""",
    "morphology.close": """
<h2>Close</h2>
<p><i>morphology.close · category: Morphology</i></p>
<p>Dilate then erode. The first pass closes small holes; the second restores
the outline. The net effect: <b>fill small gaps inside bright regions
without growing them</b>.</p>
<h3>Where it shines</h3>
<ul>
  <li>Filling holes inside a thresholded object (broken edges → solid blob).</li>
  <li>Repairing dotted-line annotations.</li>
  <li>Joining nearby fragments of the same letter or shape.</li>
</ul>
""",
    # ------------------------------------------------------------------ Edge
    "edge.canny": """
<h2>Canny</h2>
<p><i>edge.canny · category: Edge</i></p>
<p>The classic multi-stage edge detector: gradient + non-maximum suppression
+ hysteresis. Produces a clean <i>binary</i> edge map.</p>
<h3>Parameters</h3>
<ul>
  <li><b>Threshold 1 / Threshold 2</b> — hysteresis bounds. Pixels above
      T2 are seed edges; pixels above T1 are kept only if connected to a
      seed. Rule of thumb: T2 is roughly 2-3 times T1.</li>
  <li><b>Aperture size</b> — Sobel kernel used internally (3, 5, or 7).</li>
</ul>
<h3>Where it shines</h3>
<ul>
  <li>Lane / line detection in photos and video.</li>
  <li>Pre-processing for contour analysis or Hough transforms.</li>
  <li>Quick "comic book" outline effect.</li>
</ul>
<p><i>Tip:</i> always pair with a small <b>Gaussian Blur</b> upstream so
noise doesn't generate spurious edges.</p>
""",
    "edge.sobel": """
<h2>Sobel</h2>
<p><i>edge.sobel · category: Edge</i></p>
<p>First-order image derivative along x and/or y. Produces a grayscale
gradient magnitude image rather than a binary edge map.</p>
<h3>Parameters</h3>
<ul>
  <li><b>dx / dy</b> — derivative order in each axis. (1, 0) = vertical
      edges, (0, 1) = horizontal edges, (1, 1) = combined.</li>
  <li><b>Kernel size</b> — odd, 1-7. Larger smooths more.</li>
</ul>
<h3>Where it shines</h3>
<ul>
  <li>Highlighting only horizontal or vertical structure.</li>
  <li>Feature engineering for classical machine vision pipelines.</li>
  <li>Gradient-magnitude maps when Canny is too aggressive.</li>
</ul>
""",
    "edge.laplacian": """
<h2>Laplacian</h2>
<p><i>edge.laplacian · category: Edge</i></p>
<p>Second-order derivative. Responds to rapid intensity changes regardless
of direction — useful for blob and dot detection but very sensitive to
noise.</p>
<h3>Where it shines</h3>
<ul>
  <li>Detecting small bright/dark blobs (stars, cells, defects).</li>
  <li>Image sharpening: add a scaled Laplacian back to the original.</li>
  <li>Measuring image focus / sharpness (variance of Laplacian).</li>
</ul>
<p>Always denoise upstream (Median or Gaussian) — Laplacian amplifies noise
aggressively.</p>
""",
    # ------------------------------------------------------------------ Color
    "color.to_grayscale": """
<h2>To Grayscale</h2>
<p><i>color.to_grayscale · category: Color</i></p>
<p>Collapses a BGR image into a single intensity channel using the
luminance-weighted standard formula. Already-gray inputs pass through.</p>
<h3>Where it shines</h3>
<ul>
  <li>Pre-processing for any op that needs a single channel
      (Threshold, Canny, Sobel, Find Contours).</li>
  <li>Stylising photos (mood, classical look).</li>
  <li>Reducing data volume when you don't need colour.</li>
</ul>
""",
    "color.to_hsv": """
<h2>To HSV</h2>
<p><i>color.to_hsv · category: Color</i></p>
<p>Converts BGR to <b>Hue / Saturation / Value</b> — a colour space where
colours are addressed by their actual hue (red, green, blue, …) rather than
by mixing primaries. Far easier to reason about for colour-based selection.</p>
<h3>Where it shines</h3>
<ul>
  <li>Right before <b>HSV In-Range Mask</b> to pick a colour range.</li>
  <li>Per-channel analysis: a hue histogram shows the dominant colours.</li>
  <li>Designing colour-based segmentation rules.</li>
</ul>
""",
    "color.invert": """
<h2>Invert</h2>
<p><i>color.invert · category: Color</i></p>
<p><code>255 - pixel</code> on every channel. Light becomes dark; dark
becomes light.</p>
<h3>Where it shines</h3>
<ul>
  <li>Photographic negative effect.</li>
  <li>Flipping a mask's foreground / background.</li>
  <li>Algorithms that assume bright = foreground when your subject is
      actually dark.</li>
</ul>
""",
    "color.channel": """
<h2>Extract Channel</h2>
<p><i>color.channel · category: Color</i></p>
<p>Picks a single channel and returns it as a grayscale image. For BGR
input: 0 = blue, 1 = green, 2 = red. For HSV input: 0 = hue, 1 = saturation,
2 = value.</p>
<h3>Where it shines</h3>
<ul>
  <li>"Show me the red channel only" debugging.</li>
  <li>Isolating saturation to find vivid regions.</li>
  <li>Working with infrared / multispectral imagery where one band carries
      the signal.</li>
</ul>
""",
    "color.clahe": """
<h2>CLAHE</h2>
<p><i>color.clahe · category: Color</i></p>
<p>Contrast Limited Adaptive Histogram Equalization. For each small tile,
spreads pixel intensities across the full 0-255 range, then clips and
recombines with neighbours so over-amplification doesn't create halos. For
colour input it operates on the L channel of LAB so colours stay natural.</p>
<h3>Parameters</h3>
<ul>
  <li><b>Clip limit</b> — caps contrast amplification per tile. Higher =
      more aggressive.</li>
  <li><b>Tile grid</b> — N by N tiles. Smaller = more local, larger =
      more global.</li>
</ul>
<h3>Where it shines</h3>
<ul>
  <li>Dim photographs and low-light footage.</li>
  <li>Medical imaging (X-ray, mammography) — the textbook use case.</li>
  <li>Recovering detail in shadowed regions without blowing out the
      highlights.</li>
</ul>
""",
    "color.hsv_in_range": """
<h2>HSV In-Range Mask</h2>
<p><i>color.hsv_in_range · category: Color</i></p>
<p>Returns a binary mask: white where the pixel's HSV falls inside the
given (H, S, V) box, black elsewhere. Input must be BGR — the op converts
to HSV internally.</p>
<h3>Parameters</h3>
<ul>
  <li><b>H min / max</b> — hue range (0-179 in OpenCV).</li>
  <li><b>S min / max</b> — saturation (0-255). Lower S = pale / grey
      colours; higher S = vivid colours.</li>
  <li><b>V min / max</b> — value / brightness.</li>
</ul>
<h3>Where it shines</h3>
<ul>
  <li>Detecting a coloured ball, sign, or marker.</li>
  <li>Picking "green" vegetation in drone imagery.</li>
  <li>Filtering out background that has a known colour.</li>
</ul>
<p><i>Note:</i> red wraps around the hue circle (0 and 179). To catch all
reds you may need a second range and combine via <b>Blend</b> with
alpha=0.5 or use upstream ops.</p>
""",
    # -------------------------------------------------------------- Geometric
    "geometric.resize": """
<h2>Resize</h2>
<p><i>geometric.resize · category: Geometric</i></p>
<p>Scales the image. Independent X and Y factors plus an interpolation
choice.</p>
<h3>Parameters</h3>
<ul>
  <li><b>Scale X / Y</b> — multiplier (1.0 = unchanged).</li>
  <li><b>Interpolation</b> — Nearest (sharp / blocky), Linear (general
      purpose), Cubic (slightly smoother upscale), Area (best for
      downscaling).</li>
</ul>
<h3>Where it shines</h3>
<ul>
  <li>Speeding up an expensive pipeline by working at half size.</li>
  <li>Preparing inputs for a fixed-size neural network.</li>
  <li>Producing thumbnails or print-resolution variants.</li>
</ul>
""",
    "geometric.rotate": """
<h2>Rotate</h2>
<p><i>geometric.rotate · category: Geometric</i></p>
<p>Rotates around the image centre by the given angle in degrees. Canvas
size is preserved, so corners that rotate outside the frame are clipped.</p>
<h3>Where it shines</h3>
<ul>
  <li>Correcting tilted scans or photographs.</li>
  <li>Data augmentation when generating training images.</li>
  <li>Compass / orientation overlays.</li>
</ul>
""",
    "geometric.flip": """
<h2>Flip</h2>
<p><i>geometric.flip · category: Geometric</i></p>
<p>Mirrors the image horizontally, vertically, or both.</p>
<h3>Where it shines</h3>
<ul>
  <li>Correcting selfie-camera mirroring.</li>
  <li>Data augmentation.</li>
  <li>Comic-strip or graphic-design layouts where you need a flipped twin.</li>
</ul>
""",
    # --------------------------------------------------------------- Analysis
    "analysis.find_contours": """
<h2>Find Contours</h2>
<p><i>analysis.find_contours · category: Analysis</i></p>
<p>Finds the outline of every connected non-zero region in the input
(treating it as binary), then draws those contours in green on top of the
original image. Pair with a threshold or mask upstream.</p>
<h3>Parameters</h3>
<ul>
  <li><b>Retrieval mode</b> — External (only outer outlines) or All (also
      nested holes).</li>
  <li><b>Min area</b> — discard contours smaller than this many pixels.
      Filters out noise blobs.</li>
  <li><b>Line thickness</b> — pixels; <code>-1</code> fills the contour.</li>
</ul>
<h3>Where it shines</h3>
<ul>
  <li>Counting objects after threshold (cells, coins, pills).</li>
  <li>Locating shapes for downstream geometric analysis.</li>
  <li>Visualising what a mask actually contains.</li>
</ul>
<p><i>Typical chain:</i> <b>Gaussian Blur → Threshold → Open → Find
Contours</b>.</p>
""",
    # --------------------------------------------------------------- Composite
    "composite.blend": """
<h2>Blend</h2>
<p><i>composite.blend · category: Composite · multi-input</i></p>
<p>Alpha-blends two images: <code>out = (1 - alpha) · a + alpha · b</code>. Drag a
wire from any node's output to the <code>b</code> port to control the
second input — by default it falls back to the Source image.</p>
<h3>Parameters</h3>
<ul>
  <li><b>Alpha</b> — weight of input <code>b</code> (0 = only
      <code>a</code>, 1 = only <code>b</code>).</li>
</ul>
<h3>Where it shines</h3>
<ul>
  <li>Soft glow: <b>Bilateral / NL-Means → Blend (Source on b, alpha=0.4)</b>
      keeps original sharpness with a denoised wash.</li>
  <li>"Selective sharpening" with alpha<0.5 between original and high-pass.</li>
  <li>Watermarking by blending a logo on top with low alpha.</li>
</ul>
""",
    "composite.apply_mask": """
<h2>Apply Mask</h2>
<p><i>composite.apply_mask · category: Composite · multi-input</i></p>
<p>Keeps the input image's pixels where the mask is non-zero, zeros the
rest. The mask is automatically thresholded and resized to match if needed.
Wire a thresholded image or HSV-range mask into the <code>mask</code>
port.</p>
<h3>Where it shines</h3>
<ul>
  <li>Isolating a coloured object: <b>HSV In-Range Mask → Apply Mask</b>
      (with the original colour image on the <code>image</code> port).</li>
  <li>Background removal once you have a foreground mask.</li>
  <li>Compositing only the interesting part of one image onto a backdrop.</li>
</ul>
""",
    "composite.difference": """
<h2>Difference</h2>
<p><i>composite.difference · category: Composite · multi-input</i></p>
<p>Absolute per-pixel difference between two images: <code>out =
|a - b|</code>. Bright pixels mark where the two inputs disagree.</p>
<h3>Where it shines</h3>
<ul>
  <li>Motion detection: <b>Difference</b> between two consecutive video
      frames lights up only the moving parts.</li>
  <li>Quality assurance — comparing a printed scan against an ideal
      reference.</li>
  <li>Building a high-pass filter: <b>Source → Difference (with Gaussian
      Blur output on b)</b> isolates the high-frequency detail.</li>
</ul>
""",
}


def get_op_doc(spec_id: str) -> str:
    """Return the HTML help blob for `spec_id`, or a fallback notice."""
    doc = OP_DOCS.get(spec_id)
    if doc is None:
        return (
            f"<p>No documentation has been written yet for "
            f"<code>{spec_id}</code>.</p>"
        )
    return doc.strip()


def documented_op_ids() -> tuple[str, ...]:
    return tuple(OP_DOCS.keys())


def get_feature_doc(key: str) -> str:
    """Return the HTML help blob for a feature topic, or a fallback notice."""
    for topic in FEATURE_TOPICS:
        if topic.key == key:
            return topic.body.strip()
    return f"<p>No documentation has been written yet for <code>{key}</code>.</p>"


def feature_topic_keys() -> tuple[str, ...]:
    return tuple(topic.key for topic in FEATURE_TOPICS)
