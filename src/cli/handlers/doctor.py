from __future__ import annotations

import logging
from argparse import Namespace

from src.auth.manager import AuthManager
from src.auth.models import AuthBootstrapResult, ServiceAuthState
from src.cli.context import CommandContext
from src.config.settings import ApiSettings, AuthSettings, SsoSettings
from src.config.settings import load_settings
from src.presenters.format import format_request_result

logger = logging.getLogger(__name__)

_SENSITIVE_KEYS = {"CGYY_COOKIE", "CGYY_CG_AUTH", "CGYY_SSO_PASSWORD"}


def _format_value(key: str, value: object) -> str:
    if key in _SENSITIVE_KEYS:
        return "已配置" if value else "缺失"
    if value in ("", None):
        return "(未配置)"
    return str(value)


def _source_label(context: CommandContext, key: str) -> str:
    if key in context.runtime_environ:
        return "env"
    if context.env_store is None:
        return "missing"
    source = context.env_store.get_value_source(key)
    if source is None:
        return "missing"
    if source == context.env_store.path:
        return "self"
    if source.name == ".env":
        return "default"
    return source.name


def _print_item(ok: bool, label: str, value: object, source: str, note: str = "") -> None:
    icon = "✅" if ok else "⚠️"
    line = f"   {icon} {label}: {_format_value(label, value)}"
    if source != "missing":
        line += f" | 来源 {source}"
    if note:
        line += f" | {note}"
    print(line)


def _auth_probe_result(
    context: CommandContext,
    api_settings: ApiSettings,
    auth_settings: AuthSettings,
    sso_settings: SsoSettings,
) -> AuthBootstrapResult:
    auth_manager = AuthManager(
        api_settings,
        auth_settings,
        sso_settings,
        env_store=context.env_store,
    )
    return auth_manager.get_cgyy_auth_status()


