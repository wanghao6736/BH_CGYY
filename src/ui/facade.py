from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from src.auth.manager import AuthManager
from src.config.profiles import ProfileManager, build_env_store
from src.config.settings import (ApiSettings, AuthSettings, SsoSettings,
                                 load_settings)
from src.core.workflow import ReservationQuery
from src.main import build_app
from src.ui.state import (BoardCell, BoardRow, BoardState, BoardStatus,
                          ProfileOption, ReserveOutcome, SessionState,
                          SessionStatus, SettingsFormState)


@dataclass
class BoardQuery:
    profile_name: str
    venue_site_id: int
    date: str
    start_time: str
    slot_count: int


@dataclass
class ReserveRequest:
    profile_name: str
    venue_site_id: int
    date: str
    space_id: int
    start_time: str
    slot_count: int


class UiFacade:
    def __init__(
        self,
        *,
        profile_manager: ProfileManager | None = None,
        auth_manager_factory: Callable[[str], AuthManager] | None = None,
        workflow_factory=None,
    ) -> None:
        self.profile_manager = profile_manager or ProfileManager(environ=dict(os.environ))
        self.auth_manager_factory = auth_manager_factory or self._build_auth_manager
        self.workflow_factory = workflow_factory or self._build_workflow

    def _build_auth_manager(self, profile_name: str) -> AuthManager:
        env_store = build_env_store(profile_name, environ=dict(os.environ))
        api_settings, _, auth_settings, sso_settings = load_settings(profile_name, env_store=env_store)
        return AuthManager(api_settings, auth_settings, sso_settings, env_store=env_store)

    def _build_workflow(self, profile_name: str, query: BoardQuery):
        env_store = build_env_store(profile_name, environ=dict(os.environ))
        api_settings, user_settings, auth_settings, sso_settings = load_settings(
            profile_name,
            env_store=env_store,
        )
        api_settings.venue_site_id = query.venue_site_id
        api_settings.default_search_date = query.date
        user_settings.reservation_start_time = query.start_time
        user_settings.reservation_slot_count = query.slot_count
        workflow, _ = build_app(
            api_settings=api_settings,
            user_settings=user_settings,
            auth_settings=auth_settings,
            sso_settings=sso_settings,
            env_store=env_store,
            ensure_auth=True,
        )
        return workflow

    def list_profiles(self) -> list[ProfileOption]:
        return [
            ProfileOption(
                name=item.name,
                display_name=item.display_name,
                auth_source=item.auth_source,
                sso_source=item.sso_source,
            )
            for item in self.profile_manager.list_profiles()
        ]

    def _display_name_for_profile(self, profile_name: str) -> str:
        for item in self.profile_manager.list_profiles():
            if item.name == profile_name:
                return item.display_name or profile_name
        return profile_name

    def get_session_state(self, profile_name: str) -> SessionState:
        auth_manager = self.auth_manager_factory(profile_name)
        result = auth_manager.get_cgyy_auth_status()
        display_name = self._display_name_for_profile(profile_name)
        env_store = getattr(auth_manager, "env_store", None)
        if env_store is not None:
            display_name = env_store.get_str("CGYY_DISPLAY_NAME", "") or display_name
        state = result.state
        ok = bool(state and result.reused and state.cookie and state.cg_authorization)
        return SessionState(
            profile_name=profile_name,
            display_name=display_name,
            status=SessionStatus.AUTHENTICATED if ok else SessionStatus.UNAUTHENTICATED,
            message="当前 profile 鉴权可用" if ok else "当前 profile 需要重新连接",
            auth_source=state.source if state else "",
        )

    def load_profile_form(self, profile_name: str) -> SettingsFormState:
        env_store = build_env_store(profile_name, environ=dict(os.environ))
        api_settings, user_settings, _, _ = load_settings(profile_name, env_store=env_store)
        return SettingsFormState(
            profile_name=profile_name,
            display_name=user_settings.display_name,
            phone=user_settings.phone,
            buddy_ids=user_settings.buddy_ids,
            venue_site_id=api_settings.venue_site_id,
            default_search_date=api_settings.default_search_date,
            start_time=user_settings.reservation_start_time,
            slot_count=user_settings.reservation_slot_count,
        )

    def save_profile_patch(self, state: SettingsFormState) -> SettingsFormState:
        updates = {
            "CGYY_DISPLAY_NAME": state.display_name,
            "CGYY_PHONE": state.phone,
            "CGYY_BUDDY_IDS": state.buddy_ids,
            "CGYY_VENUE_SITE_ID": str(state.venue_site_id),
            "CGYY_DEFAULT_SEARCH_DATE": state.default_search_date,
            "CGYY_RESERVATION_START_TIME": state.start_time,
            "CGYY_RESERVATION_SLOT_COUNT": str(state.slot_count),
        }
        self.profile_manager.modify_profile(state.profile_name, updates=updates, unset_keys=[])
        return self.load_profile_form(state.profile_name)

    def login(self, profile_name: str, username: str, password: str) -> SessionState:
        updates = {}
        if username:
            updates["CGYY_SSO_USERNAME"] = username
        if password:
            updates["CGYY_SSO_PASSWORD"] = password
        if updates:
            updates["CGYY_SSO_ENABLED"] = "1"
            self.profile_manager.modify_profile(profile_name, updates=updates, unset_keys=[])
        auth_manager = self.auth_manager_factory(profile_name)
        auth_manager.ensure_cgyy_auth()
        return self.get_session_state(profile_name)

    def logout(self, profile_name: str) -> SessionState:
        auth_manager = self.auth_manager_factory(profile_name)
        auth_manager.clear_cgyy_auth()
        return self.get_session_state(profile_name)

    def load_board(self, query: BoardQuery) -> BoardState:
        workflow = self.workflow_factory(query.profile_name, query)
        info, book_date, _ = workflow.get_solutions(
            ReservationQuery(
                date=query.date,
                start_time=None,
                slot_count=query.slot_count,
                show_order_param=False,
            )
        )
        return build_board_state(
            profile_name=query.profile_name,
            venue_site_id=query.venue_site_id,
            date=book_date,
            slot_count=query.slot_count,
            info=info,
            start_time=query.start_time,
        )

    def reserve(self, request: ReserveRequest) -> ReserveOutcome:
        workflow = self.workflow_factory(
            request.profile_name,
            BoardQuery(
                profile_name=request.profile_name,
                venue_site_id=request.venue_site_id,
                date=request.date,
                start_time=request.start_time,
                slot_count=request.slot_count,
            ),
        )
        result = workflow.run_selected_reservation(
            search_date=request.date,
            space_id=request.space_id,
            start_time=request.start_time,
            slot_count=request.slot_count,
        )
        submit = result.reservation.submit_parsed
        return ReserveOutcome(
            success=result.reservation.success,
            message=result.reservation.message,
            trade_no=submit.trade_no if submit else "",
            order_id=submit.order_id if submit else 0,
        )


