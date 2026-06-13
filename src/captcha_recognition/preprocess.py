from __future__ import annotations

import io
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageOps

from .types import Box


def load_pil_image(image: str | Path | bytes | Image.Image) -> Image.Image:
    if isinstance(image, Image.Image):
        return image.convert("RGB")
    if isinstance(image, (str, Path)):
        return Image.open(image).convert("RGB")
    if isinstance(image, bytes):
        return Image.open(io.BytesIO(image)).convert("RGB")
    raise TypeError(f"Unsupported image type: {type(image)}")


def image_to_bytes(image: Image.Image, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    image.save(buf, format=fmt)
    return buf.getvalue()


def crop_box(image: Image.Image, box: Box, pad_ratio: float = 0.15) -> Image.Image:
    padded = box.pad(pad_ratio, image.width, image.height)
    return image.crop((padded.x1, padded.y1, padded.x2, padded.y2))


def preprocess_for_ocr(
    image: Image.Image,
    target_height: int = 64,
    median_filter_size: int = 3,
) -> bytes:
    """Lightweight preprocessing optimized for ddddocr classification.

    Unlike normalize_to_mask which produces aggressive binary masks for
    template matching, this preserves more grayscale detail suitable for
    the OCR model's neural network input.
    """
    gray = ImageOps.autocontrast(image.convert("L"), cutoff=3)
    if median_filter_size > 0:
        gray = gray.filter(ImageFilter.MedianFilter(size=median_filter_size))

    arr = np.array(gray, dtype=np.uint8)
    binary = cv2.adaptiveThreshold(
        arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 21, 8,
    )

    # Pad to square-ish aspect ratio for consistent OCR input
    h, w = binary.shape
    if w > h:
        pad = (w - h) // 2
        binary = cv2.copyMakeBorder(binary, pad, pad, 0, 0, cv2.BORDER_CONSTANT, value=0)
    elif h > w:
        pad = (h - w) // 2
        binary = cv2.copyMakeBorder(binary, 0, 0, pad, pad, cv2.BORDER_CONSTANT, value=0)

    # Resize to target height
    h2, w2 = binary.shape
    scale = target_height / float(h2)
    new_w = max(16, int(round(w2 * scale)))
    resized = cv2.resize(binary, (new_w, target_height), interpolation=cv2.INTER_AREA)

    result = Image.fromarray(resized).convert("RGB")
    return image_to_bytes(result)


def otsu_threshold(gray: np.ndarray) -> int:
    hist = np.bincount(gray.ravel(), minlength=256)
    total = gray.size
    sum_total = float(np.dot(np.arange(256), hist))
    sum_bg = 0.0
    weight_bg = 0.0
    best_t = 127
    best_var = -1.0
    for t in range(256):
        weight_bg += hist[t]
        if weight_bg == 0:
            continue
        weight_fg = total - weight_bg
        if weight_fg == 0:
            break
        sum_bg += t * hist[t]
        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_total - sum_bg) / weight_fg
        var_between = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if var_between > best_var:
            best_var = var_between
            best_t = t
    return best_t


def _crop_foreground(mask: np.ndarray) -> np.ndarray:
    ys, xs = np.where(mask > 0)
    if len(xs) < 8:
        return mask
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()
    return mask[y0 : y1 + 1, x0 : x1 + 1]


def _center_to_canvas(mask: np.ndarray, canvas_size: int = 96, target_size: int = 72) -> np.ndarray:
    h, w = mask.shape
    scale = target_size / float(max(h, w))
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    resized = cv2.resize(mask, (nw, nh), interpolation=cv2.INTER_NEAREST)
    canvas = np.zeros((canvas_size, canvas_size), dtype=np.uint8)
    ox = (canvas_size - nw) // 2
    oy = (canvas_size - nh) // 2
    canvas[oy : oy + nh, ox : ox + nw] = resized
    return canvas


def normalize_to_mask(image: Image.Image) -> np.ndarray:
    gray = ImageOps.autocontrast(image.convert("L"))
    gray = gray.filter(ImageFilter.MedianFilter(size=3))
    arr = np.array(gray, dtype=np.uint8)
    t_otsu = otsu_threshold(arr)

    candidates: list[np.ndarray] = []
    for t in (t_otsu, 90, 110, 130, 150, 170):
        fg_black = (arr < t).astype(np.uint8)
        candidates.append(fg_black)
        candidates.append(1 - fg_black)

    best = candidates[0]
    best_cost = float("inf")
    target_fg = 0.16
    for c in candidates:
        ratio = float(c.mean())
        penalty = 0.0 if 0.02 <= ratio <= 0.60 else 1.0
        cost = abs(ratio - target_fg) + penalty
        if cost < best_cost:
            best = c
            best_cost = cost

    cropped = _crop_foreground(best)
    centered = _center_to_canvas(cropped)
    return (centered > 0).astype(np.uint8)
