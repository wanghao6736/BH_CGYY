from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Tuple

from src.core.captcha_service import (CaptchaData, CaptchaService,
                                      CaptchaVerificationResult)
from src.core.exceptions import BuddyConfigError, CaptchaError, QueryError
from src.core.reservation_service import ReservationResult, ReservationService
from src.core.selection_strategies import apply_pipeline
from src.parsers.day_info import DayInfoParsed, SiteParam
from src.parsers.slot_filter import SlotChoice, SlotSolution, find_solutions
from src.utils.buddy_ids import (clamp_buddy_ids, split_buddy_ids,
                                 supports_buddy_selection)

if TYPE_CHECKING:
    from src.config.settings import ApiSettings, UserSettings

logger = logging.getLogger(__name__)


@dataclass
class ReservationQuery:
    """统一查询参数：info 与 reserve 共用。"""
    date: str
    start_time: Optional[str] = None  # None 表示返回所有开始时间的方案
    slot_count: int = 1
    show_order_param: bool = False


@dataclass
class FullReservationResult:
    captcha: CaptchaVerificationResult
    reservation: ReservationResult
    solutions: Optional[List[SlotSolution]] = None  # 本次查询到的方案（若有）
    site_param: Optional[SiteParam] = None  # 场地信息（校区+场馆，用于展示）
    reservation_date: Optional[str] = None  # 本次预约日期，用于展示


