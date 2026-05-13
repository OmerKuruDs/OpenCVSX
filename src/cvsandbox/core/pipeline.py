"""Pipeline — ordered list of operations applied to an image.

A Pipeline holds a sequence of PipelineNodes. Each node binds an OperationSpec
to a concrete set of parameter values. Executing the pipeline copies the input
image once at the start, then folds each enabled node over it in order.

The original image is never mutated. Disabled nodes are skipped without affecting
downstream output.

Optionally a `Roi` can be set on the pipeline. When present, execute() crops the
input to the ROI, runs the nodes on the crop, and splices the result back into
a copy of the original image. If the steps change the crop's shape (e.g. a
Resize op), the splice is skipped and the unchanged source is returned.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from cvsandbox.core.operation import OperationSpec


def _fit_crop_to_destination(
    patch: np.ndarray,
    target_shape: tuple[int, ...],
    dst_x: int,
    dst_y: int,
) -> tuple[np.ndarray, tuple[int, int]] | None:
    """Clip `patch` so it fits at `(dst_x, dst_y)` inside an image of
    `target_shape`. Returns the (possibly trimmed) patch and the clamped
    destination origin, or None if the destination has no on-image overlap."""
    target_h, target_w = target_shape[:2]
    ph, pw = patch.shape[:2]

    src_x0 = max(0, -dst_x)
    src_y0 = max(0, -dst_y)
    dst_x0 = max(0, dst_x)
    dst_y0 = max(0, dst_y)

    avail_w = max(0, target_w - dst_x0)
    avail_h = max(0, target_h - dst_y0)
    take_w = min(pw - src_x0, avail_w)
    take_h = min(ph - src_y0, avail_h)
    if take_w <= 0 or take_h <= 0:
        return None

    sliced = patch[src_y0 : src_y0 + take_h, src_x0 : src_x0 + take_w]
    return sliced, (dst_x0, dst_y0)


def coerce_to_match(image: np.ndarray, like: np.ndarray) -> np.ndarray:
    """Return `image` reshaped to match `like`'s channel layout — gray ↔ BGR ↔
    BGRA — so it can be assigned back into a slice of `like`. Falls back to the
    untouched input when there is no clean colour-space mapping (the caller's
    splice will then raise and trigger the original-source fallback)."""
    src_2d = image.ndim == 2
    dst_2d = like.ndim == 2
    src_c = 1 if src_2d else image.shape[2]
    dst_c = 1 if dst_2d else like.shape[2]
    if (src_2d, src_c) == (dst_2d, dst_c):
        return image

    if src_2d:
        if dst_c == 3:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        if dst_c == 4:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
    elif dst_2d:
        if src_c == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        if src_c == 4:
            return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    else:
        if src_c == 3 and dst_c == 4:
            return cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
        if src_c == 4 and dst_c == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

    return image


@dataclass(frozen=True, slots=True)
class Roi:
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError(
                f"Roi requires positive width and height, got {self.width}x{self.height}"
            )

    def clipped_to(self, shape: tuple[int, ...]) -> Roi | None:
        """Return a copy clipped to the image's H,W bounds, or None if the
        intersection is empty."""
        h_img, w_img = shape[:2]
        x0 = max(0, min(w_img, self.x))
        y0 = max(0, min(h_img, self.y))
        x1 = max(0, min(w_img, self.x + self.width))
        y1 = max(0, min(h_img, self.y + self.height))
        if x1 <= x0 or y1 <= y0:
            return None
        return Roi(x=x0, y=y0, width=x1 - x0, height=y1 - y0)


@dataclass(slots=True)
class PipelineNode:
    spec: OperationSpec
    params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def __post_init__(self) -> None:
        # Fill in defaults for unspecified params; reject unknown ones.
        defaults = self.spec.default_params()
        unknown = set(self.params) - set(defaults)
        if unknown:
            raise ValueError(f"Unknown parameter(s) for {self.spec.id}: {sorted(unknown)}")
        for name, default in defaults.items():
            self.params.setdefault(name, default)

    def execute(self, image: np.ndarray) -> np.ndarray:
        return self.spec.func(image, **self.params)


class Pipeline:
    def __init__(self) -> None:
        self._nodes: list[PipelineNode] = []
        self.roi: Roi | None = None
        self.roi_paste_to: tuple[int, int] | None = None
        """When set together with `roi`, the processed crop is spliced into
        this (x, y) top-left coordinate instead of back at the ROI's own
        position. Ignored when `roi` is None."""

    @property
    def nodes(self) -> list[PipelineNode]:
        return self._nodes

    def __len__(self) -> int:
        return len(self._nodes)

    def add(self, spec: OperationSpec, params: dict[str, Any] | None = None) -> PipelineNode:
        node = PipelineNode(spec=spec, params=dict(params) if params else {})
        self._nodes.append(node)
        return node

    def remove(self, index: int) -> PipelineNode:
        return self._nodes.pop(index)

    def move(self, src: int, dst: int) -> None:
        node = self._nodes.pop(src)
        self._nodes.insert(dst, node)

    def reorder(self, permutation: Sequence[int]) -> None:
        """Permute the nodes in-place. `permutation` is the new ordering as
        old-index values — e.g. `[2, 0, 1]` says "what is now at position 0 used
        to be at index 2." Raises if it is not a valid permutation."""
        n = len(self._nodes)
        order = list(permutation)
        if len(order) != n or sorted(order) != list(range(n)):
            raise ValueError(
                f"reorder() expects a permutation of 0..{n - 1}, got {order!r}"
            )
        self._nodes = [self._nodes[i] for i in order]

    def clear(self) -> None:
        self._nodes.clear()
        self.roi = None
        self.roi_paste_to = None

    def execute(self, image: np.ndarray) -> np.ndarray:
        if self.roi is None:
            return self._run_steps(image.copy())

        clipped = self.roi.clipped_to(image.shape)
        if clipped is None:
            return image.copy()

        crop = image[
            clipped.y : clipped.y + clipped.height,
            clipped.x : clipped.x + clipped.width,
        ].copy()
        processed = self._run_steps(crop)
        # Pipeline steps may change channel count (To Grayscale, HSV mask, Canny
        # on a colour input, ...). Coerce back to the source's layout before
        # splicing — otherwise the assignment raises and the whole ROI effect
        # is silently lost.
        processed = coerce_to_match(processed, image)

        dst_x, dst_y = (
            self.roi_paste_to if self.roi_paste_to is not None else (clipped.x, clipped.y)
        )
        result = image.copy()
        try:
            paste = _fit_crop_to_destination(
                processed, image.shape, dst_x, dst_y
            )
            if paste is None:
                return image.copy()
            patch, (px, py) = paste
            ph, pw = patch.shape[:2]
            result[py : py + ph, px : px + pw] = patch
        except (ValueError, TypeError):
            # H/W mismatch or other splice failure (e.g. Resize op). Return
            # the source untouched.
            return image.copy()
        return result

    def _run_steps(self, image: np.ndarray) -> np.ndarray:
        current = image
        for node in self._nodes:
            if not node.enabled:
                continue
            current = node.execute(current)
        return current
