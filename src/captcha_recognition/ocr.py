from __future__ import annotations

from pathlib import Path

import ddddocr

from .preprocess import crop_box, image_to_bytes, load_pil_image, preprocess_for_ocr
from .types import Box, OcrResult


class OcrRecognizer:
    def __init__(
        self,
        show_ad: bool = False,
        beta: bool = True,
        use_ocr_preprocess: bool = True,
        ocr_target_height: int = 64,
        ocr_median_filter: int = 3,
    ) -> None:
        self.ocr = ddddocr.DdddOcr(show_ad=show_ad, beta=beta)
        self.use_ocr_preprocess = use_ocr_preprocess
        self.ocr_target_height = ocr_target_height
        self.ocr_median_filter = ocr_median_filter

    def _parse_probability_result(self, result: object) -> OcrResult:
        if isinstance(result, str):
            text = result.strip()
            conf = 0.0
            return OcrResult(text=text, confidence=conf, quality_score=conf, topk=[])

        if not isinstance(result, dict):
            return OcrResult(text="", confidence=0.0, quality_score=0.0, topk=[])

        text = str(result.get("text") or "").strip()
        conf = float(result.get("confidence") or 0.0)

        # 兼容旧版/新版结构，提取一个可读 top-k（不强依赖其语义）
        topk: list[tuple[str, float]] = []
        charset = result.get("charset") or result.get("charsets") or []
        probs = result.get("probabilities") or result.get("probability") or []
        if isinstance(charset, list) and probs and isinstance(probs, list) and isinstance(probs[0], list):
            first = probs[0]
            # 新版 ddddocr 结构常见为 [time][1][charset_size]
            if first and isinstance(first[0], list):
                first = first[0]
            idx_scores = sorted(
                ((i, float(v)) for i, v in enumerate(first)),
                key=lambda x: x[1],
                reverse=True,
            )[:5]
            for idx, score in idx_scores:
                if 0 <= idx < len(charset):
                    topk.append((str(charset[idx]), score))

        # 某些样本会出现 text 为空但 probabilities 可用，回退到 top-1
        if not text and topk:
            text, conf = topk[0]
        # 兜底：空文本不应有高置信度，避免后续排序误选
        if not text:
            conf = 0.0

        return OcrResult(text=text, confidence=conf, quality_score=conf, topk=topk)

    def _filter_against_known(self, result: OcrResult, known_chars: list[str]) -> OcrResult:
        if result.text in known_chars:
            return result
        # 从 top-k 中找在 known_chars 中置信度最高的字符
        best_ch = ""
        best_conf = 0.0
        for ch, prob in result.topk:
            if ch in known_chars and prob > best_conf:
                best_ch = ch
                best_conf = prob
        if best_ch:
            return OcrResult(
                text=best_ch,
                confidence=best_conf,
                quality_score=best_conf,
                topk=result.topk,
            )
        # topk 中也没有 known_chars，保留原始结果（后续融合阶段可拒识）
        return result

    def recognize(self, image: str | Path | bytes, box: Box, pad_ratio: float = 0.15) -> OcrResult:
        pil = load_pil_image(image)
        roi = crop_box(pil, box, pad_ratio=pad_ratio)
        if self.use_ocr_preprocess:
            inp = preprocess_for_ocr(roi, target_height=self.ocr_target_height, median_filter_size=self.ocr_median_filter)
        else:
            inp = image_to_bytes(roi)
        result = self.ocr.classification(inp, probability=True)
        parsed = self._parse_probability_result(result)
        if not parsed.text:
            # fallback，避免某些版本 probability=True 输出异常
            text = str(self.ocr.classification(inp) or "").strip()
            parsed.text = text
        return parsed

    def recognize_many(
        self,
        image: str | Path | bytes,
        boxes: list[Box],
        pad_ratio: float = 0.15,
        known_chars: list[str] | None = None,
    ) -> list[OcrResult]:
        pil = load_pil_image(image)
        results = [self.recognize(pil, b, pad_ratio=pad_ratio) for b in boxes]
        if known_chars:
            results = [self._filter_against_known(r, known_chars) for r in results]
        return results
