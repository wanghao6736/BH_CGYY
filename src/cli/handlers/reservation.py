from __future__ import annotations

import logging
from argparse import Namespace

from src.cli.context import CommandContext
from src.cli.handlers.shared import display_name, print_reserve_hints
from src.core.exceptions import CgyyError
from src.presenters.format import (format_request_result,
                                   format_solutions_table,
                                   format_submit_result)

logger = logging.getLogger(__name__)


def run_reserve(workflow, args: Namespace) -> None:
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
    except CgyyError as exc:
        logger.error(str(exc))
        print(format_request_result("预约流程", False, str(exc)))
        print_reserve_hints(exc)
    except Exception as exc:
        logger.exception("预约失败")
        print(format_request_result("预约流程", False, str(exc)))
        print_reserve_hints(exc)


def handle_reserve(context: CommandContext, args: Namespace) -> None:
    run_reserve(context.services.workflow, args)