def run_config_doctor(context: CommandContext, args: Namespace) -> None:
    try:
        if context.env_store is None:
            raise RuntimeError("配置环境未初始化")

        api_settings, user_settings, auth_settings, sso_settings = load_settings(
            context.active_profile,
            env_store=context.env_store,
        )

        print(format_request_result("配置诊断", True, f"profile={context.active_profile}"))
        print(f"   📁 当前配置 {context.env_store.path}")
        if len(context.env_store.paths) > 1:
            layers = " -> ".join(str(path) for path in context.env_store.paths)
            print(f"   🧱 配置层 {layers}")

        critical_missing: list[str] = []
        auth_blockers: list[str] = []
        warnings: list[str] = []

        checks: list[tuple[bool, str, object, str, str]] = [
            (bool(api_settings.base_url), "CGYY_BASE_URL", api_settings.base_url,
             _source_label(context, "CGYY_BASE_URL"), "接口地址"),
            (bool(api_settings.prefix), "CGYY_PREFIX", api_settings.prefix, _source_label(context, "CGYY_PREFIX"), "签名前缀"),
            (bool(api_settings.app_key), "CGYY_APP_KEY", api_settings.app_key, _source_label(context, "CGYY_APP_KEY"), "应用标识"),
            (bool(api_settings.aes_cbc_key), "CGYY_AES_CBC_KEY", api_settings.aes_cbc_key,
             _source_label(context, "CGYY_AES_CBC_KEY"), "订单加密 key"),
            (bool(api_settings.aes_cbc_iv), "CGYY_AES_CBC_IV", api_settings.aes_cbc_iv,
             _source_label(context, "CGYY_AES_CBC_IV"), "订单加密 iv"),
            (bool(user_settings.phone), "CGYY_PHONE", user_settings.phone, _source_label(context, "CGYY_PHONE"), "手机号"),
            (api_settings.venue_site_id > 0, "CGYY_VENUE_SITE_ID", api_settings.venue_site_id,
             _source_label(context, "CGYY_VENUE_SITE_ID"), "场地 siteId"),
            (user_settings.reservation_slot_count > 0, "CGYY_RESERVATION_SLOT_COUNT",
             user_settings.reservation_slot_count, _source_label(context, "CGYY_RESERVATION_SLOT_COUNT"), "连续时段数"),
            (bool(user_settings.selection_strategy), "CGYY_SELECTION_STRATEGY",
             user_settings.selection_strategy, _source_label(context, "CGYY_SELECTION_STRATEGY"), "筛选策略"),
        ]

        print("   📋 基础配置")
        for ok, key, value, source, note in checks:
            _print_item(ok, key, value, source, note)
            if not ok:
                critical_missing.append(key)

        print("   👤 预约信息")
        _print_item(
            bool(
                user_settings.display_name),
            "CGYY_DISPLAY_NAME",
            user_settings.display_name,
            _source_label(
                context,
                "CGYY_DISPLAY_NAME"),
            "显示名，可选")
        _print_item(
            True,
            "CGYY_RESERVATION_START_TIME",
            user_settings.reservation_start_time or "-",
            _source_label(
                context,
                "CGYY_RESERVATION_START_TIME"),
            "开始时间，空表示任意时段")
        buddy_ok = bool(user_settings.buddy_ids)
        _print_item(
            buddy_ok,
            "CGYY_BUDDY_IDS",
            user_settings.buddy_ids,
            _source_label(
                context,
                "CGYY_BUDDY_IDS"),
            "同伴 ID，可选，部分场地下单必需")
        if not buddy_ok:
            warnings.append("CGYY_BUDDY_IDS")

        print("   🔐 鉴权配置")
        auth_ok = bool(auth_settings.cookie and auth_settings.cg_authorization)
        sso_enabled = bool(sso_settings.enabled)
        sso_missing: list[str] = []
        _print_item(
            bool(
                auth_settings.cookie),
            "CGYY_COOKIE",
            auth_settings.cookie,
            _source_label(
                context,
                "CGYY_COOKIE"),
            "业务 cookie")
        _print_item(
            bool(
                auth_settings.cg_authorization),
            "CGYY_CG_AUTH",
            auth_settings.cg_authorization,
            _source_label(
                context,
                "CGYY_CG_AUTH"),
            "业务鉴权头")
        _print_item(
            True,
            "CGYY_SSO_ENABLED",
            sso_enabled,
            _source_label(
                context,
                "CGYY_SSO_ENABLED"),
            "是否启用 SSO 自动登录")
        if sso_enabled:
            login_url_ok = bool(sso_settings.login_base_url)
            service_url_ok = bool(sso_settings.service_url)
            username_ok = bool(sso_settings.username)
            password_ok = bool(sso_settings.password)
            _print_item(
                login_url_ok,
                "CGYY_SSO_LOGIN_URL",
                sso_settings.login_base_url,
                _source_label(
                    context,
                    "CGYY_SSO_LOGIN_URL"),
                "SSO 登录地址")
            _print_item(
                service_url_ok,
                "CGYY_SSO_SERVICE_URL",
                sso_settings.service_url,
                _source_label(
                    context,
                    "CGYY_SSO_SERVICE_URL"),
                "SSO 服务地址")
            _print_item(
                username_ok,
                "CGYY_SSO_USERNAME",
                sso_settings.username,
                _source_label(
                    context,
                    "CGYY_SSO_USERNAME"),
                "SSO 账号")
            _print_item(
                password_ok,
                "CGYY_SSO_PASSWORD",
                sso_settings.password,
                _source_label(
                    context,
                    "CGYY_SSO_PASSWORD"),
                "SSO 密码")
            if not login_url_ok:
                sso_missing.append("CGYY_SSO_LOGIN_URL")
            if not service_url_ok:
                sso_missing.append("CGYY_SSO_SERVICE_URL")
            if not username_ok:
                sso_missing.append("CGYY_SSO_USERNAME")
            if not password_ok:
                sso_missing.append("CGYY_SSO_PASSWORD")

        sso_ready = sso_enabled and not sso_missing
        if auth_ok:
            if sso_enabled and sso_missing:
                warnings.append(f"SSO 回退配置缺少 {', '.join(sso_missing)}")
        else:
            if sso_ready:
                warnings.append("当前未配置 CGYY_COOKIE/CGYY_CG_AUTH，将依赖 SSO 自动登录")
            else:
                reason = "缺少可用鉴权：未配置 CGYY_COOKIE/CGYY_CG_AUTH"
                if not sso_enabled:
                    reason += "，且未启用 SSO 自动登录"
                elif sso_missing:
                    reason += f"，SSO 配置缺少 {', '.join(sso_missing)}"
                else:
                    reason += "，且 SSO 配置不完整"
                auth_blockers.append(reason)

        if getattr(args, "probe", False):
            probe = _auth_probe_result(
                context,
                api_settings,
                auth_settings,
                sso_settings,
            )
            probe_ok = bool(probe.reused and probe.state and probe.state.cookie and probe.state.cg_authorization)
            state = probe.state or ServiceAuthState(service_name="cgyy")
            _print_item(probe_ok, "AUTH_PROBE", "可用" if probe_ok else "失败", state.source or "env", "实时探活")
            if not probe_ok:
                if auth_ok and not sso_ready:
                    auth_blockers.append("当前鉴权探活失败，且无可用 SSO 回退")
                else:
                    warnings.append("AUTH_PROBE")

        summary_parts: list[str] = []
        if critical_missing:
            summary_parts.append(f"缺少关键配置 {', '.join(critical_missing)}")
        if auth_blockers:
            summary_parts.extend(auth_blockers)
        if warnings:
            summary_parts.append(f"存在提醒项 {'；'.join(warnings)}")
        if not summary_parts:
            summary_parts.append("配置完整，可继续查询/预约")
        print()
        is_healthy = not critical_missing and not auth_blockers
        print(format_request_result("诊断结论", is_healthy, "；".join(summary_parts)))
        if critical_missing or auth_blockers:
            print("   💡 先补齐关键配置，再执行预约相关命令。")
        elif warnings:
            print("   💡 当前可运行，但提醒项可能在部分场景下影响下单。")
    except Exception as exc:
        logger.exception("配置诊断失败")
        print(format_request_result("配置诊断", False, str(exc)))


def handle_config_doctor(context: CommandContext, args: Namespace) -> None:
    run_config_doctor(context, args)
