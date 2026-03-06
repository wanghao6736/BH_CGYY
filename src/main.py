from __future__ import annotations

import argparse
import logging

from src.api.captcha_api import CaptchaApi
from src.api.catalog_api import CatalogApi
from src.api.client import ApiClient
from src.api.reservation_api import ReservationApi
from src.config.settings import load_settings
from src.core.captcha_service import CaptchaService
from src.core.catalog_service import CatalogService
from src.core.reservation_service import ReservationService
from src.core.workflow import ReservationWorkflow
from src.presenters.format import (format_buddy_list,
                                   format_catalog_sites_table,
                                   format_catalog_sports_table,
                                   format_order_detail, format_request_result,
                                   format_solutions_table,
                                   format_submit_result)
from src.utils.crypto_utils import AesCbcEncryptor
from src.utils.sign_utils import SignBuilder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def build_app() -> tuple[ReservationWorkflow, CatalogService]:
    api_settings, user_settings, auth_settings = load_settings()
    sign_builder = SignBuilder(prefix=api_settings.prefix)
    client = ApiClient(
        api_settings=api_settings,
        auth_settings=auth_settings,
        sign_builder=sign_builder,
        retry_count=api_settings.retry_count,
        retry_interval_sec=api_settings.retry_interval_sec,
    )
    captcha_api = CaptchaApi(client=client)
    reservation_api = ReservationApi(
        client=client, api_settings=api_settings, user_settings=user_settings
    )
    catalog_api = CatalogApi(client=client)
    catalog_service = CatalogService(api=catalog_api)
    order_pin_encryptor = AesCbcEncryptor(
        key=api_settings.aes_cbc_key.encode("utf-8"),
        iv=api_settings.aes_cbc_iv.encode("utf-8"),
    )
    captcha_service = CaptchaService(api=captcha_api)
    reservation_service = ReservationService(
        api=reservation_api,
        api_settings=api_settings,
        user_settings=user_settings,
        order_pin_encryptor=order_pin_encryptor,
    )
    workflow = ReservationWorkflow(
        captcha_service=captcha_service,
        reservation_service=reservation_service,
        delay_min=api_settings.captcha_delay_min,
        delay_max=api_settings.captcha_delay_max,
        api_settings=api_settings,
        user_settings=user_settings,
    )
    return workflow, catalog_service


def build_workflow() -> ReservationWorkflow:
    """Backward compatible helper used by test_steps."""
    workflow, _ = build_app()
    return workflow


def _run_fetch_captcha(workflow: ReservationWorkflow) -> None:
    logger.info("获取验证码…")
    captcha_data = workflow.captcha_service.fetch_captcha()
    print(format_request_result("获取验证码", True))
    print(f"   🖼️  图片已保存：{captcha_data.image_path}")
    print(f"   📝 待识别文字：{captcha_data.word_list}")
    print(f"   🔑 token: {captcha_data.token[:16]}…")


def _run_verify_captcha(workflow: ReservationWorkflow) -> None:
    import random
    import time

    logger.info("获取验证码…")
    captcha_data = workflow.captcha_service.fetch_captcha()
    print(format_request_result("获取验证码", True))
    time.sleep(random.uniform(workflow.delay_min, workflow.delay_max))
    logger.info("识别并校验验证码…")
    result = workflow.captcha_service.verify_captcha(captcha_data)
    print(format_request_result("验证码校验", result.success, result.message))


def _run_day_info(workflow: ReservationWorkflow, show_order_param: bool) -> None:
    search_date = workflow.api_settings.default_search_date
    logger.info("查询场地信息 date=%s", search_date)
    ok, msg, day_info = workflow.reservation_service.get_day_info_parsed(
        search_date, has_reserve_info=show_order_param
    )
    print(format_request_result("查询场地信息", ok, msg))
    if not ok or not day_info:
        return
    book_date = (day_info.reservation_date_list or [search_date])[0]
    start_time = workflow.user_settings.reservation_start_time
    duration = workflow.user_settings.reservation_duration_hours
    solutions = workflow.reservation_service.find_available_slots(
        day_info, book_date, start_time, duration
    )
    if show_order_param and day_info.order_param_view and day_info.order_param_view.buddy_list:
        print(format_buddy_list(day_info.order_param_view.buddy_list))
    if solutions:
        print(format_solutions_table(solutions, book_date, day_info.site_param))
    else:
        print(f"   📋 {book_date} {start_time} 起 {duration}h 暂无可用方案。")


def _run_order_detail(workflow: ReservationWorkflow, trade_no: str) -> None:
    logger.info("查询订单详情 trade_no=%s", trade_no)
    ok, msg, parsed = workflow.reservation_service.get_order_detail_parsed(trade_no)
    print(format_request_result("查询订单详情", ok, msg))
    if ok and parsed:
        print(format_order_detail(parsed))


def _run_cancel_order(workflow: ReservationWorkflow, trade_no: str) -> None:
    logger.info("取消订单 trade_no=%s", trade_no)
    ok, msg = workflow.reservation_service.cancel_order_parsed(trade_no)
    print(format_request_result("取消订单", ok, msg))


def _run_catalog(catalog_service: CatalogService, venue_site_id: int | None, env_venue_site_id: int) -> None:
    logger.info("查询场地目录…")
    ok, msg, parsed = catalog_service.get_catalog_parsed()
    print(format_request_result("场地目录", ok, msg))
    if not ok or not parsed:
        return
    filter_id = venue_site_id
    if venue_site_id == -1:
        filter_id = int(env_venue_site_id)
    print(format_catalog_sports_table(parsed.sports))
    print(format_catalog_sites_table(parsed.sites, filter_id))


