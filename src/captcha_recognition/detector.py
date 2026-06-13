from __future__ import annotations

from pathlib import Path

import ddddocr

from .preprocess import image_to_bytes, load_pil_image
from .types import Box


class BoxDetector:
    def __init__(self, show_ad: bool = False) -> None:
        self.det = ddddocr.DdddOcr(det=True, ocr=False, show_ad=show_ad)

    def detect(self, image: str | Path | bytes) -> list[Box]:
        if isinstance(image, bytes):
            img_bytes = image
        else:
            img_bytes = image_to_bytes(load_pil_image(image))

        raw_boxes = self.det.detection(img_bytes) or []
        boxes: list[Box] = []
        for b in raw_boxes:
            if len(b) != 4:
                continue
            x1, y1, x2, y2 = [int(v) for v in b]
            if x2 > x1 and y2 > y1:
                boxes.append(Box(x1, y1, x2, y2))
        return boxes
