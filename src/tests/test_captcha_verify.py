from __future__ import annotations

import pytest

from src.captcha_recognition.pipeline import CaptchaRecognizer
from src.captcha_recognition.types import Box, Candidate, MatchResult, OcrResult
from src.config.settings import ApiSettings, UserSettings
from src.core.captcha_service import (CaptchaData, CaptchaVerification,
                                      CaptchaVerificationResult)
from src.core.exceptions import CaptchaError
from src.core.workflow import ReservationWorkflow


# --- _gate_click: the cross-method consistency gate -------------------------
#
# Built via object.__new__ so the test never loads the ddddocr models; the gate
# only reads the three verify_* thresholds.

def _gate(min_conf=0.72, conflict=0.80, agree=0.60) -> CaptchaRecognizer:
    r = object.__new__(CaptchaRecognizer)
    r.verify_min_conf = min_conf
    r.verify_ocr_conflict_conf = conflict
    r.verify_ocr_agree_conf = agree
    return r


def _cand(word, conf, ocr_text, ocr_conf) -> Candidate:
    return Candidate(
        box_index=0,
        box=Box(0, 0, 10, 10),
        text=word,
        confidence=conf,
        source="fuse",
        ocr=OcrResult(text=ocr_text, confidence=ocr_conf, quality_score=ocr_conf),
        match=MatchResult(scores={word: conf}, best_char=word, best_score=conf),
    )


def test_gate_rejects_when_ocr_reads_a_different_char() -> None:
    # The distractor signature: OCR confidently sees some OTHER glyph here.
    gate = _gate()
    click = gate._gate_click(_cand("山", conf=0.95, ocr_text="房", ocr_conf=0.95), "山")
    assert not click.accepted
    assert click.reason == "ocr_conflict"


def test_gate_accepts_on_ocr_agreement_even_below_conf_threshold() -> None:
    # OCR independently agrees -> trusted at a lower bar than min_conf.
    gate = _gate(min_conf=0.72)
    click = gate._gate_click(_cand("白", conf=0.50, ocr_text="白", ocr_conf=0.70), "白")
    assert click.accepted
    assert click.reason == "ocr_agree"


def test_gate_falls_back_to_confidence_threshold() -> None:
    gate = _gate(min_conf=0.72)
    # No OCR signal either way; fused conf clears the bar.
    ok = gate._gate_click(_cand("量", conf=0.80, ocr_text="", ocr_conf=0.0), "量")
    assert ok.accepted and ok.reason == "conf_ok"
    # Just under the bar -> abstain.
    low = gate._gate_click(_cand("量", conf=0.60, ocr_text="", ocr_conf=0.0), "量")
    assert not low.accepted and low.reason == "low_conf"


def test_gate_marks_missing_candidate_not_found() -> None:
    click = _gate()._gate_click(None, "或")
    assert not click.accepted and click.reason == "not_found" and click.box is None


# --- _verify_captcha_with_retry: dual budget --------------------------------

class _Captcha:
    """Scripted fake: each entry is "abstain" (raise), "reject" (submitted but
    wrong) or "ok" (submitted and accepted)."""

    def __init__(self, script: list[str]) -> None:
        self.script = list(script)
        self.fetches = 0
        self.submits = 0

    def fetch_captcha(self) -> CaptchaData:
        self.fetches += 1
        return CaptchaData(secret_key="s", token="t", word_list=["A"],
                           image_path="x.png")  # type: ignore[arg-type]

    def verify_captcha(self, data: CaptchaData) -> CaptchaVerificationResult:
        step = self.script.pop(0)
        if step == "abstain":
            raise CaptchaError("未能识别全部目标字符")
        self.submits += 1
        v = CaptchaVerification(point_json="p", verify_json="v")
        return CaptchaVerificationResult(success=(step == "ok"), message=step, verification=v)


def _workflow(captcha, retry_count=5, refetch_count=12) -> ReservationWorkflow:
    return ReservationWorkflow(
        captcha_service=captcha,  # type: ignore[arg-type]
        reservation_service=None,  # type: ignore[arg-type]  (unused by this method)
        delay_min=0.0,
        delay_max=0.0,
        api_settings=ApiSettings(retry_count=retry_count,
                                 captcha_refetch_count=refetch_count,
                                 retry_interval_sec=0.0),
        user_settings=UserSettings(profile_name="default"),
    )


def test_abstentions_do_not_consume_submit_budget() -> None:
    # Three local abstentions then a clean submit: must succeed, since each
    # abstention draws from the refetch budget, not the 5 submit attempts.
    cap = _Captcha(["abstain", "abstain", "abstain", "ok"])
    data, result = _workflow(cap, retry_count=5)._verify_captcha_with_retry()
    assert result.success
    assert cap.fetches == 4 and cap.submits == 1


def test_server_rejections_exhaust_submit_budget() -> None:
    # Every submit is rejected by the server -> stop after retry_count submits.
    cap = _Captcha(["reject"] * 10)
    with pytest.raises(CaptchaError):
        _workflow(cap, retry_count=3)._verify_captcha_with_retry()
    assert cap.submits == 3


def test_refetch_budget_caps_endless_abstention() -> None:
    cap = _Captcha(["abstain"] * 20)
    with pytest.raises(CaptchaError):
        _workflow(cap, retry_count=5, refetch_count=4)._verify_captcha_with_retry()
    assert cap.fetches == 4 and cap.submits == 0
