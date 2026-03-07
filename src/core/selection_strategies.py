"""从多个可预约方案中选取一个的策略。"""
from __future__ import annotations

from src.parsers.slot_filter import SlotSolution


def pick_solution(solutions: list[SlotSolution], mode: str = "first") -> SlotSolution:
    """
    从方案列表中选取一个方案。
    - first: 取第一个（当前默认行为）
    - cheapest: 按 total_fee 升序取最便宜
    """
    if not solutions:
        raise ValueError("方案列表为空")
    if mode == "cheapest":
        return min(solutions, key=lambda s: s.total_fee)
    return solutions[0]