def main() -> None:
    parser = argparse.ArgumentParser(description="CGYY 自动预约")
    parser.add_argument(
        "-a",
        "--action",
        choices=["catalog", "fetch_captcha", "verify_captcha", "day_info", "order_detail", "cancel_order", "reserve"],
        default="reserve",
        help="catalog=场地目录, fetch_captcha=获取验证码, verify_captcha=识别并校验验证码, day_info=查询场地信息, order_detail=查询订单, cancel_order=取消订单, reserve=完整预约",
    )
    parser.add_argument(
        "-d",
        "--date",
        default=None,
        help="查询/预约日期 (YYYY-MM-DD)，day_info 与 reserve 共用，默认当天/配置值",
    )
    parser.add_argument(
        "-t",
        "--trade-no",
        dest="trade_no",
        default=None,
        help="订单编号，仅 order_detail/cancel_order 使用",
    )
    parser.add_argument(
        "-v",
        "--venue-site-id",
        dest="venue_site_id",
        nargs="?",
        type=int,
        default=None,
        const=-1,
        help="场地 siteId(=venueSiteId)。catalog 时用于筛选展示；day_info/reserve 时用于覆盖本次调用的 venueSiteId（不传则使用 .env/默认值）。仅传 --venue-site-id 则在 catalog 中使用 .env 的 CGYY_VENUE_SITE_ID。",
    )
    parser.add_argument(
        "-p",
        "--show-order-param",
        dest="show_order_param",
        action="store_true",
        help="day_info 时同时查询并展示 orderParamView（包含 buddy 列表）；默认不查询，以便下单时只使用 .env 中的 CGYY_BUDDY_IDS。",
    )
    parser.add_argument(
        "-s",
        "--start-time",
        dest="start_time",
        default=None,
        help="day_info/reserve 使用的开始时间 (HH:MM)。不传则使用 .env 中 CGYY_RESERVATION_START_TIME 或默认值。",
    )
    parser.add_argument(
        "-n",
        "--duration",
        dest="duration",
        type=int,
        default=None,
        help="day_info/reserve 使用的连续时段数（整数）。不传则使用 .env 中 CGYY_RESERVATION_DURATION_HOURS 或默认值。",
    )
    parser.add_argument(
        "-b",
        "--buddies",
        dest="buddies",
        default=None,
        help="reserve 使用的同伴 ID 列表，逗号分隔（如 7876,3343）。不传则使用 .env 中 CGYY_BUDDY_IDS。",
    )
    args = parser.parse_args()

    workflow, catalog_service = build_app()

    # 本次调用级别的设置覆盖：优先级为 CLI > main 中的设定值 > .env/环境变量 > 默认值
    if args.date:
        workflow.api_settings.default_search_date = args.date
        workflow.user_settings.reservation_date = args.date
        workflow.user_settings.week_start_date = args.date
    if args.start_time:
        workflow.user_settings.reservation_start_time = args.start_time
    if args.duration is not None:
        workflow.user_settings.reservation_duration_hours = args.duration
    if args.venue_site_id is not None and args.venue_site_id != -1:
        workflow.api_settings.venue_site_id = args.venue_site_id
    if args.buddies:
        workflow.user_settings.buddy_ids = args.buddies

    if args.action == "catalog":
        try:
            _run_catalog(catalog_service, args.venue_site_id, workflow.api_settings.venue_site_id)
        except Exception as e:
            logger.exception("查询场地目录失败")
            print(format_request_result("场地目录", False, str(e)))
    elif args.action == "fetch_captcha":
        try:
            _run_fetch_captcha(workflow)
        except Exception as e:
            logger.exception("获取验证码失败")
            print(format_request_result("获取验证码", False, str(e)))
    elif args.action == "verify_captcha":
        try:
            _run_verify_captcha(workflow)
        except Exception as e:
            logger.exception("验证码校验失败")
            print(format_request_result("验证码校验", False, str(e)))
    elif args.action == "day_info":
        try:
            _run_day_info(workflow, args.show_order_param)
        except Exception as e:
            logger.exception("查询场地信息失败")
            print(format_request_result("查询场地信息", False, str(e)))
    elif args.action == "order_detail":
        if not args.trade_no:
            print("❌ 请指定 --trade-no 订单编号")
            return
        try:
            _run_order_detail(workflow, args.trade_no)
        except Exception as e:
            logger.exception("查询订单失败")
            print(format_request_result("查询订单详情", False, str(e)))
    elif args.action == "cancel_order":
        if not args.trade_no:
            print("❌ 请指定 --trade-no 订单编号")
            return
        try:
            _run_cancel_order(workflow, args.trade_no)
        except Exception as e:
            logger.exception("取消订单失败")
            print(format_request_result("取消订单", False, str(e)))
    elif args.action == "reserve":
        try:
            logger.info("查询可预约场地…")
            result = workflow.run_full_reservation()
            if result.solutions:
                date_str = result.reservation_date or workflow.api_settings.default_search_date
                print(format_solutions_table(result.solutions, date_str, result.site_param))
            print(format_request_result("验证码校验", result.captcha.success, result.captcha.message))
            print(
                format_submit_result(
                    result.reservation.success,
                    result.reservation.message,
                    result.reservation.submit_parsed,
                )
            )
        except RuntimeError as e:
            logger.error(str(e))
            print(format_request_result("预约流程", False, str(e)))
        except Exception as e:
            logger.exception("预约失败")
            print(format_request_result("预约流程", False, str(e)))


if __name__ == "__main__":
    main()
