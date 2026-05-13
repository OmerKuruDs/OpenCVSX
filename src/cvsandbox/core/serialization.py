"""Pipeline persistence to/from JSON.

`.cvpipe.json` files are versioned. v1 layout:

    {
        "version": 1,
        "nodes": [
            {"id": "filtering.gaussian_blur",
             "params": {"ksize": 5, "sigma_x": 1.0},
             "enabled": true},
            ...
        ]
    }

Unknown operation ids raise `KeyError` (via the registry). Unknown parameters
raise `ValueError` (via PipelineNode.__post_init__). Loading is atomic:
either every node materializes successfully and the target pipeline is
replaced, or the target is left untouched.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cvsandbox.core.pipeline import Pipeline, PipelineNode, Roi
from cvsandbox.core.registry import get_operation

CURRENT_VERSION = 1


def to_dict(pipeline: Pipeline) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": CURRENT_VERSION,
        "nodes": [
            {"id": node.spec.id, "params": dict(node.params), "enabled": node.enabled}
            for node in pipeline.nodes
        ],
    }
    if pipeline.roi is not None:
        payload["roi"] = {
            "x": pipeline.roi.x,
            "y": pipeline.roi.y,
            "width": pipeline.roi.width,
            "height": pipeline.roi.height,
        }
    if pipeline.roi_paste_to is not None:
        payload["roi_paste_to"] = list(pipeline.roi_paste_to)
    return payload


def from_dict(data: dict[str, Any], into: Pipeline) -> None:
    version = data.get("version")
    if version != CURRENT_VERSION:
        raise ValueError(f"Unsupported pipeline version: {version!r}")
    new_nodes: list[PipelineNode] = []
    for raw in data.get("nodes", []):
        spec = get_operation(raw["id"])
        node = PipelineNode(spec=spec, params=dict(raw.get("params", {})))
        node.enabled = bool(raw.get("enabled", True))
        new_nodes.append(node)
    new_roi: Roi | None = None
    if "roi" in data and data["roi"] is not None:
        raw_roi = data["roi"]
        new_roi = Roi(
            x=int(raw_roi["x"]),
            y=int(raw_roi["y"]),
            width=int(raw_roi["width"]),
            height=int(raw_roi["height"]),
        )
    new_paste: tuple[int, int] | None = None
    if data.get("roi_paste_to") is not None:
        raw_paste = data["roi_paste_to"]
        new_paste = (int(raw_paste[0]), int(raw_paste[1]))
    into.nodes[:] = new_nodes  # atomic swap once we know everything materialized
    into.roi = new_roi
    into.roi_paste_to = new_paste


def save(pipeline: Pipeline, path: Path) -> None:
    path.write_text(json.dumps(to_dict(pipeline), indent=2), encoding="utf-8")


def load(path: Path, into: Pipeline) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    from_dict(data, into)
