"""将用户输入规范化为标准格式，便于后续校验与使用。"""
from __future__ import annotations

import re
from datetime import date


def normalize_date(raw: str | None) -> str | None:
    """
    将宽松日期输入规范化为 YYYY-MM-DD。
    支持：2025-12-6, 25-12-6, 2025/12/6, 2025.12.6 等。
    两位年份 00-99 视为 2000-2099。
    无法解析时返回 None（由 validators 报错）。
    """
    if not raw or not (s := raw.strip()):
        return None
    s = re.sub(r"[/.]", "-", s)
    # YYYY-M-D 或 YYYY-MM-DD
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.match(r"^(\d{2})-(\d{1,2})-(\d{1,2})$", s)
        if m:
            yy, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            y = 2000 + yy if yy < 100 else yy
        else:
            return None
    try:
        dt = date(y, mo, d)
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def normalize_time(raw: str | None) -> str | None:
    """
    将宽松时间输入规范化为 HH:MM。
    支持：9 -> 09:00, 9.0 -> 09:00, 9.5 -> 09:30, 21.5 -> 21:30,
          09:00, 9:30 等。小数部分 <0.25 视为 :00，0.25~0.75 视为 :30，否则拒绝。
    无法解析时返回 None。
    """
    if not raw or not (s := raw.strip()):
        return None
    s = s.strip()
    # 已有冒号：H:MM 或 HH:MM
    m = re.match(r"^(\d{1,2}):(\d{1,2})$", s)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h < 24 and 0 <= mi < 60:
            return f"{h:02d}:{mi:02d}"
        return None
    # 数字或小数：9, 9.0, 9.5
    m = re.match(r"^(\d{1,2})(?:\.(\d+))?$", s)
    if not m:
        return None
    h = int(m.group(1))
    if h < 0 or h >= 24:
        return None
    frac = m.group(2)
    if not frac or frac == "0" or all(c == "0" for c in frac):
        return f"{h:02d}:00"
    # 支持 .5 或 .50 等表示半点
    frac_val = int(frac.ljust(2, "0")[:2])  # 取前两位，如 "5" -> 50
    if 25 <= frac_val <= 75:
        return f"{h:02d}:30"
    if frac_val < 25:
        return f"{h:02d}:00"
    return None  # > .75 不自动进位，视为无效


def normalize_buddies(raw: str | None) -> str | None:
    """
    将同伴 ID 字符串规范化为逗号分隔、无多余空格的字符串。
    例如 " 7876 , 3343 " -> "7876,3343"。空或仅空白返回 None。
    """
    if not raw or not (s := raw.strip()):
        return None
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if not parts:
        return None
    return ",".join(parts)


def normalize_positive_int(raw: int | str | None) -> int | None:
    """将整数参数规范化：None 保持 None，否则确保为正整数。不修改合法值。"""
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    s = str(raw).strip()
    if not s:
        return None
    try:
        n = int(s)
        return n if n > 0 else None
    except ValueError:
        return None
