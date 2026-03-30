"""按动作分发并执行 CLI 命令。"""
from __future__ import annotations

import logging
from argparse import Namespace
from datetime import datetime
from typing import TYPE_CHECKING

from src.auth.manager import AuthManager
from src.config.profiles import DISPLAY_NAME_ENV_VAR, ProfileManager
from src.core.exceptions import (BuddyConfigError, CaptchaError, CgyyError,
                                 QueryError)
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
LEGACY_SSO_KEYS = ("CGYY_SSO_USERNAME", "CGYY_SSO_PASSWORD")


def get_cmd(args: Namespace) -> str:
    """从 argparse 结果中取子命令名，默认 'reserve'。"""
    return getattr(args, "cmd", None) or "reserve"


def run(
    workflow: "ReservationWorkflow | None",
    catalog_service: "CatalogService | None",
    auth_manager: AuthManager,
    profile_manager: ProfileManager,
    args: Namespace,
) -> None:
    """根据 args.cmd 分发到对应子命令。"""
    cmd = get_cmd(args)
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
    elif cmd == "login":
        run_login(auth_manager)
    elif cmd == "auth-status":
        run_auth_status(auth_manager)
    elif cmd == "logout":
        run_logout(auth_manager)
    elif cmd == "profile":
        run_profile(profile_manager, args)
    else:
        run_reserve(workflow, args)


def _display_name(profile_name: str, configured_name: str = "") -> str:
    return configured_name or profile_name


def _print_identity(profile_name: str, configured_name: str = "") -> None:
    print(f"   👤 当前身份 {_display_name(profile_name, configured_name)} | profile {profile_name}")


def _parse_updates(items: list[str] | None) -> dict[str, str]:
    updates: dict[str, str] = {}
    for item in items or []:
        key, value = item.split("=", 1)
        updates[key] = value
    return updates


def run_catalog(
    workflow: "ReservationWorkflow | None",
    catalog_service: "CatalogService | None",
    args: Namespace,
) -> None:
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
    except Exception as e:
        logger.exception("查询场地目录失败")
        print(format_request_result("场地目录", False, str(e)))


def run_fetch_captcha(workflow: "ReservationWorkflow") -> None:
    try:
        if workflow is None:
            raise RuntimeError("应用未初始化")
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
        if workflow is None:
            raise RuntimeError("应用未初始化")
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
            st = args.start_time or "任意"
            print(f"   📋 {book_date} {st} 起 {workflow.user_settings.reservation_slot_count} 时段暂无可用方案。")
    except CgyyError as e:
        print(format_request_result("查询场地信息", False, str(e)))
    except Exception as e:
        logger.exception("查询场地信息失败")
        print(format_request_result("查询场地信息", False, str(e)))


def run_order_detail(workflow: "ReservationWorkflow", args: Namespace) -> None:
    try:
        if workflow is None:
            raise RuntimeError("应用未初始化")
        logger.info("查询订单详情 trade_no=%s", args.trade_no)
        ok, msg, parsed = workflow.reservation_service.get_order_detail_parsed(args.trade_no)
        print(format_request_result("查询订单详情", ok, msg))
        if ok and parsed:
            _print_identity(
                workflow.user_settings.profile_name,
                workflow.user_settings.display_name,
            )
            print(format_order_detail(parsed))
    except Exception as e:
        logger.exception("查询订单失败")
        print(format_request_result("查询订单详情", False, str(e)))


def run_cancel_order(workflow: "ReservationWorkflow", args: Namespace) -> None:
    try:
        if workflow is None:
            raise RuntimeError("应用未初始化")
        logger.info("取消订单 trade_no=%s", args.trade_no)
        ok, msg = workflow.reservation_service.cancel_order_parsed(args.trade_no)
        print(format_request_result("取消订单", ok, msg))
    except Exception as e:
        logger.exception("取消订单失败")
        print(format_request_result("取消订单", False, str(e)))


def _print_reserve_hints(exc: Exception) -> None:
    """根据异常类型给出可执行的下一步建议。"""
    hints: list[str] = []
    if isinstance(exc, BuddyConfigError):
        hints.append("请在当前 profile 配置中写入 CGYY_BUDDY_IDS（逗号分隔的同伴 id）")
        hints.append("查看可选同伴：python -m src.main info --show-order-param")
    elif isinstance(exc, QueryError):
        hints.append("尝试其他日期：python -m src.main reserve -d YYYY-MM-DD")
        hints.append("尝试其他时段：python -m src.main reserve -s HH:MM")
        hints.append("查看当前空闲：python -m src.main info -d YYYY-MM-DD")
    elif isinstance(exc, CaptchaError):
        hints.append("验证码识别可能不稳定，请直接重试")
    else:
        low = str(exc).lower()
        if "cookie" in low or "authorization" in low or "401" in str(exc) or "403" in str(exc):
            hints.append("登录凭证可能过期，请更新当前 profile 中的 CGYY_COOKIE 和 CGYY_CG_AUTH")
    if not hints:
        hints.append("查看帮助：python -m src.main --help")
    print("\n💡 下一步建议：")
    for h in hints:
        print(f"   → {h}")


def run_reserve(workflow: "ReservationWorkflow", args: Namespace) -> None:
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
                display_name=_display_name(
                    workflow.user_settings.profile_name,
                    workflow.user_settings.display_name,
                ),
                profile_name=workflow.user_settings.profile_name,
            )
        )
    except CgyyError as e:
        logger.error(str(e))
        print(format_request_result("预约流程", False, str(e)))
        _print_reserve_hints(e)
    except Exception as e:
        logger.exception("预约失败")
        print(format_request_result("预约流程", False, str(e)))
        _print_reserve_hints(e)


