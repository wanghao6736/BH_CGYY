"""CGYY CLI 参数解析。子命令：reserve（默认）, info, catalog, fetch-captcha, verify-captcha, order-detail, cancel-order。"""
from __future__ import annotations

import argparse


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    """为 info/reserve 等添加共用选项。"""
    parser.add_argument(
        "-d",
        "--date",
        default=None,
        help="查询/预约日期 (YYYY-MM-DD)，info 与 reserve 共用",
    )
    parser.add_argument(
        "-v",
        "--venue-site-id",
        dest="venue_site_id",
        nargs="?",
        type=int,
        default=None,
        const=-1,
        help="场地 siteId；catalog 时筛选展示，info/reserve 时覆盖本次调用",
    )
    parser.add_argument(
        "-s",
        "--start-time",
        dest="start_time",
        default=None,
        help="info/reserve 开始时间 (HH:MM)，不传则返回所有时段方案",
    )
    parser.add_argument(
        "-n",
        "--duration",
        dest="duration",
        type=int,
        default=None,
        help="info/reserve 连续时段数，不传则默认为 1",
    )
    parser.add_argument(
        "-b",
        "--buddies",
        dest="buddies",
        default=None,
        help="reserve 同伴 ID 列表，逗号分隔（如 7876,3343）",
    )
    parser.add_argument(
        "-p",
        "--show-order-param",
        dest="show_order_param",
        action="store_true",
        help="info 时同时展示 orderParamView（同伴列表）",
    )
    parser.add_argument(
        "-t",
        "--trade-no",
        dest="trade_no",
        default=None,
        help="订单编号，order-detail / cancel-order 必填",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CGYY 自动预约")
    sub = parser.add_subparsers(dest="cmd", required=False, help="子命令")

    # 子命令后的 -d -v 等由对应子解析器解析，因此需在各子命令上添加共用选项
    for name, help_text in [
        ("reserve", "完整预约（默认）"),
        ("info", "查询场地信息与可预约方案"),
        ("catalog", "场地目录"),
        ("fetch-captcha", "获取验证码"),
        ("verify-captcha", "识别并校验验证码"),
        ("order-detail", "查询订单详情"),
        ("cancel-order", "取消订单"),
    ]:
        subp = sub.add_parser(name, help=help_text)
        _add_common_options(subp)

    return parser
