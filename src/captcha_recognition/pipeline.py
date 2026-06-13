from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal
import re

from .detector import BoxDetector
from .matcher import TemplateMatcher
from .ocr import OcrRecognizer
from .types import Candidate, Click, MatchResult, OcrResult, RecognitionResult, VerifyResult

logger = logging.getLogger(__name__)

Mode = Literal["ocr", "match", "fuse"]


class CaptchaRecognizer:
    def __init__(
        self,
        ocr_weight: float = 0.6,
        match_weight: float = 0.4,
        pad_ratio: float = 0.15,
        show_ad: bool = False,
        ocr_min_conf: float = 0.55,
        match_min_score: float = 0.45,
        match_min_margin: float = 0.04,
        fill_min_score: float = 0.42,
        matcher_iou_weight: float = 0.5,
        matcher_ncc_weight: float = 0.3,
        matcher_shape_weight: float = 0.2,
        matcher_rotation_angles: tuple[float, ...] = (-20, -10, 0, 10, 20),
        matcher_augment: bool = True,
        ocr_use_preprocess: bool = True,
        ocr_target_height: int = 64,
        ocr_median_filter: int = 3,
        verify_min_conf: float = 0.72,
        verify_ocr_conflict_conf: float = 0.80,
        verify_ocr_agree_conf: float = 0.60,
    ) -> None:
        self.ocr_weight = ocr_weight
        self.match_weight = match_weight
        self.detector = BoxDetector(show_ad=show_ad)
        self.ocr = OcrRecognizer(
            show_ad=show_ad, beta=True,
            use_ocr_preprocess=ocr_use_preprocess,
            ocr_target_height=ocr_target_height,
            ocr_median_filter=ocr_median_filter,
        )
        self.matcher = TemplateMatcher(
            pad_ratio=pad_ratio,
            iou_weight=matcher_iou_weight,
            ncc_weight=matcher_ncc_weight,
            shape_weight=matcher_shape_weight,
            rotation_angles=matcher_rotation_angles,
            augment_templates=matcher_augment,
        )
        self.pad_ratio = pad_ratio
        self.ocr_min_conf = ocr_min_conf
        self.match_min_score = match_min_score
        self.match_min_margin = match_min_margin
        self.fill_min_score = fill_min_score
        self.verify_min_conf = verify_min_conf
        self.verify_ocr_conflict_conf = verify_ocr_conflict_conf
        self.verify_ocr_agree_conf = verify_ocr_agree_conf

    def _fuse_score(self, ocr_conf: float, match_score: float) -> float:
        s = self.ocr_weight * ocr_conf + self.match_weight * match_score
        return float(max(0.0, min(1.0, s)))

    def _best_unique_assignment(
        self,
        match_results: list[MatchResult],
        known_chars: list[str],
    ) -> dict[int, tuple[str, float]]:
        """Greedy unique assignment: each char assigned to at most one box.

        Sorts all (box, char, score) tuples descending by score, then
        greedily picks the best available (box, char) pair that doesn't
        violate uniqueness constraints.  O(n*m*log(n*m)) vs the old
        exhaustive O(C(n,k)*P(n,k)).
        """
        if not match_results or not known_chars:
            return {}
        n_chars = len(known_chars)
        k = min(len(match_results), n_chars)
        if k == 0:
            return {}

        pairs: list[tuple[float, int, str]] = []
        for bi, mr in enumerate(match_results):
            for ch in known_chars:
                s = mr.scores.get(ch, 0.0)
                pairs.append((s, bi, ch))
        pairs.sort(key=lambda x: x[0], reverse=True)

        assign: dict[int, tuple[str, float]] = {}
        used_boxes: set[int] = set()
        used_chars: set[str] = set()
        for score, bi, ch in pairs:
            if len(assign) >= k:
                break
            if bi in used_boxes or ch in used_chars:
                continue
            assign[bi] = (ch, score)
            used_boxes.add(bi)
            used_chars.add(ch)
        return assign

    def _is_cjk(self, text: str) -> bool:
        if not text or len(text) != 1:
            return False
        return bool(re.match(r"[\u4e00-\u9fff]", text))

    def _top2(self, scores: dict[str, float]) -> tuple[tuple[str, float], tuple[str, float]]:
        if not scores:
            return ("", 0.0), ("", 0.0)
        ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if len(ordered) == 1:
            return ordered[0], ("", 0.0)
        return ordered[0], ordered[1]

    def _decide_once(
        self,
        ocr_r: OcrResult,
        match_r: MatchResult | None,
        known_chars: list[str],
    ) -> tuple[str, float, str]:
        ocr_text = (ocr_r.text or "").strip()
        ocr_valid = (
            (ocr_text in known_chars)
            and self._is_cjk(ocr_text)
            and (ocr_r.confidence >= self.ocr_min_conf)
        )

        m_char = ""
        m_score = 0.0
        m_margin = 0.0
        if match_r and match_r.scores:
            (m_char, m_score), (_, m2) = self._top2(match_r.scores)
            m_margin = m_score - m2
        match_valid = bool(m_char) and (m_score >= self.match_min_score) and (m_margin >= self.match_min_margin)

        if ocr_valid and match_valid:
            if ocr_text == m_char:
                return ocr_text, self._fuse_score(ocr_r.confidence, m_score), "fuse_agree"
            # Conflict: favour match when its margin is decisive, since
            # ddddocr confidence values are poorly calibrated on these
            # captcha glyphs whereas template-match scores are stable.
            if m_margin >= 0.10:
                return m_char, m_score, "fuse_match_win"
            if m_score >= 0.55:
                return m_char, m_score, "fuse_match_win"
            # OCR only wins if its confidence is exceptionally high and
            # match is marginal.
            if ocr_r.confidence >= 0.95 and m_score < 0.50:
                return ocr_text, ocr_r.confidence, "fuse_ocr_win"
            # Otherwise reject — neither source is trustworthy enough.
            return "", m_score * 0.5, "fuse_uncertain"

        if ocr_valid:
            return ocr_text, ocr_r.confidence, "ocr_only"
        if match_valid:
            return m_char, m_score, "match_only"
        return "", 0.0, "noise"

    def recognize(
        self,
        image: str | Path | bytes,
        known_chars: list[str] | None = None,
        target_count: int = 4,
        mode: Mode = "fuse",
    ) -> RecognitionResult:
        if mode not in ("ocr", "match", "fuse"):
            raise ValueError(f"Unsupported mode: {mode}")

        warnings: list[str] = []
        boxes = self.detector.detect(image)
        ocr_results = self.ocr.recognize_many(
            image,
            boxes,
            pad_ratio=self.pad_ratio,
            known_chars=known_chars,
        )

        match_results = [None] * len(boxes)
        if mode in ("match", "fuse") and known_chars:
            match_results = self.matcher.match_many(image, boxes, known_chars)
        elif mode in ("match", "fuse"):
            warnings.append("mode 需要 known_chars，已退化为 OCR 结果")

        all_candidates: list[Candidate] = []
        unique_assign: dict[int, tuple[str, float]] = {}
        if mode == "match" and known_chars:
            unique_assign = self._best_unique_assignment(match_results, known_chars)

        for idx, box in enumerate(boxes):
            ocr_r = ocr_results[idx]
            match_r = match_results[idx] if idx < len(match_results) else None

            if mode == "ocr" or not known_chars:
                all_candidates.append(
                    Candidate(
                        box_index=idx,
                        box=box,
                        text=ocr_r.text,
                        confidence=ocr_r.quality_score,
                        source="ocr",
                        ocr=ocr_r,
                        match=match_r,
                    )
                )
                continue

            if mode == "match":
                # 先做全局唯一分配，再做阈值过滤，避免重复字符和低质量硬匹配
                if idx in unique_assign:
                    text, conf = unique_assign[idx]
                    second = 0.0
                    if match_r and match_r.scores:
                        vals = sorted(match_r.scores.values(), reverse=True)
                        second = vals[1] if len(vals) > 1 else 0.0
                    margin = conf - second
                    if conf < self.match_min_score or margin < self.match_min_margin:
                        text, conf = "", 0.0
                else:
                    text, conf = "", 0.0
                all_candidates.append(
                    Candidate(
                        box_index=idx,
                        box=box,
                        text=text,
                        confidence=conf,
                        source="match",
                        ocr=ocr_r,
                        match=match_r,
                    )
                )
                continue

            # mode == fuse：单次融合决策（可拒识）
            text, conf, source = self._decide_once(ocr_r, match_r, known_chars)
            all_candidates.append(
                Candidate(
                    box_index=idx,
                    box=box,
                    text=text,
                    confidence=conf,
                    source=source,
                    ocr=ocr_r,
                    match=match_r,
                )
            )

        # 默认仅保留有文本的候选，避免 '?' + 0.000 干扰结果与标注
        selected = [c for c in all_candidates if (c.text or "").strip()]
        # 已知字符场景：字符去重，优先保留高置信度
        if known_chars and mode in ("match", "fuse"):
            dedup: list[Candidate] = []
            used_chars: set[str] = set()
            for c in sorted(selected, key=lambda x: x.confidence, reverse=True):
                if not c.text:
                    continue
                if c.text in used_chars:
                    continue
                dedup.append(c)
                used_chars.add(c.text)
            selected = dedup

            # 已知字符补位：若还有缺失字符，从未使用 bbox 中按该字符 match 分数补齐
            used_boxes = {tuple(c.box.as_list()) for c in selected}
            missing_chars = [ch for ch in known_chars if ch not in used_chars]
            for miss in missing_chars:
                best_idx = -1
                best_score = -1.0
                for idx, cand in enumerate(all_candidates):
                    if tuple(cand.box.as_list()) in used_boxes:
                        continue
                    if not cand.match:
                        continue
                    s = cand.match.scores.get(miss, 0.0)
                    if s > best_score:
                        best_score = s
                        best_idx = idx
                if best_idx >= 0 and best_score >= self.fill_min_score:
                    base = all_candidates[best_idx]
                    filled = Candidate(
                        box_index=base.box_index,
                        box=base.box,
                        text=miss,
                        confidence=float(best_score),
                        source=f"{base.source}_fill",
                        ocr=base.ocr,
                        match=base.match,
                    )
                    selected.append(filled)
                    used_chars.add(miss)
                    used_boxes.add(tuple(base.box.as_list()))

        if len(selected) > target_count:
            selected = sorted(selected, key=lambda c: c.confidence, reverse=True)[:target_count]
            selected = sorted(selected, key=lambda c: c.box.x1)
        elif len(selected) < target_count:
            msg = f"识别结果数量 {len(selected)} 小于目标数量 {target_count}"
            warnings.append(msg)
            logger.warning(msg)

        return RecognitionResult(
            boxes=boxes,
            selected=selected,
            all_candidates=all_candidates,
            target_count=target_count,
            mode=mode,
            warnings=warnings,
        )

    def _gate_click(self, cand: Candidate | None, word: str) -> Click:
        """Cross-method consistency gate deciding if a click is trustworthy.

        Rejects when OCR confidently reads a different glyph (the distractor
        signature); accepts outright when OCR independently agrees; otherwise
        falls back to the fused confidence threshold.
        """
        if cand is None or not cand.text:
            return Click(word=word, box=None, confidence=0.0, accepted=False, reason="not_found")

        ocr_text = (cand.ocr.text or "").strip() if cand.ocr else ""
        ocr_conf = cand.ocr.confidence if cand.ocr else 0.0

        if ocr_text and ocr_text != word and ocr_conf >= self.verify_ocr_conflict_conf:
            return Click(word=word, box=cand.box, confidence=cand.confidence, accepted=False, reason="ocr_conflict")
        if ocr_text == word and ocr_conf >= self.verify_ocr_agree_conf:
            return Click(word=word, box=cand.box, confidence=cand.confidence, accepted=True, reason="ocr_agree")
        if cand.confidence >= self.verify_min_conf:
            return Click(word=word, box=cand.box, confidence=cand.confidence, accepted=True, reason="conf_ok")
        return Click(word=word, box=cand.box, confidence=cand.confidence, accepted=False, reason="low_conf")

    def verify(self, image: str | Path | bytes, word_list: list[str]) -> VerifyResult:
        """Locate each word in word_list order and gate every click locally.

        Maps fused recognition back to the requested words by char identity, so
        distractor glyphs fall out naturally. ``complete`` is True only when all
        words pass the consistency gate, signalling the result is safe to submit.
        """
        result = self.recognize(image, known_chars=word_list, target_count=len(word_list), mode="fuse")
        by_word: dict[str, Candidate] = {}
        for c in sorted(result.selected, key=lambda c: c.confidence, reverse=True):
            if c.text and c.text not in by_word:
                by_word[c.text] = c

        clicks = [self._gate_click(by_word.get(word), word) for word in word_list]
        return VerifyResult(word_list=word_list, clicks=clicks, complete=all(c.accepted for c in clicks))