class ReservationWorkflow:
    def __init__(
        self,
        captcha_service: CaptchaService,
        reservation_service: ReservationService,
        delay_min: float,
        delay_max: float,
        api_settings: "ApiSettings",
        user_settings: "UserSettings",
    ) -> None:
        self.captcha_service = captcha_service
        self.reservation_service = reservation_service
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.api_settings = api_settings
        self.user_settings = user_settings

    def get_solutions(
        self, query: ReservationQuery
    ) -> Tuple[DayInfoParsed, str, List[SlotSolution]]:
        """
        统一查询可预约方案。返回 (info, book_date, solutions)。
        query.start_time 为 None 时返回当日所有满足 duration 的方案并集。
        """
        search_date = query.date
        logger.info("查询场地信息 date=%s", search_date)
        ok, msg, info = self.reservation_service.get_info_parsed(
            search_date, has_reserve_info=query.show_order_param
        )
        if not ok or not info:
            raise QueryError(f"查询场地信息失败：{msg}")
        book_date = (info.reservation_date_list or [search_date])[0]
        raw_solutions = find_solutions(
            info,
            book_date,
            query.start_time,
            query.slot_count,
        )
        solutions = apply_pipeline(raw_solutions, self.user_settings.selection_strategy)
        return info, book_date, solutions

    # ------------------------------------------------------------------
    # run_full_reservation 的子步骤
    # ------------------------------------------------------------------

    def _resolve_buddy_ids(self, info: DayInfoParsed) -> str:
        """根据场地同伴人数要求和当前 profile 配置确定最终 buddyIds。"""
        configured = split_buddy_ids(self.user_settings.buddy_ids)
        if not info.site_param:
            return ",".join(configured)

        buddy_num_min = max(0, int(info.site_param.buddy_num_min or 0))
        buddy_num_max = max(0, int(info.site_param.buddy_num_max or 0))
        supports_buddy = supports_buddy_selection(
            buddy_num_min=buddy_num_min,
            buddy_num_max=buddy_num_max,
            available_buddy_count=len(info.order_param_view.buddy_list) if info.order_param_view else 0,
        )
        if not supports_buddy:
            return ""

        if len(configured) < buddy_num_min:
            raise BuddyConfigError(
                f"该场地要求至少 {buddy_num_min} 名同伴，但当前 profile 中 CGYY_BUDDY_IDS 配置不足 "
                f"(need={buddy_num_min}, got={len(configured)})，请先在当前 profile 中配置同伴 id。"
            )
        return ",".join(clamp_buddy_ids(configured, buddy_num_max=buddy_num_max))

    def _verify_captcha_with_retry(
        self,
    ) -> Tuple[CaptchaData, CaptchaVerificationResult]:
        """带重试的验证码获取与校验。"""
        max_attempts = max(self.api_settings.retry_count, 1)
        logger.info("正在进行验证码校验，请稍候... (最多 %d 次)", max_attempts)
        last_exc: Optional[Exception] = None

        for attempt in range(max_attempts):
            data: Optional[CaptchaData] = None
            result: Optional[CaptchaVerificationResult] = None
            try:
                data = self.captcha_service.fetch_captcha()
                time.sleep(random.uniform(self.delay_min, self.delay_max))
                result = self.captcha_service.verify_captcha(data)
            except CaptchaError as e:
                last_exc = e
                logger.warning("验证码校验失败 (%d/%d): %s", attempt + 1, max_attempts, e)
                if attempt < max_attempts - 1:
                    time.sleep(self.api_settings.retry_interval_sec)
                continue

            if result.success:
                logger.info("验证码校验通过 (%d/%d)", attempt + 1, max_attempts)
                return data, result

            last_exc = CaptchaError(result.message or "验证码校验未通过")
            logger.warning("验证码校验未通过 (%d/%d): %s", attempt + 1, max_attempts, result.message)
            if attempt < max_attempts - 1:
                time.sleep(self.api_settings.retry_interval_sec)

        raise last_exc or CaptchaError("验证码流程失败")

    # ------------------------------------------------------------------

    def _make_slot_solution(
        self,
        info: DayInfoParsed,
        book_date: str,
        *,
        space_id: int,
        start_time: str,
        slot_count: int,
    ) -> SlotSolution:
        sorted_slots = sorted(info.time_slots, key=lambda item: item.begin_time)
        start_index = next((idx for idx, item in enumerate(sorted_slots) if item.begin_time == start_time), None)
        if start_index is None:
            raise QueryError(f"未找到开始时间 {start_time}")
        end_index = start_index + slot_count
        if end_index > len(sorted_slots):
            raise QueryError(f"{start_time} 起不足 {slot_count} 个连续时段")

        schedule = next(
            (item for item in info.space_schedules_by_date.get(book_date, []) if item.space_id == space_id),
            None,
        )
        if schedule is None:
            raise QueryError(f"未找到场地 id={space_id}")

        selected_slots = sorted_slots[start_index:end_index]
        choices: list[SlotChoice] = []
        total_minutes = 0
        for item in selected_slots:
            state = schedule.slots.get(str(item.id))
            if state is None or not state.is_available:
                raise QueryError(
                    f"场地 {schedule.space_name} 在 {item.begin_time}-{item.end_time} 不可预约"
                )
            choices.append(
                SlotChoice(
                    space_id=schedule.space_id,
                    time_id=item.id,
                    space_name=schedule.space_name,
                    start_time=item.begin_time,
                    end_time=item.end_time,
                    order_fee=float(state.order_fee or 0),
                )
            )
            start_m, end_m = item.begin_time.split(":"), item.end_time.split(":")
            total_minutes += (int(end_m[0]) * 60 + int(end_m[1])) - (int(start_m[0]) * 60 + int(start_m[1]))

        total_fee = sum(item.order_fee for item in choices)
        return SlotSolution(
            choices=choices,
            total_fee=total_fee,
            slot_count=len(choices),
            total_hours=round(total_minutes / 60, 1),
        )

    def _submit_solution(
        self,
        info: DayInfoParsed,
        book_date: str,
        solution: SlotSolution,
    ) -> FullReservationResult:
        reservation_order_json = json.dumps(
            [{"spaceId": str(c.space_id), "timeId": str(c.time_id)} for c in solution.choices],
            separators=(",", ":"),
        )
        buddy_ids = self._resolve_buddy_ids(info)
        order_price = int(round(solution.total_fee))
        captcha_data, captcha_result = self._verify_captcha_with_retry()
        logger.info("提交订单... date=%s", book_date)
        reservation_result = self.reservation_service.submit_reservation(
            captcha_token=captcha_data.token,
            captcha_verification=captcha_result.verification.verify_json,
            reservation_date=book_date,
            week_start_date=book_date,
            reservation_order_json=reservation_order_json,
            buddy_ids=buddy_ids,
            order_price=order_price,
        )
        return FullReservationResult(
            captcha=captcha_result,
            reservation=reservation_result,
            solutions=[solution],
            site_param=info.site_param,
            reservation_date=book_date,
        )

    def run_selected_reservation(
        self,
        *,
        search_date: str,
        space_id: int,
        start_time: str,
        slot_count: int,
    ) -> FullReservationResult:
        info, book_date, _ = self.get_solutions(
            ReservationQuery(
                date=search_date,
                start_time=start_time,
                slot_count=slot_count,
                show_order_param=False,
            )
        )
        solution = self._make_slot_solution(
            info,
            book_date,
            space_id=space_id,
            start_time=start_time,
            slot_count=slot_count,
        )
        return self._submit_solution(info, book_date, solution)

    def run_solution_reservation(
        self,
        *,
        search_date: str,
        solution: SlotSolution,
    ) -> FullReservationResult:
        logger.info("按显式方案提交预约 date=%s slots=%d", search_date, len(solution.choices))
        ok, msg, info = self.reservation_service.get_info_parsed(
            search_date,
            has_reserve_info=False,
        )
        if not ok or not info:
            raise QueryError(f"查询场地信息失败：{msg}")
        book_date = (info.reservation_date_list or [search_date])[0]
        return self._submit_solution(info, book_date, solution)

    def run_full_reservation(self, search_date: str | None = None) -> FullReservationResult:
        date = search_date or self.api_settings.default_search_date
        query = ReservationQuery(
            date=date,
            start_time=self.user_settings.reservation_start_time or None,
            slot_count=self.user_settings.reservation_slot_count,
            show_order_param=False,
        )

        # 1) 查询可用方案
        info, book_date, solutions = self.get_solutions(query)
        if not solutions:
            st = query.start_time or "任意"
            raise QueryError(f"📅 {book_date} {st} 起 {query.slot_count} 时段暂无可用场地")

        first_solution = solutions[0]
        logger.info("找到 %d 个可预约方案，使用第 1 个 (总价=%.2f)", len(solutions), first_solution.total_fee)
        return self._submit_solution(info, book_date, first_solution)
