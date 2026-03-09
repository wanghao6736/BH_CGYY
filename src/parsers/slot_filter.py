"""Enumerate all feasible slot solutions for a given date/start/slot_count.

本模块只负责**枚举**满足连续时段要求的所有组合解，不做任何"同场地优先 / 价格优先"等偏好过滤，
这些策略由 `src.core.selection_strategies` 负责。
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import List

from src.parsers.day_info import (DayInfoParsed, SlotState, SpaceSchedule,
                                  TimeSlot)


@dataclass
class SlotChoice:
    """单一时段：何时、何地、哪块场地、该时段费用。"""

    space_id: int
    time_id: int
    space_name: str = ""
    start_time: str = ""
    end_time: str = ""
    order_fee: float = 0.0


@dataclass
class SlotSolution:
    """一组可预约方案：若干时段 + 总费用 + 时段数 + 真实总时长。"""

    choices: List[SlotChoice] = field(default_factory=list)
    total_fee: float = 0.0
    slot_count: int = 0
    total_hours: float = 0.0


def _time_id_to_range(time_slots: List[TimeSlot]) -> dict[int, tuple[str, str]]:
    """time_id -> (begin_time, end_time)."""
    return {t.id: (t.begin_time, t.end_time) for t in time_slots}


def _parse_hhmm_to_minutes(hhmm: str) -> int | None:
    """'HH:MM' -> 总分钟数，解析失败返回 None。"""
    parts = hhmm.split(":")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        return None


def _calc_total_hours(choices: List[SlotChoice]) -> float:
    """根据各时段的 start_time/end_time 计算真实总时长（小时）。"""
    total_minutes = 0
    for c in choices:
        s = _parse_hhmm_to_minutes(c.start_time)
        e = _parse_hhmm_to_minutes(c.end_time)
        if s is not None and e is not None and e > s:
            total_minutes += e - s
    return round(total_minutes / 60, 1)


def _consecutive_time_ids(
    time_slots: List[TimeSlot], start_time: str, slot_count: int
) -> List[int]:
    """返回从 start_time 起连续 slot_count 个 timeSlot 的 id 列表。"""
    sorted_slots = sorted(time_slots, key=lambda t: t.begin_time)
    start_idx = None
    for i, t in enumerate(sorted_slots):
        if t.begin_time == start_time:
            start_idx = i
            break
    if start_idx is None:
        return []
    end_idx = start_idx + slot_count
    if end_idx > len(sorted_slots):
        return []
    return [sorted_slots[j].id for j in range(start_idx, end_idx)]


def _make_choice(
    space: SpaceSchedule,
    tid: int,
    time_range: dict[int, tuple[str, str]],
    default_state: SlotState,
) -> SlotChoice:
    st = space.slots.get(str(tid), default_state)
    beg, end = time_range.get(tid, ("", ""))
    fee = float(st.order_fee or 0)
    return SlotChoice(
        space_id=space.space_id,
        time_id=tid,
        space_name=space.space_name,
        start_time=beg,
        end_time=end,
        order_fee=fee,
    )


def _to_solution(choices: List[SlotChoice]) -> SlotSolution:
    total = sum(c.order_fee for c in choices)
    return SlotSolution(
        choices=choices,
        total_fee=total,
        slot_count=len(choices),
        total_hours=_calc_total_hours(choices),
    )


def _enumerate_solutions_for_ids(
    schedules: List[SpaceSchedule],
    required_ids: List[int],
    time_range: dict[int, tuple[str, str]],
) -> List[SlotSolution]:
    """枚举给定一组 time_id 的所有可行组合解（每个 time_id 在某个可用场地上）。"""
    if not required_ids or not schedules:
        return []

    default_state = SlotState(reservation_status=4, is_available=False, order_fee=0.0)

    available_per_tid: list[list[SpaceSchedule]] = []
    for tid in required_ids:
        candidates: list[SpaceSchedule] = []
        for space in schedules:
            state = space.slots.get(str(tid), default_state)
            if state.is_available:
                candidates.append(space)
        if not candidates:
            return []
        available_per_tid.append(candidates)

    solutions: List[SlotSolution] = []
    seen: set[tuple[tuple[int, int], ...]] = set()

    for spaces_combo in itertools.product(*available_per_tid):
        choices: List[SlotChoice] = []
        for tid, space in zip(required_ids, spaces_combo):
            choices.append(_make_choice(space, tid, time_range, default_state))
        key = tuple((c.space_id, c.time_id) for c in choices)
        if key in seen:
            continue
        seen.add(key)
        solutions.append(_to_solution(choices))

    return solutions


def _distinct_start_times(time_slots: List[TimeSlot]) -> List[str]:
    """Return sorted distinct begin_time values from time_slots."""
    return sorted({t.begin_time for t in time_slots})


def find_solutions(
    parsed: DayInfoParsed,
    date: str,
    start_time: str | None,
    slot_count: int,
) -> List[SlotSolution]:
    """
    枚举指定日期、开始时间与连续时段数下的所有可预约方案。

    - start_time 不为 None：仅从该开始时间起枚举一组连续时段；
    - start_time 为 None：对当日每个可能的开始时间分别枚举，并返回所有方案的并集。
    """
    time_range = _time_id_to_range(parsed.time_slots)
    schedules = parsed.space_schedules_by_date.get(date, [])
    if not schedules or not parsed.time_slots:
        return []

    all_solutions: List[SlotSolution] = []
    seen: set[tuple[tuple[int, int], ...]] = set()

    def _add_solutions_for_start(st: str) -> None:
        required_ids = _consecutive_time_ids(parsed.time_slots, st, slot_count)
        if not required_ids:
            return
        sols = _enumerate_solutions_for_ids(schedules, required_ids, time_range)
        for s in sols:
            key = tuple((c.space_id, c.time_id) for c in s.choices)
            if key in seen:
                continue
            seen.add(key)
            all_solutions.append(s)

    if start_time:
        _add_solutions_for_start(start_time)
    else:
        for st in _distinct_start_times(parsed.time_slots):
            _add_solutions_for_start(st)

    return all_solutions
