from __future__ import annotations

import base64
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from src.api.captcha_api import CaptchaApi
from src.core.exceptions import CaptchaError
from src.parsers.captcha import (parse_captcha_response,
                                 parse_check_captcha_response)
from src.utils.char_locator import CharLocator, draw_boxes_with_chars
from src.utils.crypto_utils import AesEcbEncryptor

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
        locator = CharLocator()
        target_chars = list(captcha_data.word_list)
        if not target_chars:
            return []
        result = locator.locate_multiple_chars(str(captcha_data.image_path), target_chars)
        draw_boxes_with_chars(
            str(captcha_data.image_path),
            result["all_regions"],
            result.get("target_bbox"),
        )
        if not result["success"] or result["found_count"] != len(target_chars):
            raise CaptchaError("未能识别全部目标字符")
        check_pos_arr: List[Dict[str, int]] = []
        for fc in result["found_chars"]:
            x1, y1, x2, y2 = fc["bbox"]
            w, h = x2 - x1, y2 - y1
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            offset_x = random.uniform(-0.1 * w, 0.1 * w)
            offset_y = random.uniform(-0.1 * h, 0.1 * h)
            imgw, imgh = result["image_size"]["width"], result["image_size"]["height"]
            sx = CAPTCHA_W * (cx + offset_x) / imgw
            sy = CAPTCHA_H * (cy + offset_y) / imgh
            check_pos_arr.append(
                {
                    "x": int(round(sx)),
                    "y": int(round(sy)),
                }
            )
        return check_pos_arr

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
