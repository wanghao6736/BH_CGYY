from __future__ import annotations

import base64
import json
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from PIL import Image

from src.api.captcha_api import CaptchaApi
from src.captcha_recognition import CaptchaRecognizer
from src.captcha_recognition.types import Box
from src.core.exceptions import CaptchaError
from src.parsers.captcha import (parse_captcha_response,
                                 parse_check_captcha_response)
from src.utils.crypto_utils import AesEcbEncryptor

logger = logging.getLogger(__name__)

CAPTCHA_DIR = Path("CAPTCHA")
CAPTCHA_W, CAPTCHA_H = 310, 155


@dataclass
class CaptchaData:
    secret_key: str
    token: str
    word_list: List[str]
    image_path: Path


@dataclass
class CaptchaVerification:
    point_json: str
    verify_json: str


@dataclass
class CaptchaVerificationResult:
    success: bool
    message: str
    verification: CaptchaVerification


class CaptchaService:
    def __init__(self, api: CaptchaApi) -> None:
        self.api = api
        self.recognizer = CaptchaRecognizer()

    def fetch_captcha(self) -> CaptchaData:
        resp = self.api.get_captcha_raw()
        success, message, parsed = parse_captcha_response(resp)
        if not parsed:
            raise CaptchaError(f"解析验证码失败: {message}")
        image_path = self._decode_and_save_image(parsed.original_image_base64)
        return CaptchaData(
            secret_key=parsed.secret_key,
            token=parsed.token,
            word_list=parsed.word_list,
            image_path=image_path,
        )

    def _decode_and_save_image(self, image_base64: str) -> Path:
        CAPTCHA_DIR.mkdir(parents=True, exist_ok=True)
        if "base64," in image_base64:
            _, image_base64 = image_base64.split("base64,", 1)
        image_bytes = base64.b64decode(image_base64)
        image_path = CAPTCHA_DIR / f"captcha_{int(time.time())}.png"
        with image_path.open("wb") as f:
            f.write(image_bytes)
        return image_path

    def locate_positions(self, captcha_data: CaptchaData) -> List[Dict[str, int]]:
        word_list = list(captcha_data.word_list)
        if not word_list:
            return []
        with Image.open(captcha_data.image_path) as img:
            img_w, img_h = img.size
        verdict = self.recognizer.verify(captcha_data.image_path.read_bytes(), word_list)
        if not verdict.complete:
            breakdown = ", ".join(
                f"{c.word}={c.reason}({c.confidence:.2f})" for c in verdict.clicks
            )
            logger.warning("验证码本地拒识: %s", breakdown)
            raise CaptchaError(f"未能识别全部目标字符 [{breakdown}]")
        return [self._scale_click(c.box, img_w, img_h) for c in verdict.clicks]

    def _scale_click(self, box: Box, img_w: int, img_h: int) -> Dict[str, int]:
        cx = (box.x1 + box.x2) / 2 + random.uniform(-0.1 * box.width(), 0.1 * box.width())
        cy = (box.y1 + box.y2) / 2 + random.uniform(-0.1 * box.height(), 0.1 * box.height())
        return {
            "x": int(round(CAPTCHA_W * cx / img_w)),
            "y": int(round(CAPTCHA_H * cy / img_h)),
        }

    def build_verification(
        self, captcha_data: CaptchaData, positions: List[Dict[str, int]]
    ) -> CaptchaVerification:
        plaintext = json.dumps(positions, separators=(",", ":"))
        verify_text = f"{captcha_data.token}---{plaintext}"
        key_bytes = captcha_data.secret_key.encode("utf-8")
        encryptor = AesEcbEncryptor(key=key_bytes)
        point_json = encryptor.encrypt_base64(plaintext.encode("utf-8"))
        verify_json = encryptor.encrypt_base64(verify_text.encode("utf-8"))
        return CaptchaVerification(point_json=point_json, verify_json=verify_json)

    def verify_captcha(self, captcha_data: CaptchaData) -> CaptchaVerificationResult:
        positions = self.locate_positions(captcha_data)
        verification = self.build_verification(captcha_data, positions)
        resp = self.api.check_captcha(verification.point_json, captcha_data.token)
        ok, message, parsed = parse_check_captcha_response(resp)
        success = ok and (parsed.result if parsed else False)
        return CaptchaVerificationResult(
            success=success, message=message, verification=verification
        )
