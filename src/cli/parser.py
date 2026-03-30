"""CGYY CLI 参数解析。子命令：reserve（默认）, info, catalog, config-doctor, fetch-captcha, verify-captcha, order-detail, cancel-order, login, auth-status, logout, profile。"""
from __future__ import annotations

import argparse


def _add_profile_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-P",
        "--profile",
        default=None,
        help="使用的 profile 名称，默认 default",
    )


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    """为 info/reserve 等添加共用选项。"""
    _add_profile_option(parser)
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
        help="info/reserve 连续时段数，不传则沿用当前配置",
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
    parser.add_argument(
        "-S",
        "--strategy",
        dest="strategy",
        default=None,
        help=(
            "场地筛选策略，逗号分隔，例如 same_first_digit,same_venue,cheapest；"
            "不指定则使用环境变量 CGYY_SELECTION_STRATEGY 或默认策略"
        ),
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
        ("login", "执行 SSO 自动登录并刷新当前 profile 鉴权信息"),
        ("auth-status", "查看当前 profile 鉴权状态"),
        ("logout", "清空当前 profile 中的鉴权信息"),
    ]:
        subp = sub.add_parser(name, help=help_text)
        _add_common_options(subp)

    doctor_parser = sub.add_parser("config-doctor", help="诊断当前 profile 配置与鉴权状态")
    _add_profile_option(doctor_parser)
    doctor_parser.add_argument(
        "--probe",
        action="store_true",
        help="额外发起一次鉴权探活请求",
    )

    profile_parser = sub.add_parser("profile", help="管理 profile 配置")
    profile_sub = profile_parser.add_subparsers(dest="profile_cmd", required=True, help="profile 子命令")

    profile_sub.add_parser("list", help="列出 profile")

    show_parser = profile_sub.add_parser("show", help="查看 profile")
    show_parser.add_argument("name", help="profile 名称")

    add_parser = profile_sub.add_parser("add", help="新增 profile")
    add_parser.add_argument("name", help="profile 名称")
    add_parser.add_argument(
        "-s",
        "--set",
        dest="set_values",
        action="append",
        default=[],
        help="设置 KEY=VALUE，可重复",
    )

    modify_parser = profile_sub.add_parser("modify", help="修改 profile")
    modify_parser.add_argument("name", help="profile 名称")
    modify_parser.add_argument(
        "-s",
        "--set",
        dest="set_values",
        action="append",
        default=[],
        help="设置 KEY=VALUE，可重复",
    )
    modify_parser.add_argument(
        "-u",
        "--unset",
        dest="unset_keys",
        action="append",
        default=[],
        help="移除指定 KEY，可重复",
    )

    cleanup_parser = profile_sub.add_parser("cleanup-legacy-sso", help="清理 profile 中遗留的 SSO 账号密码字段")
    cleanup_parser.add_argument("name", help="profile 名称")

    remove_parser = profile_sub.add_parser("remove", help="删除 profile")
    remove_parser.add_argument("name", help="profile 名称")
    remove_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="确认删除",
    )

    return parser
