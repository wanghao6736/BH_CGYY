from __future__ import annotations

import logging
from argparse import Namespace
from typing import Mapping

from src.cli.context import CommandContext
from src.cli.handlers.shared import display_name, print_reserve_hints
from src.core.exceptions import CgyyError
from src.notifier import build_payment_notification_message, send_notification
from src.presenters.format import (format_payment_result,
                                   format_request_result,
                                   format_solutions_table,
                                   format_submit_result)

logger = logging.getLogger(__name__)


def run_reserve(
    workflow,
    payment_service,
    args: Namespace,
    *,
    environ: Mapping[str, str] | None = None,
) -> None:
    try:
        if workflow is None:
            raise RuntimeError("应用未初始化")
        logger.info("查询可预约场地…")
        result = workflow.run_full_reservation()
        if result.solutions:
            date_str = result.reservation_date or workflow.api_settings.default_search_date
            print(format_solutions_table(result.solutions, date_str, result.site_param))
        print(format_request_result("验证码校验", result.captcha.success, result.captcha.message or ""))
        print(
            format_submit_result(
                result.reservation.success,
                result.reservation.message or "",
                result.reservation.submit_parsed,
                display_name=display_name(
                    workflow.user_settings.profile_name,
                    workflow.user_settings.display_name,
                ),
                profile_name=workflow.user_settings.profile_name,
            )
        )
        payment_target = ""
        payment_message = ""
        if result.reservation.success and result.reservation.submit_parsed is not None:
            try:
                if payment_service is None:
                    raise RuntimeError("PaymentService 未初始化")
                payment_result = payment_service.create_reservation_payment(
                    result.reservation.submit_parsed.trade_no
                )
                payment_target = payment_result.resolved_target
                print(
                    format_payment_result(
                        payment_result,
                        display_name=display_name(
                            workflow.user_settings.profile_name,
                            workflow.user_settings.display_name,
                        ),
                        profile_name=workflow.user_settings.profile_name,
                    )
                )
            except Exception as exc:
                payment_message = str(exc)
                logger.error("预约成功，但支付跳转生成失败: %s", exc)
                print(format_request_result("订单支付", False, payment_message))
            send_notification(
                "CGYY 预约成功",
                build_payment_notification_message(
                    success=result.reservation.success,
                    message=result.reservation.message or "",
                    order_id=(
                        result.reservation.submit_parsed.order_id
                        if result.reservation.submit_parsed
                        else 0
                    ),
                    trade_no=(
                        result.reservation.submit_parsed.trade_no
                        if result.reservation.submit_parsed
                        else ""
                    ),
                    reservation_start_date=(
                        result.reservation.submit_parsed.reservation_start_date
                        if result.reservation.submit_parsed
                        else ""
                    ),
                    reservation_end_date=(
                        result.reservation.submit_parsed.reservation_end_date
                        if result.reservation.submit_parsed
                        else ""
                    ),
                    display_name=display_name(
                        workflow.user_settings.profile_name,
                        workflow.user_settings.display_name,
                    ),
                    profile_name=workflow.user_settings.profile_name,
                    payment_target=payment_target,
                    payment_message=payment_message,
                ),
                url=payment_target,
                profile_name=workflow.user_settings.profile_name,
                environ=environ,
            )
    except CgyyError as exc:
        logger.error(str(exc))
        print(format_request_result("预约流程", False, str(exc)))
        print_reserve_hints(exc)
    except Exception as exc:
        logger.exception("预约失败")
        print(format_request_result("预约流程", False, str(exc)))
        print_reserve_hints(exc)


def handle_reserve(context: CommandContext, args: Namespace) -> None:
    run_reserve(
        context.services.workflow,
        context.services.payment_service,
        args,
        environ=context.runtime_environ,
    )
