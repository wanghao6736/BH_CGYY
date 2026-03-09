"""
Test info parsers and slot_filter using local JSON only (no requests).
Run from project root: python -m src.tests.test_parsers_info
"""

from __future__ import annotations

import json
from pathlib import Path

from src.parsers.day_info import parse_info_data, parse_info_response
from src.parsers.slot_filter import find_solutions


def _load_fixture(name: str) -> dict:
    root = Path(__file__).resolve().parents[2]
    path = root / "docs" / name
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def test_parse_info_from_data_section() -> None:
    """Parse using only the 'data' section (simulate loading from file)."""
    raw = _load_fixture("get_info.json")
    data = raw.get("data", {})
    parsed = parse_info_data(data)
    assert len(parsed.reservation_date_list) >= 1
    assert len(parsed.time_slots) >= 1
    assert parsed.time_slots[0].begin_time == "08:00"
    assert len(parsed.space_schedules_by_date) >= 1
    date_key = list(parsed.space_schedules_by_date.keys())[0]
    spaces = parsed.space_schedules_by_date[date_key]
    assert len(spaces) >= 1
    assert hasattr(spaces[0], "space_id") and hasattr(spaces[0], "slots")
    if parsed.order_param_view:
        assert parsed.order_param_view.phone
        assert len(parsed.order_param_view.buddy_list) >= 0
    if parsed.site_param:
        assert parsed.site_param.site_name or parsed.site_param.venue_name


def test_parse_info_full_response() -> None:
    """Parse full response (success + message + data)."""
    raw = _load_fixture("get_info.json")
    success, message, parsed = parse_info_response(raw)
    assert success is True
    assert parsed is not None
    assert len(parsed.reservation_date_list) >= 1


def test_find_solutions() -> None:
    """Find slots for 12:00, 1 slot; each solution has choices + total_fee + slot_count + total_hours."""
    raw = _load_fixture("get_info.json")
    data = raw.get("data", {})
    parsed = parse_info_data(data)
    date = parsed.reservation_date_list[0] if parsed.reservation_date_list else "2026-03-06"
    solutions = find_solutions(
        parsed, date=date, start_time="12:00", slot_count=1
    )
    for sol in solutions:
        assert len(sol.choices) == 1
        assert sol.slot_count == 1
        assert sol.total_hours > 0
        assert sol.total_fee == sum(c.order_fee for c in sol.choices)
        for choice in sol.choices:
            assert choice.space_id and choice.time_id
            assert choice.start_time and choice.end_time


if __name__ == "__main__":
    test_parse_info_from_data_section()
    print("parse_info_data: ok")
    test_parse_info_full_response()
    print("parse_info_response: ok")
    test_find_solutions()
    print("find_solutions: ok")
