"""按动作分发并执行 CLI 命令。"""
from __future__ import annotations

import logging
from argparse import Namespace
from typing import TYPE_CHECKING

from src.presenters.format import (format_buddy_list,
                                   format_catalog_sites_table,
                                   format_catalog_sports_table,
                                   format_order_detail, format_request_result,
                                   format_solutions_table,
                                   format_submit_result)

if TYPE_CHECKING:
    from src.core.catalog_service import CatalogService
    from src.core.workflow import ReservationWorkflow

logger = logging.getLogger(__name__)


def run(
    workflow: "ReservationWorkflow",
    catalog_service: "CatalogService",
    args: Namespace,
) -> None:
    """根据 args.cmd 分发到对应子命令。"""
    cmd = getattr(args, "cmd", None) or "reserve"
    if cmd == "catalog":
        run_catalog(workflow, catalog_service, args)
    elif cmd == "fetch-captcha":
        run_fetch_captcha(workflow)
    elif cmd == "verify-captcha":
        run_verify_captcha(workflow)
    elif cmd == "info":
        run_info(workflow, args)
    elif cmd == "order-detail":
        run_order_detail(workflow, args)
    elif cmd == "cancel-order":
        run_cancel_order(workflow, args)
    else:
        run_reserve(workflow, args)


def run_catalog(
    workflow: "ReservationWorkflow",
    catalog_service: "CatalogService",
    args: Namespace,
) -> None:
    try:
        logger.info("查询场地目录…")
        ok, msg, parsed = catalog_service.get_catalog_parsed()
        print(format_request_result("场地目录", ok, msg))
        if not ok or not parsed:
            return
        filter_id = args.venue_site_id
        if args.venue_site_id == -1:
            filter_id = int(workflow.api_settings.venue_site_id)
        print(format_catalog_sports_table(parsed.sports))
        print(format_catalog_sites_table(parsed.sites, filter_id))
    except Exception as e:
        logger.exception("查询场地目录失败")
        print(format_request_result("场地目录", False, str(e)))


def run_fetch_captcha(workflow: "ReservationWorkflow") -> None:
    try:
        logger.info("获取验证码…")
        captcha_data = workflow.captcha_service.fetch_captcha()
        print(format_request_result("获取验证码", True))
        print(f"   🖼️  图片已保存：{captcha_data.image_path}")
        print(f"   📝 待识别文字：{captcha_data.word_list}")
        print(f"   🔑 token: {captcha_data.token[:16]}…")
    except Exception as e:
        logger.exception("获取验证码失败")
        print(format_request_result("获取验证码", False, str(e)))


def run_verify_captcha(workflow: "ReservationWorkflow") -> None:
    import random
    import time

    try:
        logger.info("获取验证码…")
        captcha_data = workflow.captcha_service.fetch_captcha()
        print(format_request_result("获取验证码", True))
        time.sleep(random.uniform(workflow.delay_min, workflow.delay_max))
        logger.info("识别并校验验证码…")
        result = workflow.captcha_service.verify_captcha(captcha_data)
        print(format_request_result("验证码校验", result.success, result.message))
    except Exception as e:
        logger.exception("验证码校验失败")
        print(format_request_result("验证码校验", False, str(e)))


def run_info(workflow: "ReservationWorkflow", args: Namespace) -> None:
    from src.core.workflow import ReservationQuery

    try:
        info, book_date, solutions = workflow.get_solutions(
            ReservationQuery(
                date=workflow.api_settings.default_search_date,
                start_time=args.start_time,
                duration_hours=workflow.user_settings.reservation_duration_hours,
                show_order_param=args.show_order_param,
            )
        )
        print(format_request_result("查询场地信息", True, ""))
        if args.show_order_param and info.order_param_view and info.order_param_view.buddy_list:
            print(format_buddy_list(info.order_param_view.buddy_list))
        if solutions:
            print(format_solutions_table(solutions, book_date, info.site_param))
        else:
            st = args.start_time or "任意"
            print(f"   📋 {book_date} {st} 起 {workflow.user_settings.reservation_duration_hours} 时段暂无可用方案。")
    except RuntimeError as e:
        print(format_request_result("查询场地信息", False, str(e)))
    except Exception as e:
        logger.exception("查询场地信息失败")
        print(format_request_result("查询场地信息", False, str(e)))


def run_order_detail(workflow: "ReservationWorkflow", args: Namespace) -> None:
    try:
        logger.info("查询订单详情 trade_no=%s", args.trade_no)
        ok, msg, parsed = workflow.reservation_service.get_order_detail_parsed(args.trade_no)
        print(format_request_result("查询订单详情", ok, msg))
        if ok and parsed:
            print(format_order_detail(parsed))
    except Exception as e:
        logger.exception("查询订单失败")
        print(format_request_result("查询订单详情", False, str(e)))


def run_cancel_order(workflow: "ReservationWorkflow", args: Namespace) -> None:
    try:
        logger.info("取消订单 trade_no=%s", args.trade_no)
        ok, msg = workflow.reservation_service.cancel_order_parsed(args.trade_no)
        print(format_request_result("取消订单", ok, msg))
    except Exception as e:
        logger.exception("取消订单失败")
        print(format_request_result("取消订单", False, str(e)))


def run_reserve(workflow: "ReservationWorkflow", args: Namespace) -> None:
    try:
        logger.info("查询可预约场地…")
        result = workflow.run_full_reservation()
        if result.solutions:
            date_str = result.reservation_date or workflow.api_settings.default_search_date
            print(format_solutions_table(result.solutions, date_str, result.site_param))
        cap_msg = result.captcha.message or ""
        if not result.captcha.success and cap_msg and not cap_msg.startswith("CAPTCHA:"):
            cap_msg = f"CAPTCHA: {cap_msg}"
        print(format_request_result("验证码校验", result.captcha.success, cap_msg))
        sub_msg = result.reservation.message or ""
        if not result.reservation.success and sub_msg and not sub_msg.startswith("SUBMIT:"):
            sub_msg = f"SUBMIT: {sub_msg}"
        print(
            format_submit_result(
                result.reservation.success,
                sub_msg,
                result.reservation.submit_parsed,
            )
        )
    except RuntimeError as e:
        logger.error(str(e))
        print(format_request_result("预约流程", False, str(e)))
    except Exception as e:
        logger.exception("预约失败")
        print(format_request_result("预约流程", False, str(e)))
