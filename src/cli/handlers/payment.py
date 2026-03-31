from __future__ import annotations

import logging
from argparse import Namespace
from typing import Mapping

from src.cli.context import CommandContext
from src.cli.handlers.shared import display_name
from src.core.exceptions import CgyyError
from src.notifier import describe_payment_target, send_notification
from src.presenters.format import format_payment_result, format_request_result

logger = logging.getLogger(__name__)


def run_pay(
    payment_service,
    workflow,
    args: Namespace,
    *,
    environ: Mapping[str, str] | None = None,
) -> None:
    try:
        if payment_service is None or workflow is None:
            raise RuntimeError("应用未初始化")
        logger.info(
            "拉起支付 trade_no=%s mode=%s pay_way_name=%s",
            args.trade_no,
            args.mode,
            args.pay_way_name or "-",
        )
        result = payment_service.create_and_resolve_order_payment(
            args.trade_no,
            mode=args.mode,
            pay_way_name=args.pay_way_name,
        )
        print(format_request_result("订单支付", result.order_payment.success, result.order_payment.message))
        payment_output = format_payment_result(
            result.payment_result,
            display_name=display_name(
                workflow.user_settings.profile_name,
                workflow.user_settings.display_name,
            ),
            profile_name=workflow.user_settings.profile_name,
        )
        print(payment_output)
        target_label = describe_payment_target(result.payment_result.resolved_target)
        send_notification(
            f"CGYY {target_label}已生成",
            payment_output,
            url=result.payment_result.resolved_target,
            profile_name=workflow.user_settings.profile_name,
            environ=environ,
        )
    except CgyyError as exc:
        logger.error(str(exc))
        print(format_request_result("订单支付", False, str(exc)))
    except Exception as exc:
        logger.exception("订单支付失败")
        print(format_request_result("订单支付", False, str(exc)))


def handle_pay(context: CommandContext, args: Namespace) -> None:
    run_pay(
        context.services.payment_service,
        context.services.workflow,
        args,
        environ=context.runtime_environ,
    )
