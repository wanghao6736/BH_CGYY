from __future__ import annotations

from src.parsers.slot_filter import SlotChoice, SlotSolution
from src.ui.facade import BoardQuery, ReserveRequest
from src.ui.state import (BoardState, BookingFormState, SelectionState,
                          SettingsFormState)
from src.utils.buddy_ids import (clamp_buddy_ids, split_buddy_ids,
                                 supports_buddy_selection)


def build_board_query(profile_name: str, state: BookingFormState) -> BoardQuery:
    return BoardQuery(
        profile_name=profile_name,
        venue_site_id=state.venue_site_id,
        date=state.date,
        start_time=state.start_time,
        slot_count=state.slot_count,
    )


def _choice_key(choice: SlotChoice | None) -> tuple[int, int]:
    if choice is None:
        return (0, 0)
    return (choice.space_id, choice.time_id)


def _cell_choice(board_state: BoardState | None, *, row: int, col: int) -> SlotChoice | None:
    if board_state is None or row >= len(board_state.rows):
        return None
    row_state = board_state.rows[row]
    if col >= len(row_state.cells):
        return None
    cell = row_state.cells[col]
    if cell.reservation_status != 1:
        return None
    return SlotChoice(
        space_id=cell.space_id,
        time_id=cell.time_id,
        space_name=cell.space_name,
        start_time=cell.begin_time,
        end_time=cell.end_time,
        order_fee=cell.fee,
    )


def _solution_matches_prefix(solution: SlotSolution, prefix: list[SlotChoice]) -> bool:
    if len(prefix) > len(solution.choices):
        return False
    for index, choice in enumerate(prefix):
        if _choice_key(solution.choices[index]) != _choice_key(choice):
            return False
    return True


def matching_solutions(
    board_state: BoardState | None,
    selection_state: SelectionState | None,
) -> list[SlotSolution]:
    if board_state is None:
        return []
    prefix = selection_state.choices if selection_state is not None else []
    if not prefix:
        return list(board_state.solutions)
    return [item for item in board_state.solutions if _solution_matches_prefix(item, prefix)]


def resolve_selected_solution(
    board_state: BoardState | None,
    selection_state: SelectionState | None,
) -> SlotSolution | None:
    if board_state is None or selection_state is None:
        return None
    if len(selection_state.choices) != board_state.slot_count:
        return None
    matches = matching_solutions(board_state, selection_state)
    return matches[0] if matches else None


def resolve_active_solution(
    board_state: BoardState | None,
    selection_state: SelectionState | None,
) -> SlotSolution | None:
    selected = resolve_selected_solution(board_state, selection_state)
    if selected is not None:
        return selected
    if board_state is None:
        return None
    return board_state.recommended_solution


def resolve_reservable_solution(
    board_state: BoardState | None,
    selection_state: SelectionState | None,
) -> SlotSolution | None:
    selected = resolve_selected_solution(board_state, selection_state)
    if selected is not None:
        return selected
    if selection_state is not None and selection_state.choices:
        return None
    if board_state is None:
        return None
    return board_state.recommended_solution


def resolve_enabled_choice_keys(
    board_state: BoardState | None,
    selection_state: SelectionState | None,
) -> set[tuple[int, int]]:
    if board_state is None:
        return set()

    selected_choices = selection_state.choices if selection_state is not None else []
    enabled = {_choice_key(choice) for choice in selected_choices}
    matches = matching_solutions(board_state, selection_state)
    next_index = len(selected_choices)
    if next_index >= board_state.slot_count:
        return enabled

    for solution in matches:
        if next_index >= len(solution.choices):
            continue
        enabled.add(_choice_key(solution.choices[next_index]))
    return enabled


