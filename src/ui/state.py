from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from src.parsers.slot_filter import SlotChoice, SlotSolution


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
class LoginFormState:
    profile_name: str
    username: str = ""
    persist_auth: bool = True


@dataclass
class BoardCell:
    space_id: int
    space_name: str
    time_id: int
    begin_time: str
    end_time: str
    label: str
    reservation_status: int
    selectable: bool
    fee: float = 0.0

    @property
    def is_available(self) -> bool:
        return self.reservation_status == 1

    @property
    def status_text(self) -> str:
        if self.reservation_status == 1:
            return "空闲"
        if self.reservation_status == 2:
            return "系统锁定"
        if self.reservation_status == 3:
            return "待付款"
        if self.reservation_status == 4:
            return "已预定"
        return "未知"

    @property
    def range_blocked(self) -> bool:
        return self.reservation_status == 1 and not self.selectable


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
    solutions: list[SlotSolution] = field(default_factory=list)
    time_headers: list[str] = field(default_factory=list)
    available_dates: list[str] = field(default_factory=list)
    campus_name: str = ""
    venue_name: str = ""
    site_name: str = ""
    runtime_phone: str = ""
    available_buddies: list["BuddyOption"] = field(default_factory=list)
    buddy_num_min: int = 0
    buddy_num_max: int = 0
    message: str = ""
    last_sync_at: str = ""

    @property
    def recommended_solution(self) -> SlotSolution | None:
        return self.solutions[0] if self.solutions else None


@dataclass
class SelectionState:
    choices: list[SlotChoice] = field(default_factory=list)

    @property
    def step_index(self) -> int:
        return len(self.choices)


@dataclass
class ReserveOutcome:
    success: bool
    message: str
    trade_no: str = ""
    order_id: int = 0
    reservation_start_date: str = ""
    reservation_end_date: str = ""
    profile_name: str = ""
    display_name: str = ""
    payment_target: str = ""
    payment_message: str = ""


@dataclass
class BookingFormState:
    date: str = ""
    start_time: str = ""
    slot_count: int = 2
    venue_site_id: int = 57


@dataclass
class BuddyOption:
    id: str
    name: str = ""


@dataclass
class VenueCatalogItem:
    venue_site_id: int
    site_name: str
    venue_name: str
    campus_name: str


@dataclass
class VenueCatalogState:
    profile_name: str
    items: list[VenueCatalogItem] = field(default_factory=list)


@dataclass
class SettingsFormState:
    profile_name: str
    display_name: str = ""
    phone: str = ""
    buddy_ids: str = ""
    selection_strategy: str = "same_first_digit,same_venue,cheapest"
    venue_site_id: int = 57
    default_search_date: str = ""
    start_time: str = ""
    slot_count: int = 2


@dataclass
class PollingConfigState:
    start_time: str = ""
    interval_sec: int = 30


@dataclass
class PollingState:
    status: PollingStatus = PollingStatus.STOPPED
    interval_sec: int = 8
    last_checked_at: str = ""
    last_message: str = "未启动"
