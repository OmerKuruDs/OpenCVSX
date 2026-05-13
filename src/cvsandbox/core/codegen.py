"""Python code generation for pipelines.

Produces a self-contained `process(img)` function that reproduces the pipeline
outside of cvsandbox. Each enabled node contributes one or more source lines
through its `OperationSpec.code_export` callable. Disabled nodes are skipped.

The generator only relies on `cv2` and `numpy`, which it always imports.
"""

from __future__ import annotations

from typing import Any

from cvsandbox.core.pipeline import Pipeline

_HEADER = (
    "import cv2",
    "import numpy as np",
    "",
    "",
)


def generate_python_code(
    pipeline: Pipeline,
    *,
    function_name: str = "process",
) -> str:
    steps: list[str] = []
    for index, node in enumerate(pipeline.nodes):
        if not node.enabled:
            continue
        if node.spec.code_export is None:
            raise ValueError(
                f"Operation {node.spec.id!r} does not support code export"
            )
        op_lines = node.spec.code_export(dict(node.params))
        if not op_lines:
            continue
        steps.append(f"# [{index}] {node.spec.name}")
        steps.extend(op_lines)

    helpers: list[str] = []
    if pipeline.roi is None:
        body = _wrap_function_body(steps)
    else:
        helpers = _COERCE_HELPER_LINES
        body = _wrap_function_body_with_roi(steps, pipeline.roi, pipeline.roi_paste_to)

    lines = [*_HEADER, *helpers, f"def {function_name}(img: np.ndarray) -> np.ndarray:", *body]
    return "\n".join(lines) + "\n"


def _wrap_function_body(steps: list[str]) -> list[str]:
    if not steps:
        return ["    # (empty pipeline)", "    pass", "    return img"]
    return [*(f"    {line}" for line in steps), "    return img"]


def _wrap_function_body_with_roi(
    steps: list[str], roi: Any, paste_to: tuple[int, int] | None
) -> list[str]:
    inner = steps if steps else ["pass"]
    if paste_to is None:
        dest_lines = ["    _dx, _dy = _x, _y"]
    else:
        dest_lines = [f"    _dx, _dy = {paste_to[0]}, {paste_to[1]}"]
    return [
        f"    _x, _y, _w, _h = {roi.x}, {roi.y}, {roi.width}, {roi.height}",
        *dest_lines,
        "    _src = img",
        "    img = _src[_y:_y + _h, _x:_x + _w].copy()",
        *(f"    {line}" for line in inner),
        "    img = _coerce_to_match(img, _src)",
        "    _out = _src.copy()",
        "    try:",
        "        _ih, _iw = img.shape[:2]",
        "        _th, _tw = _out.shape[:2]",
        "        _sx0 = max(0, -_dx); _sy0 = max(0, -_dy)",
        "        _dx0 = max(0, _dx); _dy0 = max(0, _dy)",
        "        _tw_a = max(0, _tw - _dx0); _th_a = max(0, _th - _dy0)",
        "        _take_w = min(_iw - _sx0, _tw_a); _take_h = min(_ih - _sy0, _th_a)",
        "        if _take_w > 0 and _take_h > 0:",
        "            _out[_dy0:_dy0 + _take_h, _dx0:_dx0 + _take_w] = "
        "img[_sy0:_sy0 + _take_h, _sx0:_sx0 + _take_w]",
        "    except (ValueError, TypeError):",
        "        return _src.copy()",
        "    return _out",
    ]


_COERCE_HELPER_LINES: list[str] = [
    "def _coerce_to_match(image: np.ndarray, like: np.ndarray) -> np.ndarray:",
    '    """Reshape image to match like\'s channel layout (gray <-> BGR <-> BGRA)."""',
    "    _src_2d = image.ndim == 2",
    "    _dst_2d = like.ndim == 2",
    "    _src_c = 1 if _src_2d else image.shape[2]",
    "    _dst_c = 1 if _dst_2d else like.shape[2]",
    "    if (_src_2d, _src_c) == (_dst_2d, _dst_c):",
    "        return image",
    "    if _src_2d:",
    "        if _dst_c == 3:",
    "            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)",
    "        if _dst_c == 4:",
    "            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)",
    "    elif _dst_2d:",
    "        if _src_c == 3:",
    "            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)",
    "        if _src_c == 4:",
    "            return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)",
    "    else:",
    "        if _src_c == 3 and _dst_c == 4:",
    "            return cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)",
    "        if _src_c == 4 and _dst_c == 3:",
    "            return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)",
    "    return image",
    "",
    "",
]