def run_login(auth_manager: AuthManager) -> None:
    try:
        result = auth_manager.ensure_cgyy_auth()
        state = result.state
        source = state.source if state else "-"
        print(format_request_result("认证登录", True, f"认证可用，source={source}"))
        configured_name = auth_manager.env_store.get_str(DISPLAY_NAME_ENV_VAR, "")
        profile_name = auth_manager.env_store.path.stem if auth_manager.env_store.path.name != ".env" else "default"
        _print_identity(profile_name, configured_name)
        if state:
            print(f"   🍪 cookie: {'已获取' if state.cookie else '未获取'}")
            print(f"   🔑 cgAuthorization: {'已获取' if state.cg_authorization else '未获取'}")
    except Exception as e:
        logger.exception("认证登录失败")
        print(format_request_result("认证登录", False, str(e)))


def run_auth_status(auth_manager: AuthManager) -> None:
    try:
        result = auth_manager.get_cgyy_auth_status()
        state = result.state
        ok = bool(state and state.cookie and state.cg_authorization and result.reused)
        msg = "当前 profile 鉴权可用" if ok else "当前 profile 鉴权缺失或已失效"
        print(format_request_result("认证状态", ok, msg))
        configured_name = auth_manager.env_store.get_str(DISPLAY_NAME_ENV_VAR, "")
        profile_name = auth_manager.env_store.path.stem if auth_manager.env_store.path.name != ".env" else "default"
        _print_identity(profile_name, configured_name)
        if state:
            obtained = "-"
            if state.obtained_at:
                obtained = datetime.fromtimestamp(state.obtained_at).strftime("%Y-%m-%d %H:%M:%S")
            print(f"   🪪 source: {state.source or '-'}")
            print(f"   🕒 obtained_at: {obtained}")
            print(f"   🍪 cookie: {'已配置' if state.cookie else '缺失'}")
            print(f"   🔑 cgAuthorization: {'已配置' if state.cg_authorization else '缺失'}")
        if not ok:
            print("   💡 可执行 `python -m src.main login -P <profile>` 自动刷新鉴权信息。")
    except Exception as e:
        logger.exception("查询认证状态失败")
        print(format_request_result("认证状态", False, str(e)))


def run_logout(auth_manager: AuthManager) -> None:
    try:
        auth_manager.clear_cgyy_auth()
        print(format_request_result("清理认证", True, "已清空当前 profile 中的 CGYY_COOKIE / CGYY_CG_AUTH"))
        configured_name = auth_manager.env_store.get_str(DISPLAY_NAME_ENV_VAR, "")
        profile_name = auth_manager.env_store.path.stem if auth_manager.env_store.path.name != ".env" else "default"
        _print_identity(profile_name, configured_name)
    except Exception as e:
        logger.exception("清理认证缓存失败")
        print(format_request_result("清理认证", False, str(e)))


def _print_legacy_sso_notice(profile_name: str) -> None:
    print(f"   💡 {profile_name} 中的 CGYY_SSO_USERNAME / CGYY_SSO_PASSWORD 仅供 CLI 自动化模式使用。")
    print(f"   💡 GUI 登录已不再使用这两个字段，可执行 `python -m src.main profile cleanup-legacy-sso {profile_name}` 清理。")


def _has_legacy_sso_values(profile_manager: ProfileManager, profile_name: str) -> bool:
    values = profile_manager.show_profile(profile_name)
    present = {item.key for item in values if item.value and item.value != "(missing)"}
    return any(key in present for key in LEGACY_SSO_KEYS)


def run_profile(profile_manager: ProfileManager, args: Namespace) -> None:
    try:
        cmd = getattr(args, "profile_cmd", "")
        if cmd == "list":
            profiles = profile_manager.list_profiles()
            print(format_request_result("profile 列表", True, f"共 {len(profiles)} 个"))
            for item in profiles:
                print(
                    f"   - {item.name} | 显示名 {item.display_name} | "
                    f"auth={item.auth_source} | sso={item.sso_source} | path={item.path}"
                )
            return
        if cmd == "show":
            values = profile_manager.show_profile(args.name)
            print(format_request_result("profile 详情", True, args.name))
            for item in values:
                print(f"   - {item.key}={item.value} ({item.source})")
            if any(item.key in LEGACY_SSO_KEYS and item.value for item in values):
                _print_legacy_sso_notice(args.name)
            return
        if cmd == "add":
            path = profile_manager.add_profile(args.name, _parse_updates(args.set_values))
            print(format_request_result("profile 新增", True, str(path)))
            return
        if cmd == "modify":
            path = profile_manager.modify_profile(
                args.name,
                updates=_parse_updates(args.set_values),
                unset_keys=list(args.unset_keys or []),
            )
            print(format_request_result("profile 修改", True, str(path)))
            touched_keys = {item.split("=", 1)[0] for item in (args.set_values or [])}
            touched_keys.update(args.unset_keys or [])
            if any(key in touched_keys for key in LEGACY_SSO_KEYS):
                _print_legacy_sso_notice(args.name)
            elif _has_legacy_sso_values(profile_manager, args.name):
                _print_legacy_sso_notice(args.name)
            return
        if cmd == "cleanup-legacy-sso":
            path = profile_manager.modify_profile(
                args.name,
                updates={},
                unset_keys=list(LEGACY_SSO_KEYS),
            )
            print(format_request_result("legacy SSO 清理", True, str(path)))
            return
        if cmd == "remove":
            profile_manager.remove_profile(args.name, force=bool(args.force))
            print(format_request_result("profile 删除", True, args.name))
            return
        raise ValueError(f"未知 profile 子命令: {cmd}")
    except Exception as e:
        logger.exception("profile 命令失败")
        print(format_request_result("profile 命令", False, str(e)))