def build_selection_state(
    board_state: BoardState | None,
    *,
    row: int,
    col: int,
    current_selection: SelectionState | None = None,
) -> SelectionState | None:
    choice = _cell_choice(board_state, row=row, col=col)
    if choice is None or board_state is None:
        return current_selection

    current_choices = list(current_selection.choices) if current_selection is not None else []
    choice_key = _choice_key(choice)

    for index, selected in enumerate(current_choices):
        if _choice_key(selected) != choice_key:
            continue
        if index == len(current_choices) - 1:
            remaining = current_choices[:index]
        else:
            remaining = current_choices[: index + 1]
        return SelectionState(choices=remaining) if remaining else None

    enabled_keys = resolve_enabled_choice_keys(board_state, current_selection)
    if choice_key not in enabled_keys:
        return current_selection

    next_choices = current_choices + [choice]
    return SelectionState(choices=next_choices)


def build_reserve_request(
    profile_name: str,
    booking_state: BookingFormState,
    board_state: BoardState | None,
    selection_state: SelectionState | None,
) -> ReserveRequest | None:
    solution = resolve_reservable_solution(board_state, selection_state)
    if board_state is None or solution is None:
        return None

    return ReserveRequest(
        profile_name=profile_name,
        venue_site_id=booking_state.venue_site_id,
        date=board_state.date,
        solution=solution,
    )


def resolve_effective_buddy_ids(
    settings_state: SettingsFormState | None,
    board_state: BoardState | None,
) -> list[str]:
    if settings_state is None or board_state is None:
        return []

    supports_buddy = supports_buddy_selection(
        buddy_num_min=board_state.buddy_num_min,
        buddy_num_max=board_state.buddy_num_max,
        available_buddy_count=len(board_state.available_buddies),
    )
    if not supports_buddy:
        return []

    configured = split_buddy_ids(settings_state.buddy_ids)
    if not configured:
        return []

    return clamp_buddy_ids(configured, buddy_num_max=board_state.buddy_num_max)


def _format_solution_detail(solution: SlotSolution) -> str:
    return " / ".join(
        f"{choice.space_name} {choice.start_time}-{choice.end_time}"
        for choice in solution.choices
    )


def build_target_summary(
    booking_state: BookingFormState | None,
    settings_state: SettingsFormState | None,
    board_state: BoardState | None,
    selection_state: SelectionState | None,
) -> str:
    if booking_state is None or board_state is None:
        return "未选择目标"

    solution = resolve_active_solution(board_state, selection_state)
    if solution is None:
        return "无满足要求的场地"

    headline = f"场地ID-{board_state.venue_site_id or booking_state.venue_site_id}"
    selected_buddies = resolve_effective_buddy_ids(settings_state, board_state)
    supports_buddy = supports_buddy_selection(
        buddy_num_min=board_state.buddy_num_min,
        buddy_num_max=board_state.buddy_num_max,
        available_buddy_count=len(board_state.available_buddies),
    )
    if supports_buddy:
        buddy_text = ",".join(selected_buddies) if selected_buddies else "未选择"
        headline = f"{headline} buddy ID {buddy_text}"

    location_parts = [
        part
        for part in (board_state.campus_name, board_state.venue_name, board_state.site_name)
        if part
    ]
    detail = " ".join(location_parts + [_format_solution_detail(solution)])
    return f"{detail} ({headline})" if detail else headline


def build_panel_selection_summary(
    board_state: BoardState | None,
    selection_state: SelectionState | None,
) -> str:
    if board_state is None:
        return "点击单元格选择场地"
    if selection_state is None or not selection_state.choices:
        if board_state.recommended_solution is not None:
            recommended = _format_solution_detail(board_state.recommended_solution)
            return f"推荐方案: {recommended}（点击单元格可改选）"
        return "当前条件下无可选方案"

    selected = " / ".join(
        f"{choice.space_name} {choice.start_time}-{choice.end_time}"
        for choice in selection_state.choices
    )
    if len(selection_state.choices) >= board_state.slot_count:
        return selected
    return f"已选 {len(selection_state.choices)}/{board_state.slot_count}: {selected}"
