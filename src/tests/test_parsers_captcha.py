"""Test captcha parser with local JSON only (no requests)."""

from __future__ import annotations

import json
from pathlib import Path

from src.parsers.captcha import (parse_captcha_data, parse_captcha_response,
                                 parse_check_captcha_data,
                                 parse_check_captcha_response)


def _load_fixture(name: str) -> dict:
    root = Path(__file__).resolve().parents[2]
    with (root / "docs/responses" / name).open(encoding="utf-8") as f:
        return json.load(f)


def test_parse_captcha_data() -> None:
    raw = _load_fixture("get_captcha.json")
    data = raw.get("data", {})
    parsed = parse_captcha_data(data)
    assert parsed is not None
    assert parsed.secret_key
    assert parsed.token
    assert parsed.word_list
    assert parsed.original_image_base64.startswith("iVBORw")


def test_parse_captcha_response() -> None:
    raw = _load_fixture("get_captcha.json")
    success, message, parsed = parse_captcha_response(raw)
    assert success is True
    assert parsed is not None
    assert parsed.word_list == ["后", "团", "世"]


def test_parse_check_captcha_data() -> None:
    raw = _load_fixture("check_captcha.json")
    data = raw.get("data", {})
    parsed = parse_check_captcha_data(data)
    assert parsed is not None
    assert parsed.result is True


def test_parse_check_captcha_response() -> None:
    raw = _load_fixture("check_captcha.json")
    success, message, parsed = parse_check_captcha_response(raw)
    print(parsed)
    assert success is True
    assert parsed is not None
    assert parsed.result is True


if __name__ == "__main__":
    test_parse_captcha_data()
    print("parse_captcha_data: ok")
    test_parse_captcha_response()
    print("parse_captcha_response: ok")
    test_parse_check_captcha_data()
    print("parse_check_captcha_data: ok")
    test_parse_check_captcha_response()
    print("parse_check_captcha_response: ok")