def _is_selectable(schedule, sorted_slots, start_index: int, slot_count: int) -> bool:
    end_index = start_index + slot_count
    if end_index > len(sorted_slots):
        return False
    for item in sorted_slots[start_index:end_index]:
        state = schedule.slots.get(str(item.id))
        if state is None or not state.is_available:
            return False
    return True


def build_board_state(
    *,
    profile_name: str,
    venue_site_id: int,
    date: str,
    slot_count: int,
    info,
    start_time: str = "",
) -> BoardState:
    sorted_slots = sorted(info.time_slots, key=lambda item: item.begin_time)
    rows: list[BoardRow] = []
    for schedule in info.space_schedules_by_date.get(date, []):
        cells: list[BoardCell] = []
        for index, slot in enumerate(sorted_slots):
            state = schedule.slots.get(str(slot.id))
            is_available = bool(state and state.is_available)
            selectable = is_available and _is_selectable(schedule, sorted_slots, index, slot_count)
            status_text = "空闲" if is_available else "占用"
            if state is None:
                status_text = "未知"
            cells.append(
                BoardCell(
                    space_id=schedule.space_id,
                    space_name=schedule.space_name,
                    time_id=slot.id,
                    begin_time=slot.begin_time,
                    end_time=slot.end_time,
                    label=slot.begin_time,
                    status_text=status_text,
                    selectable=selectable,
                    is_available=is_available,
                    fee=float(state.order_fee or 0) if state else 0.0,
                )
            )
        rows.append(BoardRow(space_id=schedule.space_id, space_name=schedule.space_name, cells=cells))

    venue_label = ""
    if info.site_param:
        venue_label = f"{info.site_param.venue_name} / {info.site_param.site_name}"
    return BoardState(
        status=BoardStatus.READY,
        profile_name=profile_name,
        venue_site_id=venue_site_id,
        venue_label=venue_label,
        date=date,
        slot_count=slot_count,
        start_time=start_time,
        rows=rows,
        time_headers=[slot.begin_time for slot in sorted_slots],
        last_sync_at=datetime.now().strftime("%H:%M:%S"),
    )
