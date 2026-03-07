from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Tuple

from src.core.captcha_service import CaptchaService, CaptchaVerificationResult
from src.core.reservation_service import ReservationResult, ReservationService
from src.core.selection_strategies import pick_solution
from src.parsers.day_info import DayInfoParsed, SiteParam
from src.parsers.slot_filter import SlotSolution

if TYPE_CHECKING:
    from src.config.settings import ApiSettings, UserSettings

logger = logging.getLogger(__name__)


@dataclass
class ReservationQuery:
    """统一查询参数：info 与 reserve 共用。"""
    date: str
    start_time: Optional[str] = None  # None 表示返回所有开始时间的方案
    duration_hours: int = 1
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
            raise RuntimeError(f"QUERY: 查询场地信息失败：{msg}")
        book_date = (info.reservation_date_list or [search_date])[0]
        solutions = self.reservation_service.find_available_slots_with_optional_start(
            info,
            book_date,
            query.start_time,
            query.duration_hours,
        )
        return info, book_date, solutions

    def run_full_reservation(self, search_date: str | None = None) -> FullReservationResult:
        date = search_date or self.api_settings.default_search_date
        query = ReservationQuery(
            date=date,
            start_time=self.user_settings.reservation_start_time or None,
            duration_hours=self.user_settings.reservation_duration_hours,
            show_order_param=False,
        )
        info, book_date, solutions = self.get_solutions(query)
        if not solutions:
            st = query.start_time or "任意"
            raise RuntimeError(f"QUERY: 📅 {book_date} {st} 起 {query.duration_hours} 时段暂无可用场地")
        first_solution = pick_solution(solutions, mode="first")
        logger.info("找到 %d 个可预约方案，使用第 1 个 (总价=%.2f)", len(solutions), first_solution.total_fee)
        reservation_order_json = json.dumps(
            [{"spaceId": str(c.space_id), "timeId": str(c.time_id)} for c in first_solution.choices],
            separators=(",", ":"),
        )
        # 同伴选择：完全由环境变量 CGYY_BUDDY_IDS 决定，不再自动从 orderParamView 选择。
        # - 若 siteParam.buddyNumMin==0：不传 buddyIds/buddyUids（显式传入 "" 触发 payload 省略）
        # - 若 buddyNumMin>=1：要求 env 中配置的 buddyIds 至少满足人数要求，否则报错提示用户先配置 .env
        if not info.site_param:
            buddy_ids = self.user_settings.buddy_ids
        else:
            buddy_num_min = max(0, int(info.site_param.buddy_num_min or 0))
            buddy_num_max = max(0, int(info.site_param.buddy_num_max or 0))

            if buddy_num_min <= 0:
                buddy_ids = ""
            else:
                need = buddy_num_min
                if buddy_num_max > 0:
                    need = min(need, buddy_num_max)

                configured = [
                    s.strip()
                    for s in (self.user_settings.buddy_ids or "").split(",")
                    if s.strip()
                ]
                if len(configured) < need:
                    raise RuntimeError(
                        f"QUERY: 该场地要求至少 {buddy_num_min} 名同伴，但 .env 中 CGYY_BUDDY_IDS 配置不足 "
                        f"(need={need}, got={len(configured)})，请先在 .env 中配置同伴 id。"
                    )
                buddy_ids = ",".join(configured[:need])
        order_price = int(round(first_solution.total_fee))

        # Captcha recognition/verification is not covered by HTTP retry.
        # Keep retry strategy consistent with ApiClient: retry_count + retry_interval_sec.
        last_exc: Optional[Exception] = None
        captcha_data = None
        captcha_result = None
        for attempt in range(self.api_settings.retry_count):
            try:
                captcha_data = self.captcha_service.fetch_captcha()
                time.sleep(random.uniform(self.delay_min, self.delay_max))
                captcha_result = self.captcha_service.verify_captcha(captcha_data)
                logger.info("验证码校验 %s", "通过" if captcha_result.success else "未通过")
                if captcha_result.success:
                    break
                last_exc = RuntimeError(f"CAPTCHA: {captcha_result.message or '验证码校验未通过'}")
            except RuntimeError as e:
                last_exc = e if str(e).startswith("CAPTCHA:") else RuntimeError(f"CAPTCHA: {e}")
            if attempt < self.api_settings.retry_count - 1:
                time.sleep(self.api_settings.retry_interval_sec)

        if captcha_data is None or captcha_result is None:
            raise (last_exc or RuntimeError("CAPTCHA: 验证码流程失败"))
        logger.info("提交订单… date=%s", book_date)
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
            solutions=solutions,
            site_param=info.site_param,
            reservation_date=book_date,
        )
