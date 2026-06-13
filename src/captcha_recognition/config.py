"""Default configuration for the captcha recognition pipeline.

These values are the starting point for further data-driven tuning
once enough labeled data is available.
"""

from __future__ import annotations

# ── Pipeline ──────────────────────────────────────────
OCR_WEIGHT = 0.6
MATCH_WEIGHT = 0.4
PAD_RATIO = 0.15

# ── Thresholds ─────────────────────────────────────────
OCR_MIN_CONF = 0.55
MATCH_MIN_SCORE = 0.45
MATCH_MIN_MARGIN = 0.04
FILL_MIN_SCORE = 0.42

# ── Template matching ──────────────────────────────────
MATCHER_IOU_WEIGHT = 0.5
MATCHER_NCC_WEIGHT = 0.3
MATCHER_SHAPE_WEIGHT = 0.2
MATCHER_ROTATION_ANGLES: tuple[float, ...] = (-20, -10, 0, 10, 20)
MATCHER_AUGMENT = True

# ── OCR preprocessing ──────────────────────────────────
OCR_USE_PREPROCESS = True
OCR_TARGET_HEIGHT = 64
OCR_MEDIAN_FILTER = 3

# ── Click verification ─────────────────────────────────
# A click is trusted when OCR independently agrees with the target, or when
# the fused confidence clears VERIFY_MIN_CONF and OCR does not confidently
# read a different char (the distractor signature).
VERIFY_MIN_CONF = 0.72
VERIFY_OCR_AGREE_CONF = 0.60
VERIFY_OCR_CONFLICT_CONF = 0.80
