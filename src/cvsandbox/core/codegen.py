"""Python code generation for pipelines.

Produces a self-contained `process(img)` function that reproduces the pipeline
outside of cvsandbox. Each enabled node contributes one or more source lines
through its `OperationSpec.code_export` callable. Disabled nodes are skipped.

The generator only relies on `cv2` and `numpy`, which it always imports.
"""

from __future__ import annotations

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
    body: list[str] = []
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
        body.append(f"    # [{index}] {node.spec.name}")
        body.extend(f"    {line}" for line in op_lines)

    if not body:
        body.append("    # (empty pipeline)")
        body.append("    pass")
    body.append("    return img")

    lines = [
        *_HEADER,
        f"def {function_name}(img: np.ndarray) -> np.ndarray:",
        *body,
    ]
    return "\n".join(lines) + "\n"
