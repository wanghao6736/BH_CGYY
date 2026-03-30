from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from src.auth.manager import AuthManager
from src.config.env_store import EnvStore
from src.config.profiles import ProfileManager, build_env_store, profile_dir
from src.config.settings import AuthSettings, load_settings
from src.core.catalog_service import CatalogService
from src.core.workflow import ReservationQuery
from src.main import build_app
from src.parsers.slot_filter import SlotSolution
from src.ui.state import (BoardCell, BoardRow, BoardState, BoardStatus,
                          BuddyOption, LoginFormState, ProfileOption,
                          ReserveOutcome, SessionState, SessionStatus,
                          SettingsFormState, VenueCatalogItem,
                          VenueCatalogState)


@dataclass
class BoardQuery:
    profile_name: str
    venue_site_id: int
    date: str
    start_time: str
    slot_count: int
    skip_auth_probe: bool = False


@dataclass
class ReserveRequest:
    profile_name: str
    venue_site_id: int
    date: str
    solution: SlotSolution


class UiFacade:
    def __init__(
        self,
        *,
        root: Path | None = None,
        profile_manager: ProfileManager | None = None,
        auth_manager_factory: Callable[[str], AuthManager] | None = None,
        workflow_factory=None,
        catalog_service_factory: Callable[[str], CatalogService] | None = None,
    ) -> None:
        self._root = root
        self._environ = dict(os.environ)
        self.profile_manager = profile_manager or ProfileManager(root=root, environ=self._environ)
        self.auth_manager_factory = auth_manager_factory or self._build_auth_manager
        self.workflow_factory = workflow_factory or self._build_workflow
        self._uses_default_catalog_service_factory = catalog_service_factory is None
        self.catalog_service_factory = catalog_service_factory or self._build_catalog_service
        self._catalog_cache: dict[str, VenueCatalogState] = {}
        self._runtime_auth_cache: dict[str, tuple[str, str]] = {}
        self._load_managed_cred_key()

    def _env_store(self, profile_name: str | None) -> EnvStore:
        # 使用 fresh environ 视图，避免 profile 文件首次读取后把旧值缓存到共享 dict，
        # 导致后续保存已落盘但界面仍优先命中旧内存值。
        return build_env_store(profile_name, root=self._root, environ=dict(self._environ))

    def _managed_cred_key_path(self) -> Path:
        return profile_dir(self._root) / ".gui_cred_key"

    def _set_runtime_env(self, key: str, value: str) -> None:
        if value:
            self._environ[key] = value
            if hasattr(self.profile_manager, "environ"):
                self.profile_manager.environ[key] = value
            return
        self._environ.pop(key, None)
        if hasattr(self.profile_manager, "environ"):
            self.profile_manager.environ.pop(key, None)

    def _load_managed_cred_key(self) -> None:
        if self._environ.get("CGYY_CRED_KEY", "").strip():
            return
        path = self._managed_cred_key_path()
        if not path.exists():
            return
        key = path.read_text(encoding="utf-8").strip()
        if key:
            self._set_runtime_env("CGYY_CRED_KEY", key)

    def _ensure_managed_cred_key(self) -> str:
        raw_key = self._environ.get("CGYY_CRED_KEY", "").strip()
        if raw_key:
            return raw_key
        path = self._managed_cred_key_path()
        if path.exists():
            key = path.read_text(encoding="utf-8").strip()
            if key:
                self._set_runtime_env("CGYY_CRED_KEY", key)
                return key
        key = secrets.token_urlsafe(32)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{key}\n", encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        self._set_runtime_env("CGYY_CRED_KEY", key)
        return key

    def _apply_runtime_auth(self, profile_name: str, auth_settings: AuthSettings) -> None:
        cached = self._runtime_auth_cache.get(profile_name)
        if cached is None:
            return
        cookie, cg_authorization = cached
        if cookie:
            auth_settings.cookie = cookie
        if cg_authorization:
            auth_settings.cg_authorization = cg_authorization

    def _remember_runtime_auth(self, profile_name: str, cookie: str, cg_authorization: str) -> None:
        if cookie and cg_authorization:
            self._runtime_auth_cache[profile_name] = (cookie, cg_authorization)

    def _clear_runtime_auth(self, profile_name: str) -> None:
        self._runtime_auth_cache.pop(profile_name, None)

    def _build_auth_manager(self, profile_name: str) -> AuthManager:
        env_store = self._env_store(profile_name)
        api_settings, _, auth_settings, sso_settings = load_settings(profile_name, env_store=env_store)
        self._apply_runtime_auth(profile_name, auth_settings)
        return AuthManager(api_settings, auth_settings, sso_settings, env_store=env_store)

    def _build_workflow(self, profile_name: str, query: BoardQuery):
        env_store = self._env_store(profile_name)
        api_settings, user_settings, auth_settings, sso_settings = load_settings(
            profile_name,
            env_store=env_store,
        )
        api_settings.venue_site_id = query.venue_site_id
        api_settings.default_search_date = query.date
        user_settings.reservation_start_time = query.start_time
        user_settings.reservation_slot_count = query.slot_count
        self._apply_runtime_auth(profile_name, auth_settings)
        workflow, _ = build_app(
            api_settings=api_settings,
            user_settings=user_settings,
            auth_settings=auth_settings,
            sso_settings=sso_settings,
            env_store=env_store,
            ensure_auth=not query.skip_auth_probe,
        )
        return workflow

    def _build_catalog_service(self, profile_name: str, *, skip_auth_probe: bool = False) -> CatalogService:
        env_store = self._env_store(profile_name)
        api_settings, user_settings, auth_settings, sso_settings = load_settings(
            profile_name,
            env_store=env_store,
        )
        self._apply_runtime_auth(profile_name, auth_settings)
        _, catalog_service = build_app(
            api_settings=api_settings,
            user_settings=user_settings,
            auth_settings=auth_settings,
            sso_settings=sso_settings,
            env_store=env_store,
            ensure_auth=not skip_auth_probe,
        )
        return catalog_service

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
        display_name = self._display_name_for_profile(profile_name)
        try:
            auth_manager = self.auth_manager_factory(profile_name)
            result = auth_manager.get_cgyy_auth_status()
            env_store = getattr(auth_manager, "env_store", None)
            if env_store is not None:
                display_name = env_store.get_str("CGYY_DISPLAY_NAME", "") or display_name
            state = result.state
            ok = bool(state and result.reused and state.cookie and state.cg_authorization)
            if ok and state is not None:
                self._remember_runtime_auth(profile_name, state.cookie, state.cg_authorization)
            elif not ok:
                self._clear_runtime_auth(profile_name)
            return SessionState(
                profile_name=profile_name,
                display_name=display_name,
                status=SessionStatus.AUTHENTICATED if ok else SessionStatus.UNAUTHENTICATED,
                message="当前 profile 鉴权可用" if ok else "当前 profile 需要重新连接",
                auth_source=state.source if state else "",
            )
        except ValueError:
            self._clear_runtime_auth(profile_name)
            return SessionState(
                profile_name=profile_name,
                display_name=display_name,
                status=SessionStatus.UNAUTHENTICATED,
                message="鉴权信息不可用，请重新登录",
                auth_source="",
            )

    def load_profile_form(self, profile_name: str) -> SettingsFormState:
        env_store = self._env_store(profile_name)
        api_settings, user_settings, _, _ = load_settings(profile_name, env_store=env_store)
        return SettingsFormState(
            profile_name=profile_name,
            display_name=user_settings.display_name,
            phone=user_settings.phone,
            buddy_ids=user_settings.buddy_ids,
            selection_strategy=user_settings.selection_strategy,
            venue_site_id=api_settings.venue_site_id,
            default_search_date=api_settings.default_search_date,
            start_time=user_settings.reservation_start_time,
            slot_count=user_settings.reservation_slot_count,
        )

    def load_login_form(self, profile_name: str) -> LoginFormState:
        return LoginFormState(
            profile_name=profile_name,
            username="",
            persist_auth=True,
        )

    def load_catalog(
        self,
        profile_name: str,
        *,
        force_refresh: bool = False,
        skip_auth_probe: bool = False,
    ) -> VenueCatalogState:
        if not force_refresh and profile_name in self._catalog_cache:
            return self._catalog_cache[profile_name]

        if skip_auth_probe and self._uses_default_catalog_service_factory:
            service = self._build_catalog_service(profile_name, skip_auth_probe=True)
        else:
            service = self.catalog_service_factory(profile_name)

        ok, message, parsed = service.get_catalog_parsed()
        if not ok or parsed is None:
            raise RuntimeError(message or "加载场馆目录失败")

        state = VenueCatalogState(
            profile_name=profile_name,
            items=sorted(
                [
                    VenueCatalogItem(
                        venue_site_id=item.site_id,
                        site_name=item.site_name,
                        venue_name=item.venue_name,
                        campus_name=item.campus_name,
                    )
                    for item in parsed.sites
                ],
                key=lambda item: (
                    item.campus_name,
                    item.venue_name,
                    item.site_name,
                    item.venue_site_id,
                ),
            ),
        )
        self._catalog_cache[profile_name] = state
        return state

    def save_profile_patch(self, state: SettingsFormState) -> SettingsFormState:
        updates = {
            "CGYY_DISPLAY_NAME": state.display_name,
            "CGYY_PHONE": state.phone,
            "CGYY_BUDDY_IDS": state.buddy_ids,
            "CGYY_SELECTION_STRATEGY": state.selection_strategy,
            "CGYY_VENUE_SITE_ID": str(state.venue_site_id),
            "CGYY_DEFAULT_SEARCH_DATE": state.default_search_date,
            "CGYY_RESERVATION_START_TIME": state.start_time,
            "CGYY_RESERVATION_SLOT_COUNT": str(state.slot_count),
        }
        self.profile_manager.modify_profile(state.profile_name, updates=updates, unset_keys=[])
        return self.load_profile_form(state.profile_name)

    def login(
        self,
        profile_name: str,
        username: str,
        password: str,
        *,
        persist_auth: bool = True,
    ) -> SessionState:
        if persist_auth:
            self._ensure_managed_cred_key()
        auth_manager = self.auth_manager_factory(profile_name)
        auth_manager.sso_settings.persist_to_env = persist_auth
        result = auth_manager.login_with_credentials(username, password)
        state = result.state
        if state is not None:
            self._remember_runtime_auth(profile_name, state.cookie, state.cg_authorization)
        updates = {
            "CGYY_SSO_ENABLED": "0",
            "CGYY_SSO_USERNAME": "",
            "CGYY_SSO_PASSWORD": "",
        }
        if not persist_auth:
            updates["CGYY_COOKIE"] = ""
            updates["CGYY_CG_AUTH"] = ""
        self.profile_manager.modify_profile(
            profile_name,
            updates=updates,
            unset_keys=[],
        )
        return self.get_session_state(profile_name)

    def logout(self, profile_name: str) -> SessionState:
        self._clear_runtime_auth(profile_name)
        auth_manager = self.auth_manager_factory(profile_name)
        auth_manager.clear_cgyy_auth()
        return self.get_session_state(profile_name)

    def load_board(self, query: BoardQuery) -> BoardState:
        workflow = self.workflow_factory(query.profile_name, query)
        info, book_date, solutions = workflow.get_solutions(
            ReservationQuery(
                date=query.date,
                start_time=query.start_time or None,
                slot_count=query.slot_count,
                show_order_param=True,
            )
        )
        return build_board_state(
            profile_name=query.profile_name,
            venue_site_id=query.venue_site_id,
            date=book_date,
            slot_count=query.slot_count,
            info=info,
            solutions=solutions,
            start_time=query.start_time,
        )

    def reserve(self, request: ReserveRequest) -> ReserveOutcome:
        if not request.solution.choices:
            raise RuntimeError("未提供可提交的预约方案")
        first_choice = request.solution.choices[0]
        workflow = self.workflow_factory(
            request.profile_name,
            BoardQuery(
                profile_name=request.profile_name,
                venue_site_id=request.venue_site_id,
                date=request.date,
                start_time=first_choice.start_time,
                slot_count=request.solution.slot_count,
            ),
        )
        result = workflow.run_solution_reservation(
            search_date=request.date,
            solution=request.solution,
        )
        submit = result.reservation.submit_parsed
        return ReserveOutcome(
            success=result.reservation.success,
            message=result.reservation.message,
            trade_no=submit.trade_no if submit else "",
            order_id=submit.order_id if submit else 0,
        )

