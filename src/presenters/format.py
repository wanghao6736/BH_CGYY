"""用户友好输出：请求结果、方案表格、订单结果等，带 emoji。"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from tabulate import tabulate

from src.core.payment_service import PaymentTargetResult
from src.parsers.catalog import SiteItem, SportItem
from src.parsers.day_info import Buddy, SiteParam
from src.parsers.order import OrderDetailParsed, SubmitParsed
from src.parsers.slot_filter import SlotSolution

_WEEKDAY_CN = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")


def _date_with_weekday(date_str: str) -> str:
    """'2026-03-07' -> '2026-03-07 星期六'。解析失败时原样返回。"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{date_str} {_WEEKDAY_CN[dt.weekday()]}"
    except (ValueError, IndexError):
        return date_str


def format_site_line(site_param: Optional[SiteParam]) -> str:
    """格式化为一行场地信息，如：📍 校区-场馆-项目。"""
    if not site_param:
        return ""
    return f"📍 {site_param.campus_name}{site_param.venue_name}-{site_param.site_name}"


def format_request_result(name: str, success: bool, message: str = "") -> str:
    """统一格式：请求是否成功 + 简短说明。"""
    icon = "✅" if success else "❌"
    status = "成功" if success else "失败"
    line = f"{icon} [{status}] {name}"
    if message:
        line += f"：{message}"
    return line


def format_solutions_table(
    solutions: List[SlotSolution],
    date: str,
    site_param: Optional[SiteParam] = None,
) -> str:
    """将可预约方案列表格式化为表格；若有 site_param 则显示场地信息（如 XX校区游泳馆）。"""
    if not solutions:
        return "📋 暂无满足条件的可预约方案。"
    lines = []
    site_line = format_site_line(site_param)
    if site_line:
        lines.append(site_line)
    lines.append(f"📅 预约日期 {_date_with_weekday(date)}")
    rows = []
    for i, sol in enumerate(solutions, 1):
        for j, c in enumerate(sol.choices):
            rows.append([
                i if j == 0 else "",
                c.space_name or str(c.space_id),
                f"{c.start_time}-{c.end_time}",
                f"¥{c.order_fee}",
                f"¥{sol.total_fee}" if j == 0 else "",
                f"{sol.slot_count}段/{sol.total_hours:.1f}h" if j == 0 else "",
            ])
    headers = ["📋 方案", "场地", "🕐 时段", "单价", "💰 总价", "时长"]
    table = tabulate(rows, headers=headers, tablefmt="simple", stralign="left")
    lines.append(table)
    lines.append(f"📊 共 {len(solutions)} 个方案 | 💡 默认将使用第 1 个方案下单。")
    return "\n".join(lines)


def format_submit_result(
    success: bool,
    message: str,
    submit_parsed: Optional[SubmitParsed] = None,
    *,
    display_name: str = "",
    profile_name: str = "",
) -> str:
    """提交订单结果。"""
    line = format_request_result("提交订单", success, message)
    if success and submit_parsed:
        line += f"\n   📌 订单ID {submit_parsed.order_id} | 编号 {submit_parsed.trade_no}"
        line += f"\n   🕐 预约时间 {submit_parsed.reservation_start_date} ~ {submit_parsed.reservation_end_date}"
        if display_name or profile_name:
            line += f"\n   👤 预定人 {display_name or profile_name} | profile {profile_name or '-'}"
    return line


def format_order_detail(parsed: OrderDetailParsed) -> str:
    """订单详情：日期、地点、时间、场地列表、状态、支付截止等。"""
    lines = [
        f"📅 {parsed.subject_desc}",
        f"📍 {parsed.subject}",
        f"🕐 {parsed.start_date} ~ {parsed.end_date}",
    ]
    if parsed.space_list:
        rows = [
            [s.space_name, f"{s.start_time}-{s.end_time}", f"¥{s.order_fee}"]
            for s in parsed.space_list
        ]
        lines.append("📋 场地列表：")
        lines.append(tabulate(rows, headers=["场地", "时段", "费用"], tablefmt="simple", stralign="left"))
    lines.append(f"🆔 订单ID {parsed.order_id} | UUID {parsed.order_uuid or '-'}")
    lines.append(f"💰 价格 ¥{parsed.pay_fee} | 付款人ID {parsed.pay_user_id}")
    order_status = "已取消" if parsed.order_status == 2 else f"{parsed.order_status}"
    pay_status = "已支付" if parsed.pay_status == 1 else f"{parsed.pay_status}"
    lines.append(f"📊 订单状态 {order_status} | 付款状态 {pay_status}")
    lines.append(f"⏰ 下单时间 {parsed.gmt_create} | 支付截止 {parsed.expire_time}")
    return "\n".join(lines)


def format_buddy_list(buddies: List[Buddy]) -> str:
    """格式化 buddy 列表，展示 id 与 name，便于用户写入 profile 配置。"""
    if not buddies:
        return "👥 可选同伴：暂无数据。"
    rows = [[b.id, b.name, b.user_id] for b in buddies]
    table = tabulate(rows, headers=["id", "姓名", "userId"], tablefmt="simple", stralign="left")
    tip = "💡 请将需要使用的同伴 id 配置到当前 profile 的 CGYY_BUDDY_IDS 中（逗号分隔），下单时将只使用该配置。"
    return "👥 可选同伴\n" + table + "\n" + tip


def format_catalog_sports_table(sports: List[SportItem]) -> str:
    if not sports:
        return "🏷️ 运动类型：暂无数据。"
    rows = [[s.id, s.code_name, s.code_key] for s in sports]
    table = tabulate(rows, headers=["ID", "名称", "codeKey"], tablefmt="simple", stralign="left")
    return "🏷️ 运动类型\n" + table


def format_catalog_sites_table(sites: List[SiteItem], venue_site_id: Optional[int] = None) -> str:
    if venue_site_id is not None:
        sites = [s for s in sites if s.site_id == int(venue_site_id)]
    if not sites:
        if venue_site_id is None:
            return "🏟️ 场地列表：暂无数据。"
        return f"🏟️ 场地列表：未找到 siteId={venue_site_id} 的场地。"
    rows = [[s.site_id, s.campus_name, s.venue_name, s.site_name] for s in sites]
    table = tabulate(rows, headers=["siteId", "校区", "场馆", "项目"], tablefmt="simple", stralign="left")
    tip = "💡 siteId 即预约接口使用的 venueSiteId（可写入 default 或当前 profile 的 CGYY_VENUE_SITE_ID）。"
    return "🏟️ 场地列表\n" + table + "\n" + tip


def format_payment_result(
    result: PaymentTargetResult,
    *,
    display_name: str = "",
    profile_name: str = "",
) -> str:
    if result.mode == "desktop":
        lines = [
            "💳 支付模式 desktop",
            f"🔗 schoolPayUrl {result.resolved_target}",
        ]
    else:
        lines = [f"💳 支付模式 mobile | 支付方式 {result.pay_way_name or '-'}"]
        if result.cashier and result.transaction:
            lines.append(
                f"🆔 cashierId {result.cashier.cashier_id} | goodsId {result.transaction.goods_id}"
            )
            lines.append(
                f"📍 订单 {result.transaction.subject or '-'} | 金额 ¥{result.transaction.money}"
            )
        lines.append(f"🎯 微信跳转 {result.resolved_target}")
    if display_name or profile_name:
        lines.append(f"👤 当前身份 {display_name or profile_name} | profile {profile_name or '-'}")
    return "\n".join(lines)
