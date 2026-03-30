from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from src.config.profiles import ProfileManager
from src.core.exceptions import BuddyConfigError, CaptchaError, QueryError

LEGACY_SSO_KEYS = ("CGYY_SSO_USERNAME", "CGYY_SSO_PASSWORD")


def display_name(profile_name: str, configured_name: str = "") -> str:
    return configured_name or profile_name


def print_identity(profile_name: str, configured_name: str = "") -> None:
    print(f"   👤 当前身份 {display_name(profile_name, configured_name)} | profile {profile_name}")


def parse_updates(items: list[str] | None) -> dict[str, str]:
    updates: dict[str, str] = {}
    for item in items or []:
        key, value = item.split("=", 1)
        updates[key] = value
    return updates


def print_reserve_hints(exc: Exception) -> None:
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
    for hint in hints:
        print(f"   → {hint}")


def print_legacy_sso_notice(profile_name: str) -> None:
    print(f"   💡 {profile_name} 中的 CGYY_SSO_USERNAME / CGYY_SSO_PASSWORD 仅供 CLI 自动化模式使用。")
    print(f"   💡 GUI 登录已不再使用这两个字段，可执行 `python -m src.main profile cleanup-legacy-sso {profile_name}` 清理。")


def has_legacy_sso_values(profile_manager: ProfileManager, profile_name: str) -> bool:
    values = profile_manager.show_profile(profile_name)
    present = {item.key for item in values if item.value and item.value != "(missing)"}
    return any(key in present for key in LEGACY_SSO_KEYS)


def get_profile_name_from_env_path(path_name: str) -> str:
    if path_name == ".env":
        return "default"
    path = Path(path_name)
    return path.stem if path.suffix == ".env" else path.name
