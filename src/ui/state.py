from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SessionStatus(Enum):
    UNAUTHENTICATED = "unauthenticated"
    PROBING = "probing"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"
    ERROR = "error"


class BoardStatus(Enum):
    IDLE = "idle"
    LOADING = "loading"
    READY = "ready"
    REFRESHING = "refreshing"
    ERROR = "error"


class PollingStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class ProfileOption:
    name: str
    display_name: str
    auth_source: str
    sso_source: str


@dataclass
class SessionState:
    profile_name: str
    display_name: str
    status: SessionStatus
    message: str = ""
    auth_source: str = ""


@dataclass
class BoardCell:
    space_id: int
    space_name: str
    time_id: int
    begin_time: str
    end_time: str
    label: str
    status_text: str
    selectable: bool
    is_available: bool
    fee: float = 0.0


@dataclass
class BoardRow:
    space_id: int
    space_name: str
    cells: list[BoardCell] = field(default_factory=list)


@dataclass
class BoardState:
    status: BoardStatus
    profile_name: str
    venue_site_id: int
    venue_label: str
    date: str
    slot_count: int
    start_time: str = ""
    rows: list[BoardRow] = field(default_factory=list)
    time_headers: list[str] = field(default_factory=list)
    message: str = ""
    last_sync_at: str = ""


@dataclass
class SelectionState:
    space_id: int
    space_name: str
    start_time: str
    end_time: str
    slot_count: int


@dataclass
class ReserveOutcome:
    success: bool
    message: str
    trade_no: str = ""
    order_id: int = 0


@dataclass
class SettingsFormState:
    profile_name: str
    display_name: str = ""
    phone: str = ""
    buddy_ids: str = ""
    venue_site_id: int = 57
    default_search_date: str = ""
    start_time: str = ""
    slot_count: int = 2


@dataclass
class PollingState:
    status: PollingStatus = PollingStatus.STOPPED
    interval_sec: int = 8
    last_checked_at: str = ""
    last_message: str = "未启动"
