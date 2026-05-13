"""Filtering operations: smoothing, denoising."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from cvsandbox.core.operation import OperationSpec, Parameter


def _gaussian_blur(image: np.ndarray, ksize: int, sigma_x: float) -> np.ndarray:
    k = int(ksize) | 1  # cv2 requires odd kernel sizes
    return cv2.GaussianBlur(image, (k, k), float(sigma_x))


def _gaussian_blur_code(
    params: dict[str, Any], input_vars: tuple[str, ...], output_var: str
) -> list[str]:
    (a,) = input_vars
    k = int(params["ksize"]) | 1
    sigma = float(params["sigma_x"])
    return [f"{output_var} = cv2.GaussianBlur({a}, ({k}, {k}), {sigma})"]


def _median_blur(image: np.ndarray, ksize: int) -> np.ndarray:
    return cv2.medianBlur(image, int(ksize) | 1)


def _median_blur_code(
    params: dict[str, Any], input_vars: tuple[str, ...], output_var: str
) -> list[str]:
    (a,) = input_vars
    k = int(params["ksize"]) | 1
    return [f"{output_var} = cv2.medianBlur({a}, {k})"]


GAUSSIAN_BLUR = OperationSpec(
    id="filtering.gaussian_blur",
    name="Gaussian Blur",
    category="Filtering",
    description="Smooths the image with a Gaussian kernel.",
    parameters=(
        Parameter(
            name="ksize",
            kind="kernel_size",
            default=3,
            min=1,
            max=99,
            step=2,
            label="Kernel size",
            description="Odd integer; larger = blurrier.",
        ),
        Parameter(
            name="sigma_x",
            kind="float",
            default=0.0,
            min=0.0,
            max=20.0,
            step=0.1,
            label="Sigma X",
            description="Gaussian standard deviation. 0 = derive from ksize.",
        ),
    ),
    func=_gaussian_blur,
    code_export=_gaussian_blur_code,
)


MEDIAN_BLUR = OperationSpec(
    id="filtering.median_blur",
    name="Median Blur",
    category="Filtering",
    description="Replaces each pixel with the median of its neighborhood. Strong against salt-and-pepper noise.",
    parameters=(
        Parameter(
            name="ksize",
            kind="kernel_size",
            default=3,
            min=1,
            max=99,
            step=2,
            label="Kernel size",
            description="Odd integer; larger = stronger denoising.",
        ),
    ),
    func=_median_blur,
    code_export=_median_blur_code,
)


def _bilateral(image: np.ndarray, d: int, sigma_color: float, sigma_space: float) -> np.ndarray:
    return cv2.bilateralFilter(image, int(d), float(sigma_color), float(sigma_space))


def _bilateral_code(
    params: dict[str, Any], input_vars: tuple[str, ...], output_var: str
) -> list[str]:
    (a,) = input_vars
    return [
        f"{output_var} = cv2.bilateralFilter({a}, {int(params['d'])}, "
        f"{float(params['sigma_color'])}, {float(params['sigma_space'])})"
    ]


def _nl_means(image: np.ndarray, strength: float, template_size: int, search_size: int) -> np.ndarray:
    t = max(3, int(template_size) | 1)
    s = max(t + 2, int(search_size) | 1)
    if image.ndim == 3:
        return cv2.fastNlMeansDenoisingColored(image, None, float(strength), float(strength), t, s)
    return cv2.fastNlMeansDenoising(image, None, float(strength), t, s)


def _nl_means_code(
    params: dict[str, Any], input_vars: tuple[str, ...], output_var: str
) -> list[str]:
    (a,) = input_vars
    strength = float(params["strength"])
    t = max(3, int(params["template_size"]) | 1)
    s = max(t + 2, int(params["search_size"]) | 1)
    return [
        f"if {a}.ndim == 3:",
        f"    {output_var} = cv2.fastNlMeansDenoisingColored({a}, None, {strength}, {strength}, {t}, {s})",
        "else:",
        f"    {output_var} = cv2.fastNlMeansDenoising({a}, None, {strength}, {t}, {s})",
    ]


BILATERAL = OperationSpec(
    id="filtering.bilateral",
    name="Bilateral Filter",
    category="Filtering",
    description="Edge-preserving smoothing. Slower than Gaussian; keeps strong edges sharp.",
    parameters=(
        Parameter(
            name="d",
            kind="int",
            default=9,
            min=1,
            max=25,
            label="Diameter",
            description="Pixel neighborhood diameter. 5 = fast, 9 = balanced, larger = very slow.",
        ),
        Parameter(
            name="sigma_color",
            kind="float",
            default=75.0,
            min=1.0,
            max=200.0,
            step=1.0,
            label="Sigma color",
            description="Higher = colors farther apart get mixed (more smoothing across edges).",
        ),
        Parameter(
            name="sigma_space",
            kind="float",
            default=75.0,
            min=1.0,
            max=200.0,
            step=1.0,
            label="Sigma space",
            description="Higher = farther pixels influence each other (more global smoothing).",
        ),
    ),
    func=_bilateral,
    code_export=_bilateral_code,
)


NL_MEANS = OperationSpec(
    id="filtering.nl_means",
    name="NL-Means Denoise",
    category="Filtering",
    description="Non-local means denoising. Slow but very effective on Gaussian noise.",
    parameters=(
        Parameter(
            name="strength",
            kind="float",
            default=10.0,
            min=1.0,
            max=50.0,
            step=1.0,
            label="Strength (h)",
            description="Filter strength. Higher = more denoising and more loss of detail.",
        ),
        Parameter(
            name="template_size",
            kind="kernel_size",
            default=7,
            min=3,
            max=21,
            step=2,
            label="Template size",
            description="Odd, ≥3. Size of the patch used to compare pixels.",
        ),
        Parameter(
            name="search_size",
            kind="kernel_size",
            default=21,
            min=5,
            max=51,
            step=2,
            label="Search size",
            description="Odd. Size of the search window. Bigger = slower.",
        ),
    ),
    func=_nl_means,
    code_export=_nl_means_code,
)


ALL: tuple[OperationSpec, ...] = (GAUSSIAN_BLUR, MEDIAN_BLUR, BILATERAL, NL_MEANS)
