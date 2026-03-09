"""从多个可预约方案中选取一个的策略（过滤 + 排序 + 选择）。"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Protocol

from src.parsers.slot_filter import SlotSolution

logger = logging.getLogger(__name__)

DEFAULT_STRATEGY_SPEC = "same_first_digit,same_venue,cheapest"


class SolutionStrategy(Protocol):
    """针对 SlotSolution 列表的通用策略接口（既可 filter 也可 sort）。"""

    name: str

    def apply(self, solutions: List[SlotSolution]) -> List[SlotSolution]:
        ...


@dataclass
class SameFirstDigitFilter:
    """同首位场地号优先（soft filter）。"""

    name: str = "same_first_digit"

    def apply(self, solutions: List[SlotSolution]) -> List[SlotSolution]:
        if not solutions:
            return solutions
        kept: List[SlotSolution] = []
        for s in solutions:
            first_digits = {str(c.space_id)[0] for c in s.choices if c.space_id}
            if first_digits and len(first_digits) == 1:
                kept.append(s)
        # soft filter：若过滤后非空，则使用过滤结果；否则保留原列表
        return kept or solutions


@dataclass
class SameVenueFilter:
    """同一场地优先（soft filter）：仅保留所有时段都在同一 space_id 的方案。"""

    name: str = "same_venue"

    def apply(self, solutions: List[SlotSolution]) -> List[SlotSolution]:
        if not solutions:
            return solutions
        kept: List[SlotSolution] = []
        for s in solutions:
            space_ids = {c.space_id for c in s.choices if c.space_id}
            if space_ids and len(space_ids) == 1:
                kept.append(s)
        return kept or solutions


@dataclass
class CheapestSorter:
    """按总价升序排序。"""

    name: str = "cheapest"

    def apply(self, solutions: List[SlotSolution]) -> List[SlotSolution]:
        return sorted(solutions, key=lambda s: s.total_fee)


_BUILTIN_STRATEGIES: dict[str, SolutionStrategy] = {
    "same_first_digit": SameFirstDigitFilter(),
    "same_venue": SameVenueFilter(),
    "cheapest": CheapestSorter(),
}


def parse_strategy_spec(spec: str | None) -> List[str]:
    """
    将逗号分隔的策略字符串解析为策略名列表。
    空值 / 仅空白时使用默认策略。
    """
    raw = (spec or "").strip()
    if not raw:
        raw = DEFAULT_STRATEGY_SPEC
    parts = [p.strip() for p in raw.split(",")]
    # 去重并保留顺序
    seen: set[str] = set()
    result: List[str] = []
    for p in parts:
        if not p or p in seen:
            continue
        if p not in _BUILTIN_STRATEGIES:
            logger.warning("忽略未知策略名 '%s'，可用策略：%s", p, ", ".join(_BUILTIN_STRATEGIES))
            continue
        seen.add(p)
        result.append(p)
    return result


class StrategyPipeline:
    """按顺序依次应用若干策略（filter + sort）。"""

    def __init__(self, strategy_names: List[str]) -> None:
        self.strategy_names = strategy_names
        self.strategies: List[SolutionStrategy] = [
            _BUILTIN_STRATEGIES[name] for name in strategy_names if name in _BUILTIN_STRATEGIES
        ]

    def apply(self, solutions: List[SlotSolution]) -> List[SlotSolution]:
        for s in self.strategies:
            solutions = s.apply(solutions)
        return solutions


def apply_pipeline(solutions: List[SlotSolution], spec: str | None) -> List[SlotSolution]:
    """根据策略配置字符串对方案列表做过滤与排序。"""
    names = parse_strategy_spec(spec)
    if not names:
        return solutions
    pipeline = StrategyPipeline(names)
    return pipeline.apply(solutions)
