"""Parse website init (catalog) API response. Pure functions on dict, no I/O."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.parsers.common import get_by_path


@dataclass
class SportItem:
    id: int
    code_key: str
    code_name: str


@dataclass
class SiteItem:
    site_id: int  # 即 venueSiteId
    site_name: str
    venue_name: str
    campus_name: str
    venue_id: Optional[int] = None


@dataclass
class CatalogParsed:
    sports: List[SportItem]
    sites: List[SiteItem]


def parse_sport_list(data: Dict[str, Any]) -> List[SportItem]:
    raw_list = get_by_path(data, "sportList") or []
    out: List[SportItem] = []
    if not isinstance(raw_list, list):
        return out
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        sid = item.get("id")
        if sid is None:
            continue
        out.append(
            SportItem(
                id=int(sid),
                code_key=str(item.get("codekey") or ""),
                code_name=str(item.get("codename") or ""),
            )
        )
    return out


def parse_sites_from_venue_list(data: Dict[str, Any]) -> List[SiteItem]:
    venue_list = get_by_path(data, "venueList") or []
    out: List[SiteItem] = []
    if not isinstance(venue_list, list):
        return out
    for venue in venue_list:
        if not isinstance(venue, dict):
            continue
        venue_id_raw = venue.get("venueId")
        venue_id = int(venue_id_raw) if venue_id_raw is not None else None
        site_list = venue.get("siteList") or []
        if not isinstance(site_list, list):
            continue
        for s in site_list:
            if not isinstance(s, dict):
                continue
            site_id = s.get("siteId")
            if site_id is None:
                continue
            out.append(
                SiteItem(
                    site_id=int(site_id),
                    site_name=str(s.get("siteName") or ""),
                    venue_name=str(s.get("venueName") or ""),
                    campus_name=str(s.get("campusName") or ""),
                    venue_id=venue_id,
                )
            )
    return out


def parse_catalog_data(data: Dict[str, Any]) -> CatalogParsed:
    """Parse the data section of website init response."""
    return CatalogParsed(
        sports=parse_sport_list(data),
        sites=parse_sites_from_venue_list(data),
    )


def parse_catalog_response(resp: Dict[str, Any]) -> tuple[bool, str, Optional[CatalogParsed]]:
    """Parse full response. Returns (success, message, parsed_or_none)."""
    from src.parsers.common import parse_success_message

    success, message = parse_success_message(resp)
    data = resp.get("data") if isinstance(resp.get("data"), dict) else None
    parsed = parse_catalog_data(data) if success and data else None
    return success, message, parsed
