from __future__ import annotations

import logging
from argparse import Namespace

from src.cli.context import CommandContext
from src.cli.handlers.shared import print_identity
from src.core.exceptions import CgyyError
from src.presenters.format import (format_buddy_list,
                                   format_catalog_sites_table,
                                   format_catalog_sports_table,
                                   format_order_detail, format_request_result,
                                   format_solutions_table)

logger = logging.getLogger(__name__)


def run_catalog(workflow, catalog_service, args: Namespace) -> None:
    try:
        if workflow is None or catalog_service is None:
            raise RuntimeError("应用未初始化")
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
    except Exception as exc:
        logger.exception("查询场地目录失败")
        print(format_request_result("场地目录", False, str(exc)))


def handle_catalog(context: CommandContext, args: Namespace) -> None:
    run_catalog(context.services.workflow, context.services.catalog_service, args)


def run_fetch_captcha(workflow) -> None:
    try:
        if workflow is None:
            raise RuntimeError("应用未初始化")
        logger.info("获取验证码…")
        captcha_data = workflow.captcha_service.fetch_captcha()
        print(format_request_result("获取验证码", True))
        print(f"   🖼️  图片已保存：{captcha_data.image_path}")
        print(f"   📝 待识别文字：{captcha_data.word_list}")
        print(f"   🔑 token: {captcha_data.token[:16]}…")
    except Exception as exc:
        logger.exception("获取验证码失败")
        print(format_request_result("获取验证码", False, str(exc)))


def handle_fetch_captcha(context: CommandContext, args: Namespace) -> None:
    del args
    run_fetch_captcha(context.services.workflow)


def run_verify_captcha(workflow) -> None:
    import random
    import time

    try:
        if workflow is None:
            raise RuntimeError("应用未初始化")
        logger.info("获取验证码…")
        captcha_data = workflow.captcha_service.fetch_captcha()
        print(format_request_result("获取验证码", True))
        time.sleep(random.uniform(workflow.delay_min, workflow.delay_max))
        logger.info("识别并校验验证码…")
        result = workflow.captcha_service.verify_captcha(captcha_data)
        print(format_request_result("验证码校验", result.success, result.message))
    except Exception as exc:
        logger.exception("验证码校验失败")
        print(format_request_result("验证码校验", False, str(exc)))


def handle_verify_captcha(context: CommandContext, args: Namespace) -> None:
    del args
    run_verify_captcha(context.services.workflow)


def run_info(workflow, args: Namespace) -> None:
    from src.core.workflow import ReservationQuery

    try:
        if workflow is None:
            raise RuntimeError("应用未初始化")
        info, book_date, solutions = workflow.get_solutions(
            ReservationQuery(
                date=workflow.api_settings.default_search_date,
                start_time=args.start_time,
                slot_count=workflow.user_settings.reservation_slot_count,
                show_order_param=args.show_order_param,
            )
        )
        print(format_request_result("查询场地信息", True, ""))
        if args.show_order_param and info.order_param_view and info.order_param_view.buddy_list:
            print(format_buddy_list(info.order_param_view.buddy_list))
        if solutions:
            print(format_solutions_table(solutions, book_date, info.site_param))
        else:
            start_time = args.start_time or "任意"
            print(f"   📋 {book_date} {start_time} 起 {workflow.user_settings.reservation_slot_count} 时段暂无可用方案。")
    except CgyyError as exc:
        print(format_request_result("查询场地信息", False, str(exc)))
    except Exception as exc:
        logger.exception("查询场地信息失败")
        print(format_request_result("查询场地信息", False, str(exc)))


def handle_info(context: CommandContext, args: Namespace) -> None:
    run_info(context.services.workflow, args)


def run_order_detail(workflow, args: Namespace) -> None:
    try:
        if workflow is None:
            raise RuntimeError("应用未初始化")
        logger.info("查询订单详情 trade_no=%s", args.trade_no)
        ok, msg, parsed = workflow.reservation_service.get_order_detail_parsed(args.trade_no)
        print(format_request_result("查询订单详情", ok, msg))
        if ok and parsed:
            print_identity(
                workflow.user_settings.profile_name,
                workflow.user_settings.display_name,
            )
            print(format_order_detail(parsed))
    except Exception as exc:
        logger.exception("查询订单失败")
        print(format_request_result("查询订单详情", False, str(exc)))


def handle_order_detail(context: CommandContext, args: Namespace) -> None:
    run_order_detail(context.services.workflow, args)


def run_cancel_order(workflow, args: Namespace) -> None:
    try:
        if workflow is None:
            raise RuntimeError("应用未初始化")
        logger.info("取消订单 trade_no=%s", args.trade_no)
        ok, msg = workflow.reservation_service.cancel_order_parsed(args.trade_no)
        print(format_request_result("取消订单", ok, msg))
    except Exception as exc:
        logger.exception("取消订单失败")
        print(format_request_result("取消订单", False, str(exc)))


def handle_cancel_order(context: CommandContext, args: Namespace) -> None:
    run_cancel_order(context.services.workflow, args)
