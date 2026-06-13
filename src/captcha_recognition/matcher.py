from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .preprocess import crop_box, normalize_to_mask, load_pil_image
from .types import Box, MatchResult


def _candidate_font_paths() -> list[Path]:
    candidates = [
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
        Path("/System/Library/Fonts/STHeiti Medium.ttc"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
    ]
    return [p for p in candidates if p.exists()]


def _largest_contour(mask: np.ndarray):
    binary = (mask * 255).astype(np.uint8)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    return max(contours, key=cv2.contourArea)


def _score_masks(
    roi_mask: np.ndarray,
    tpl_mask: np.ndarray,
    iou_weight: float = 0.5,
    ncc_weight: float = 0.3,
    shape_weight: float = 0.2,
) -> float:
    inter = np.logical_and(roi_mask, tpl_mask).sum()
    union = np.logical_or(roi_mask, tpl_mask).sum()
    iou = float(inter / union) if union > 0 else 0.0

    rv = roi_mask.astype(np.float32).ravel()
    tv = tpl_mask.astype(np.float32).ravel()
    rv -= rv.mean()
    tv -= tv.mean()
    denom = (np.linalg.norm(rv) * np.linalg.norm(tv)) + 1e-6
    ncc = float(np.dot(rv, tv) / denom)
    ncc = (ncc + 1.0) / 2.0

    rc = _largest_contour(roi_mask)
    tc = _largest_contour(tpl_mask)
    if rc is not None and tc is not None:
        dist = cv2.matchShapes(rc, tc, cv2.CONTOURS_MATCH_I1, 0)
        shape_score = 1.0 / (1.0 + float(dist))
    else:
        shape_score = 0.0

    return float(max(0.0, min(1.0, iou_weight * iou + ncc_weight * ncc + shape_weight * shape_score)))


def _augment_masks(mask: np.ndarray) -> list[np.ndarray]:
    """Generate eroded/dilated variants to match captcha rendering artifacts."""
    binary = (mask * 255).astype(np.uint8)
    results = [mask]
    for ksize in (3, 5):
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))
        eroded = cv2.erode(binary, kernel, iterations=1)
        results.append((eroded > 127).astype(np.uint8))
        dilated = cv2.dilate(binary, kernel, iterations=1)
        results.append((dilated > 127).astype(np.uint8))
    return results


def _rotate_mask(mask: np.ndarray, angle_deg: float) -> np.ndarray:
    if abs(angle_deg) < 1e-6:
        return mask
    h, w = mask.shape
    center = (w / 2.0, h / 2.0)
    mat = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    rotated = cv2.warpAffine(
        (mask * 255).astype(np.uint8),
        mat,
        (w, h),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    return (rotated > 127).astype(np.uint8)


@lru_cache(maxsize=512)
def _build_templates(char: str) -> tuple[np.ndarray, ...]:
    seen: set[bytes] = set()
    out: list[np.ndarray] = []
    for fp in _candidate_font_paths():
        for size in (28, 32, 36, 40, 44, 48, 52, 56):
            for sw in (0, 1):
                try:
                    font = ImageFont.truetype(str(fp), size=size)
                except OSError:
                    continue
                canvas = Image.new("L", (128, 128), color=255)
                draw = ImageDraw.Draw(canvas)
                x0, y0, x1, y1 = draw.textbbox((0, 0), char, font=font, stroke_width=sw)
                tw, th = x1 - x0, y1 - y0
                pos = ((128 - tw) // 2 - x0, (128 - th) // 2 - y0)
                draw.text(pos, char, fill=0, font=font, stroke_width=sw, stroke_fill=0)
                mask = normalize_to_mask(canvas)
                key = mask.tobytes()
                if key not in seen:
                    seen.add(key)
                    out.append(mask)
    if not out:
        fallback = Image.new("L", (128, 128), color=255)
        draw = ImageDraw.Draw(fallback)
        draw.text((48, 40), char, fill=0)
        out.append(normalize_to_mask(fallback))
    return tuple(out)


class TemplateMatcher:
    def __init__(
        self,
        pad_ratio: float = 0.15,
        iou_weight: float = 0.5,
        ncc_weight: float = 0.3,
        shape_weight: float = 0.2,
        rotation_angles: tuple[float, ...] = (-20, -10, 0, 10, 20),
        augment_templates: bool = True,
    ) -> None:
        self.pad_ratio = pad_ratio
        self.iou_weight = iou_weight
        self.ncc_weight = ncc_weight
        self.shape_weight = shape_weight
        self.rotation_angles = rotation_angles
        self.augment_templates = augment_templates

    def match(self, image: str | Path | bytes | Image.Image, box: Box, known_chars: list[str]) -> MatchResult:
        roi = crop_box(load_pil_image(image), box, pad_ratio=self.pad_ratio)
        roi_mask = normalize_to_mask(roi)
        roi_rots = [_rotate_mask(roi_mask, a) for a in self.rotation_angles]
        scores: dict[str, float] = {}
        for ch in known_chars:
            best = 0.0
            tpls = _build_templates(ch)
            for tpl in tpls:
                tpl_variants = _augment_masks(tpl) if self.augment_templates else [tpl]
                for tvar in tpl_variants:
                    for rmask in roi_rots:
                        s = _score_masks(rmask, tvar, self.iou_weight, self.ncc_weight, self.shape_weight)
                        if s > best:
                            best = s
            scores[ch] = best
        if not scores:
            return MatchResult(scores={}, best_char="", best_score=0.0)
        best_char = max(scores, key=scores.get)
        return MatchResult(scores=scores, best_char=best_char, best_score=scores[best_char])

    def match_many(
        self,
        image: str | Path | bytes | Image.Image,
        boxes: list[Box],
        known_chars: list[str],
    ) -> list[MatchResult]:
        pil = load_pil_image(image)
        return [self.match(pil, b, known_chars) for b in boxes]
