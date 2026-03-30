from __future__ import annotations

import logging
from argparse import Namespace

from src.cli.context import CommandContext
from src.cli.handlers.shared import (LEGACY_SSO_KEYS, has_legacy_sso_values,
                                     parse_updates, print_legacy_sso_notice)
from src.presenters.format import format_request_result

logger = logging.getLogger(__name__)


def run_profile(profile_manager, args: Namespace) -> None:
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
                print_legacy_sso_notice(args.name)
            return
        if cmd == "add":
            path = profile_manager.add_profile(args.name, parse_updates(args.set_values))
            print(format_request_result("profile 新增", True, str(path)))
            return
        if cmd == "modify":
            path = profile_manager.modify_profile(
                args.name,
                updates=parse_updates(args.set_values),
                unset_keys=list(args.unset_keys or []),
            )
            print(format_request_result("profile 修改", True, str(path)))
            touched_keys = {item.split("=", 1)[0] for item in (args.set_values or [])}
            touched_keys.update(args.unset_keys or [])
            if any(key in touched_keys for key in LEGACY_SSO_KEYS):
                print_legacy_sso_notice(args.name)
            elif has_legacy_sso_values(profile_manager, args.name):
                print_legacy_sso_notice(args.name)
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
    except Exception as exc:
        logger.exception("profile 命令失败")
        print(format_request_result("profile 命令", False, str(exc)))


def handle_profile(context: CommandContext, args: Namespace) -> None:
    run_profile(context.profile_manager, args)
