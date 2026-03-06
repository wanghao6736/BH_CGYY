"""
Test catalog (website init) parsers using local JSON only (no requests).
Run from project root: python -m src.tests.test_parsers_catalog
"""

from __future__ import annotations

import json
from pathlib import Path

from src.parsers.catalog import parse_catalog_data, parse_catalog_response


def _load_fixture(name: str) -> dict:
    root = Path(__file__).resolve().parents[2]
    path = root / "docs" / name
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def test_parse_catalog_from_data_section() -> None:
    raw = _load_fixture("catalog.json")
    data = raw.get("data", {})
    parsed = parse_catalog_data(data)
    assert len(parsed.sports) >= 1
    assert any(s.code_name == "羽毛球" for s in parsed.sports)
    assert len(parsed.sites) >= 1
    # The sample includes: siteId=39, siteName=羽毛球, campusName=学院路校区
    assert any(s.site_id == 39 and s.site_name == "羽毛球" for s in parsed.sites)


def test_parse_catalog_full_response() -> None:
    raw = _load_fixture("catalog.json")
    ok, msg, parsed = parse_catalog_response(raw)
    assert ok is True
    assert parsed is not None
    assert msg is not None


if __name__ == "__main__":
    test_parse_catalog_from_data_section()
    print("parse_catalog_data: ok")
    test_parse_catalog_full_response()
    print("parse_catalog_response: ok")
