"""Parse get_captcha API response. Pure functions on dict, no I/O."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from src.parsers.common import get_by_path, parse_success_message


@dataclass
class CaptchaParsed:
    secret_key: str
    token: str
    word_list: List[str]
    original_image_base64: str


def parse_captcha_data(data: dict) -> Optional[CaptchaParsed]:
    if not isinstance(data, dict):
        return None
    rep_data = get_by_path(data, "repData")
    if not isinstance(rep_data, dict):
        return None
    secret_key = rep_data.get("secretKey")
    token = rep_data.get("token")
    word_list = rep_data.get("wordList")
    original_image_base64 = rep_data.get("originalImageBase64")
    if secret_key is None or token is None or word_list is None or original_image_base64 is None:
        return None
    return CaptchaParsed(
        secret_key=str(secret_key),
        token=str(token),
        word_list=list(word_list) if isinstance(word_list, list) else [],
        original_image_base64=str(original_image_base64),
    )


def parse_captcha_response(resp: dict) -> tuple[bool, str, Optional[CaptchaParsed]]:
    success, message = parse_success_message(resp)
    data = resp.get("data") if isinstance(resp.get("data"), dict) else None
    parsed = parse_captcha_data(data) if success and data else None
    return success, message, parsed


@dataclass
class CheckCaptchaParsed:
    result: bool
    point_json: str
    token: str
    captcha_type: str


def parse_check_captcha_data(data: dict) -> Optional[CheckCaptchaParsed]:
    if not isinstance(data, dict):
        return None
    rep_data = get_by_path(data, "repData")
    if not isinstance(rep_data, dict):
        return None
    result = rep_data.get("result")
    point_json = rep_data.get("pointJson")
    token = rep_data.get("token")
    captcha_type = rep_data.get("captchaType")
    if result is None:
        return None
    return CheckCaptchaParsed(result=bool(result), point_json=str(point_json),
                              token=str(token), captcha_type=str(captcha_type))


def parse_check_captcha_response(resp: dict) -> tuple[bool, str, Optional[CheckCaptchaParsed]]:
    success, message = parse_success_message(resp)
    data = resp.get("data") if isinstance(resp.get("data"), dict) else None
    parsed = parse_check_captcha_data(data) if success and data else None
    return success, message, parsed
