from __future__ import annotations

import ast

import numpy as np
import pytest

from cvsandbox.core.codegen import generate_python_code
from cvsandbox.core.operation import OperationSpec
from cvsandbox.core.pipeline import Pipeline, Roi
from cvsandbox.operations import all_builtin_specs, load_builtin_operations


def _no_export() -> OperationSpec:
    return OperationSpec(
        id="test.no_export",
        name="No Export",
        category="Test",
        description="",
        parameters=(),
        func=lambda image: image,
    )


def test_empty_pipeline_emits_pass_body() -> None:
    code = generate_python_code(Pipeline())
    assert "def process(img: np.ndarray) -> np.ndarray:" in code
    assert "pass" in code
    assert code.rstrip().endswith("return img")


def test_generated_code_always_parses_as_valid_python() -> None:
    load_builtin_operations()
    pipe = Pipeline()
    for spec in all_builtin_specs():
        pipe.add(spec)  # use defaults
    code = generate_python_code(pipe)
    ast.parse(code)  # raises on invalid syntax


def test_disabled_nodes_are_skipped_in_output() -> None:
    load_builtin_operations()
    pipe = Pipeline()
    pipe.add(_spec("filtering.gaussian_blur"))
    disabled = pipe.add(_spec("filtering.median_blur"))
    disabled.enabled = False
    code = generate_python_code(pipe)
    assert "GaussianBlur" in code
    assert "medianBlur" not in code


def test_gaussian_blur_bakes_odd_kernel() -> None:
    load_builtin_operations()
    pipe = Pipeline()
    pipe.add(_spec("filtering.gaussian_blur"), {"ksize": 4, "sigma_x": 2.5})
    code = generate_python_code(pipe)
    assert "cv2.GaussianBlur(img, (5, 5), 2.5)" in code


def test_node_index_and_name_appear_as_comment() -> None:
    load_builtin_operations()
    pipe = Pipeline()
    pipe.add(_spec("filtering.gaussian_blur"))
    code = generate_python_code(pipe)
    assert "# [0] Gaussian Blur" in code


def test_op_without_code_export_raises() -> None:
    pipe = Pipeline()
    pipe.add(_no_export())
    with pytest.raises(ValueError, match="does not support code export"):
        generate_python_code(pipe)


def test_generated_canny_pipeline_matches_runtime() -> None:
    """The exported code should be functionally equivalent to the live pipeline."""
    load_builtin_operations()
    pipe = Pipeline()
    pipe.add(_spec("filtering.gaussian_blur"), {"ksize": 5, "sigma_x": 1.0})
    pipe.add(_spec("edge.canny"), {"threshold1": 50, "threshold2": 150, "aperture_size": 3})

    rng = np.random.default_rng(0)
    img = rng.integers(0, 256, size=(50, 50, 3), dtype=np.uint8)

    live = pipe.execute(img)

    code = generate_python_code(pipe)
    namespace: dict[str, object] = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    process = namespace["process"]
    generated = process(img.copy())  # type: ignore[operator]

    assert isinstance(generated, np.ndarray)
    assert np.array_equal(live, generated)


def test_roi_pipeline_emits_crop_and_splice_wrapper() -> None:
    load_builtin_operations()
    pipe = Pipeline()
    pipe.add(_spec("filtering.gaussian_blur"))
    pipe.roi = Roi(x=10, y=20, width=100, height=50)
    code = generate_python_code(pipe)
    assert "_x, _y, _w, _h = 10, 20, 100, 50" in code
    assert "_dx, _dy = _x, _y" in code  # paste-to defaults to ROI origin
    assert "_src[_y:_y + _h, _x:_x + _w].copy()" in code
    assert "_coerce_to_match" in code  # helper for channel-changing steps
    assert "return _out" in code


def test_roi_pipeline_with_paste_destination_bakes_offset() -> None:
    load_builtin_operations()
    pipe = Pipeline()
    pipe.add(_spec("filtering.gaussian_blur"))
    pipe.roi = Roi(x=10, y=20, width=30, height=40)
    pipe.roi_paste_to = (200, 100)
    code = generate_python_code(pipe)
    assert "_dx, _dy = 200, 100" in code


def test_roi_pipeline_paste_destination_matches_runtime() -> None:
    """Exported code with a custom paste destination should match Pipeline.execute."""
    load_builtin_operations()
    pipe = Pipeline()
    pipe.add(_spec("filtering.gaussian_blur"), {"ksize": 3, "sigma_x": 1.0})
    pipe.roi = Roi(x=2, y=2, width=8, height=8)
    pipe.roi_paste_to = (20, 20)

    rng = np.random.default_rng(7)
    img = rng.integers(0, 256, size=(40, 40, 3), dtype=np.uint8)

    live = pipe.execute(img)

    code = generate_python_code(pipe)
    namespace: dict[str, object] = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    process = namespace["process"]
    generated = process(img.copy())  # type: ignore[operator]

    assert np.array_equal(live, generated)


def test_roi_generated_pipeline_matches_runtime() -> None:
    """Exported code with ROI should produce the same array as Pipeline.execute."""
    load_builtin_operations()
    pipe = Pipeline()
    pipe.add(_spec("filtering.gaussian_blur"), {"ksize": 5, "sigma_x": 1.0})
    pipe.roi = Roi(x=5, y=5, width=20, height=20)

    rng = np.random.default_rng(0)
    img = rng.integers(0, 256, size=(40, 40, 3), dtype=np.uint8)

    live = pipe.execute(img)

    code = generate_python_code(pipe)
    namespace: dict[str, object] = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    process = namespace["process"]
    generated = process(img.copy())  # type: ignore[operator]

    assert isinstance(generated, np.ndarray)
    assert np.array_equal(live, generated)


def _spec(spec_id: str) -> OperationSpec:
    from cvsandbox.core.registry import get_operation

    return get_operation(spec_id)
