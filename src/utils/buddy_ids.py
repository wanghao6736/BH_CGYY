from __future__ import annotations

from collections.abc import Sequence


def split_buddy_ids(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def clamp_buddy_ids(
    configured: Sequence[str],
    *,
    buddy_num_max: int = 0,
) -> list[str]:
    buddy_ids = [str(item).strip() for item in configured if str(item).strip()]
    if buddy_num_max > 0:
        return buddy_ids[:buddy_num_max]
    return buddy_ids


def supports_buddy_selection(
    *,
    buddy_num_min: int = 0,
    buddy_num_max: int = 0,
    available_buddy_count: int = 0,
) -> bool:
    return buddy_num_min > 0 or buddy_num_max > 0 or available_buddy_count > 0
