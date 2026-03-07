"""Filter available slots by start time, duration, and same-space-id-first-digit rule."""

from __future__ import annotations

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
    """一组可预约方案：若干时段 + 总费用 + 总时长。"""

    choices: List[SlotChoice] = field(default_factory=list)
    total_fee: float = 0.0
    duration_hours: float = 0.0


def _first_digit(sid: int) -> str:
    return str(sid)[0] if sid else ""


def _time_id_to_range(time_slots: List[TimeSlot]) -> dict[int, tuple[str, str]]:
    """time_id -> (begin_time, end_time)."""
    return {t.id: (t.begin_time, t.end_time) for t in time_slots}


def _consecutive_time_ids(
    time_slots: List[TimeSlot], start_time: str, duration_hours: int
) -> List[int]:
    """Return list of time_slot ids covering [start_time, start_time + duration_hours)."""
    sorted_slots = sorted(time_slots, key=lambda t: t.begin_time)
    n = len(sorted_slots)
    start_idx = None
    for i, t in enumerate(sorted_slots):
        if t.begin_time == start_time:
            start_idx = i
            break
    if start_idx is None:
        return []
    end_idx = min(start_idx + duration_hours, n)
    return [sorted_slots[j].id for j in range(start_idx, end_idx)]


def find_available_slots(
    parsed: DayInfoParsed,
    date: str,
    start_time: str,
    duration_hours: int,
    allow_multi_space: bool = True,
    require_same_first_digit: bool = True,
) -> List[SlotSolution]:
    """
    找出覆盖 [start_time, start_time + duration_hours) 的所有可预约方案。
    每个方案包含：各时段在何场地、开始/结束时间、该时段费用，以及总费用和总时长。
    """
    required_ids = _consecutive_time_ids(parsed.time_slots, start_time, duration_hours)
    if not required_ids:
        return []

    time_range = _time_id_to_range(parsed.time_slots)
    schedules = parsed.space_schedules_by_date.get(date, [])
    _unavail = SlotState(reservation_status=4, is_available=False, order_fee=0.0)
    solutions: List[SlotSolution] = []

    def make_choice(space: SpaceSchedule, tid: int) -> SlotChoice:
        st = space.slots.get(str(tid), _unavail)
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

    def to_solution(choices: List[SlotChoice]) -> SlotSolution:
        total = sum(c.order_fee for c in choices)
        return SlotSolution(choices=choices, total_fee=total, duration_hours=float(len(choices)))

    # 单场地：该场地所有所需时段均空闲
    for space in schedules:
        if all(space.slots.get(str(tid), _unavail).is_available for tid in required_ids):
            choices = [make_choice(space, tid) for tid in required_ids]
            solutions.append(to_solution(choices))

    if not allow_multi_space or not require_same_first_digit:
        return solutions

    # 多场地：每个时段由不同场地覆盖，场地 id 首位相同
    by_tid: dict[int, List[tuple[SpaceSchedule, int, str]]] = {tid: [] for tid in required_ids}
    for space in schedules:
        for tid in required_ids:
            if space.slots.get(str(tid), _unavail).is_available:
                by_tid[tid].append((space, space.space_id, space.space_name))

    all_first_digits = set()
    for tid in required_ids:
        for _, sid, _ in by_tid[tid]:
            all_first_digits.add(_first_digit(sid))

    for fd in all_first_digits:
        choice_per_tid: List[SlotChoice] = []
        for tid in required_ids:
            candidates = [(sp, sid, sname) for sp, sid, sname in by_tid[tid] if _first_digit(sid) == fd]
            if not candidates:
                choice_per_tid = []
                break
            sp, _, _ = candidates[0]
            choice_per_tid.append(make_choice(sp, tid))
        if len(choice_per_tid) == len(required_ids):
            sol = to_solution(choice_per_tid)
            if not any(_same_choices(sol.choices, s.choices) for s in solutions):
                solutions.append(sol)

    return solutions


def _same_choices(a: List[SlotChoice], b: List[SlotChoice]) -> bool:
    if len(a) != len(b):
        return False
    return all((x.space_id == y.space_id and x.time_id == y.time_id) for x, y in zip(a, b))


def _distinct_start_times(time_slots: List[TimeSlot]) -> List[str]:
    """Return sorted distinct begin_time values from time_slots."""
    return sorted({t.begin_time for t in time_slots})


def find_available_slots_for_all_starts(
    parsed: DayInfoParsed,
    date: str,
    duration_hours: int,
    allow_multi_space: bool = True,
    require_same_first_digit: bool = True,
) -> List[SlotSolution]:
    """
    对当日每个可能的开始时间分别查询可预约方案，返回所有方案的并集。
    -s 不指定时使用此逻辑，返回所有满足时间段信息的方案。
    """
    starts = _distinct_start_times(parsed.time_slots)
    all_solutions: List[SlotSolution] = []
    seen: set[tuple[tuple[int, int], ...]] = set()

    for start_time in starts:
        sols = find_available_slots(
            parsed, date, start_time, duration_hours, allow_multi_space, require_same_first_digit
        )
        for s in sols:
            key = tuple((c.space_id, c.time_id) for c in s.choices)
            if key not in seen:
                seen.add(key)
                all_solutions.append(s)
    return all_solutions
