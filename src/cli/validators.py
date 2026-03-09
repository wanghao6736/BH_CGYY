from __future__ import annotations

from argparse import Namespace

from src.cli.normalize import (normalize_buddies, normalize_date,
                               normalize_positive_int, normalize_time)


class CliValidationError(ValueError):
    """命令行参数校验错误。"""


def validate_and_normalize_args(args: Namespace) -> Namespace:
    """
    对 CLI 参数做规范化与校验。
    - 日期：支持宽松格式，统一为 YYYY-MM-DD。
    - 时间：支持整数/小数/HH:MM，统一为 HH:MM。
    - 时段数/场地：必须为正整数。
    - 同伴：逗号分隔的非空 ID 列表。
    校验失败时抛 CliValidationError。
    """
    # 日期
    if getattr(args, "date", None):
        norm = normalize_date(args.date)
        if norm is None:
            raise CliValidationError(
                f"无效的日期 '{args.date}'，请使用类似 2025-12-06 / 2025/12/6 的格式。"
            )
        args.date = norm

    # 开始时间
    if getattr(args, "start_time", None):
        norm = normalize_time(args.start_time)
        if norm is None:
            raise CliValidationError(
                f"无效的开始时间 '{args.start_time}'，支持示例：9, 9.5, 09:00, 09:30。"
            )
        args.start_time = norm

    # 时段数
    if getattr(args, "duration", None) is not None:
        norm = normalize_positive_int(args.duration)
        if norm is None:
            raise CliValidationError(
                f"无效的时段数量 '{args.duration}'，必须为大于 0 的整数。"
            )
        args.duration = norm

    # 场地 ID（注意保留 -1 表示“使用 env 值”的语义）
    if getattr(args, "venue_site_id", None) is not None and args.venue_site_id != -1:
        norm = normalize_positive_int(args.venue_site_id)
        if norm is None:
            raise CliValidationError(
                f"无效的场地编号 '{args.venue_site_id}'，必须为大于 0 的整数。"
            )
        args.venue_site_id = norm

    # 同伴 ID 列表
    if getattr(args, "buddies", None):
        norm = normalize_buddies(args.buddies)
        if norm is None:
            raise CliValidationError(
                f"无效的同伴 ID 列表 '{args.buddies}'，请使用逗号分隔的 ID，例如 7876,3343。"
            )
        args.buddies = norm

    # 场地筛选策略字符串：目前仅做去首尾空白，具体策略名在业务层解析
    if getattr(args, "strategy", None):
        args.strategy = str(args.strategy).strip()

    return args
