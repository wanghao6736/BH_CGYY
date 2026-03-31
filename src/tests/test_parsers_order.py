"""Test submit & order_detail parsers with local JSON only (no requests)."""

from __future__ import annotations

import json
from pathlib import Path

from src.parsers.order import (parse_order_detail_data,
                               parse_order_detail_response, parse_submit_data,
                               parse_submit_response)


def _load_fixture(name: str) -> dict:
    root = Path(__file__).resolve().parents[2]
    with (root / "docs/responses" / name).open(encoding="utf-8") as f:
        return json.load(f)


def test_parse_submit_data() -> None:
    raw = _load_fixture("submit.json")
    data = raw.get("data", {})
    parsed = parse_submit_data(data)
    assert parsed is not None
    assert parsed.order_id == 760907
    assert parsed.trade_no == "D260306000729"
    assert "2026-03-07 11:00" in parsed.reservation_start_date
    assert "2026-03-07 13:00" in parsed.reservation_end_date


def test_parse_submit_response() -> None:
    raw = _load_fixture("submit.json")
    success, message, parsed = parse_submit_response(raw)
    assert success is True
    assert parsed is not None
    assert parsed.order_id == 760907


def test_parse_order_detail_data() -> None:
    raw = _load_fixture("order_detail.json")
    data = raw.get("data", {})
    parsed = parse_order_detail_data(data)
    assert parsed is not None
    assert parsed.order_id == 760907
    assert parsed.pay_user_id == 41369
    assert parsed.order_status == 2
    assert parsed.pay_status == 1
    assert parsed.pay_fee == 70.0
    assert parsed.gmt_create and parsed.expire_time
    assert parsed.subject == "沙河校区综合馆羽毛球"
    assert parsed.start_date == "2026-03-07 11:00:00"
    assert len(parsed.space_list) == 2
    assert parsed.space_list[0].venue_space_id == 239
    assert parsed.space_list[0].space_name == "7号"
    assert parsed.space_list[0].order_fee == 35.0
    assert parsed.space_list[0].order_uuid


def test_parse_order_detail_response() -> None:
    raw = _load_fixture("order_detail.json")
    success, message, parsed = parse_order_detail_response(raw)
    assert success is True
    assert parsed is not None
    assert parsed.order_uuid and len(parsed.space_list) == 2


if __name__ == "__main__":
    test_parse_submit_data()
    print("parse_submit_data: ok")
    test_parse_submit_response()
    print("parse_submit_response: ok")
    test_parse_order_detail_data()
    print("parse_order_detail_data: ok")
    test_parse_order_detail_response()
    print("parse_order_detail_response: ok")
