from __future__ import annotations

import logging
from argparse import Namespace
from datetime import datetime

from src.cli.context import CommandContext
from src.cli.handlers.shared import (get_profile_name_from_env_path,
                                     print_identity)
from src.config.profiles import DISPLAY_NAME_ENV_VAR
from src.presenters.format import format_request_result

logger = logging.getLogger(__name__)


def run_login(auth_manager) -> None:
    try:
        result = auth_manager.ensure_cgyy_auth()
        state = result.state
        source = state.source if state else "-"
        print(format_request_result("认证登录", True, f"认证可用，source={source}"))
        configured_name = auth_manager.env_store.get_str(DISPLAY_NAME_ENV_VAR, "")
        profile_name = get_profile_name_from_env_path(auth_manager.env_store.path.name)
        print_identity(profile_name, configured_name)
        if state:
            print(f"   🍪 cookie: {'已获取' if state.cookie else '未获取'}")
            print(f"   🔑 cgAuthorization: {'已获取' if state.cg_authorization else '未获取'}")
    except Exception as exc:
        logger.exception("认证登录失败")
        print(format_request_result("认证登录", False, str(exc)))


def handle_login(context: CommandContext, args: Namespace) -> None:
    del args
    run_login(context.auth_manager)


def run_auth_status(auth_manager) -> None:
    try:
        result = auth_manager.get_cgyy_auth_status()
        state = result.state
        ok = bool(state and state.cookie and state.cg_authorization and result.reused)
        msg = "当前 profile 鉴权可用" if ok else "当前 profile 鉴权缺失或已失效"
        print(format_request_result("认证状态", ok, msg))
        configured_name = auth_manager.env_store.get_str(DISPLAY_NAME_ENV_VAR, "")
        profile_name = get_profile_name_from_env_path(auth_manager.env_store.path.name)
        print_identity(profile_name, configured_name)
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
    except Exception as exc:
        logger.exception("查询认证状态失败")
        print(format_request_result("认证状态", False, str(exc)))


def handle_auth_status(context: CommandContext, args: Namespace) -> None:
    del args
    run_auth_status(context.auth_manager)


def run_logout(auth_manager) -> None:
    try:
        auth_manager.clear_cgyy_auth()
        print(format_request_result("清理认证", True, "已清空当前 profile 中的 CGYY_COOKIE / CGYY_CG_AUTH"))
        configured_name = auth_manager.env_store.get_str(DISPLAY_NAME_ENV_VAR, "")
        profile_name = get_profile_name_from_env_path(auth_manager.env_store.path.name)
        print_identity(profile_name, configured_name)
    except Exception as exc:
        logger.exception("清理认证缓存失败")
        print(format_request_result("清理认证", False, str(exc)))


def handle_logout(context: CommandContext, args: Namespace) -> None:
    del args
    run_logout(context.auth_manager)