def build_board_state(
    *,
    profile_name: str,
    venue_site_id: int,
    date: str,
    slot_count: int,
    info,
    solutions: list[SlotSolution],
    start_time: str = "",
) -> BoardState:
    sorted_slots = sorted(info.time_slots, key=lambda item: item.begin_time)
    solution_keys = {
        (choice.space_id, choice.time_id)
        for solution in solutions
        for choice in solution.choices
    }
    rows: list[BoardRow] = []
    for schedule in info.space_schedules_by_date.get(date, []):
        cells: list[BoardCell] = []
        for index, slot in enumerate(sorted_slots):
            state = schedule.slots.get(str(slot.id))
            reservation_status = int(state.reservation_status) if state else 0
            selectable = bool(
                state
                and state.is_available
                and (schedule.space_id, slot.id) in solution_keys
            )
            cells.append(
                BoardCell(
                    space_id=schedule.space_id,
                    space_name=schedule.space_name,
                    time_id=slot.id,
                    begin_time=slot.begin_time,
                    end_time=slot.end_time,
                    label=slot.begin_time,
                    reservation_status=reservation_status,
                    selectable=selectable,
                    fee=float(state.order_fee or 0) if state else 0.0,
                )
            )
        rows.append(BoardRow(space_id=schedule.space_id, space_name=schedule.space_name, cells=cells))

    venue_label = ""
    campus_name = ""
    venue_name = ""
    site_name = ""
    buddy_num_min = 0
    buddy_num_max = 0
    if info.site_param:
        campus_name = info.site_param.campus_name
        venue_name = info.site_param.venue_name
        site_name = info.site_param.site_name
        buddy_num_min = info.site_param.buddy_num_min
        buddy_num_max = info.site_param.buddy_num_max
        venue_label = f"{venue_name} / {site_name}"

    runtime_phone = ""
    available_buddies: list[BuddyOption] = []
    if info.order_param_view:
        runtime_phone = info.order_param_view.phone
        available_buddies = [
            BuddyOption(id=str(item.id), name=item.name)
            for item in info.order_param_view.buddy_list
        ]

    return BoardState(
        status=BoardStatus.READY,
        profile_name=profile_name,
        venue_site_id=venue_site_id,
        venue_label=venue_label,
        date=date,
        slot_count=slot_count,
        start_time=start_time,
        rows=rows,
        solutions=list(solutions),
        time_headers=[slot.begin_time for slot in sorted_slots],
        available_dates=list(info.reservation_date_list or [date]),
        campus_name=campus_name,
        venue_name=venue_name,
        site_name=site_name,
        runtime_phone=runtime_phone,
        available_buddies=available_buddies,
        buddy_num_min=buddy_num_min,
        buddy_num_max=buddy_num_max,
        last_sync_at=datetime.now().strftime("%H:%M:%S"),
    )
