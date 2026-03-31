"""Shared parsing utilities: path access and unified success/message extraction."""

from typing import Any, Dict, Tuple


def get_by_path(obj: Any, path: str, default: Any = None) -> Any:
    """Get nested value by dot path, e.g. 'data.reservationDateList'. Returns default if any key missing."""
    for key in path.split("."):
        if obj is None or not isinstance(obj, dict):
            return default
        obj = obj.get(key)
    return obj if obj is not None else default


def parse_success_message(resp: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Unified success + message from API response.
    Handles code==200, repCode==\"0000\", success flag; message from message/repMsg/data.repMsg.
    """
    data = resp.get("data") or {}
    if not isinstance(data, dict):
        data = {}
    success = (
        resp.get("code") == 200
        or resp.get("repCode") == "0000"
        or resp.get("success", False)
        or data.get("success", False)
        or data.get("repCode") == "0000"
    )
    msg = (
        resp.get("message")
        or resp.get("msg")
        or resp.get("repMsg")
        or data.get("repMsg")
        or data.get("msg")
        or data.get("message")
        or ""
    )
    return (bool(success), str(msg) if msg is not None else "")
