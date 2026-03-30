from __future__ import annotations

from src.parsers.slot_filter import SlotChoice, SlotSolution
from src.ui.state import (BoardCell, BoardRow, BoardState, BoardStatus,
                          BookingFormState, BuddyOption, SelectionState,
                          SettingsFormState)
from src.ui.ui_mappers import (build_board_query, build_reserve_request,
                               build_selection_state,
                               resolve_active_solution,
                               resolve_effective_buddy_ids,
                               resolve_enabled_choice_keys)


def _choice(space_id: int, time_id: int, space_name: str, start: str, end: str, fee: float = 25.0) -> SlotChoice:
    return SlotChoice(
        space_id=space_id,
        time_id=time_id,
        space_name=space_name,
        start_time=start,
        end_time=end,
        order_fee=fee,
    )


def _solution(*choices: SlotChoice) -> SlotSolution:
    return SlotSolution(
        choices=list(choices),
        total_fee=sum(item.order_fee for item in choices),
        slot_count=len(choices),
        total_hours=0.5 * len(choices),
    )


def _build_board_state(*, slot_count: int = 2) -> BoardState:
    return BoardState(
        status=BoardStatus.READY,
        profile_name="default",
        venue_site_id=57,
        venue_label="Test Venue",
        date="2026-03-27",
        slot_count=slot_count,
        rows=[
            BoardRow(
                space_id=101,
                space_name="A1",
                cells=[
                    BoardCell(
                        space_id=101,
                        space_name="A1",
                        time_id=1,
                        begin_time="18:00",
                        end_time="18:30",
                        label="18:00",
                        reservation_status=1,
                        selectable=True,
                        fee=25.0,
                    ),
                    BoardCell(
                        space_id=101,
                        space_name="A1",
                        time_id=2,
                        begin_time="18:30",
                        end_time="19:00",
                        label="18:30",
                        reservation_status=1,
                        selectable=False,
                        fee=25.0,
                    ),
                ],
            ),
            BoardRow(
                space_id=201,
                space_name="B1",
                cells=[
                    BoardCell(
                        space_id=201,
                        space_name="B1",
                        time_id=1,
                        begin_time="18:00",
                        end_time="18:30",
                        label="18:00",
                        reservation_status=1,
                        selectable=False,
                        fee=30.0,
                    ),
                    BoardCell(
                        space_id=201,
                        space_name="B1",
                        time_id=2,
                        begin_time="18:30",
                        end_time="19:00",
                        label="18:30",
                        reservation_status=1,
                        selectable=True,
                        fee=30.0,
                    ),
                ],
            ),
            BoardRow(
                space_id=202,
                space_name="C1",
                cells=[
                    BoardCell(
                        space_id=202,
                        space_name="C1",
                        time_id=1,
                        begin_time="18:00",
                        end_time="18:30",
                        label="18:00",
                        reservation_status=1,
                        selectable=False,
                        fee=35.0,
                    ),
                    BoardCell(
                        space_id=202,
                        space_name="C1",
                        time_id=2,
                        begin_time="18:30",
                        end_time="19:00",
                        label="18:30",
                        reservation_status=1,
                        selectable=True,
                        fee=35.0,
                    ),
                ],
            ),
        ],
        solutions=[
            _solution(
                _choice(101, 1, "A1", "18:00", "18:30"),
                _choice(201, 2, "B1", "18:30", "19:00"),
            ),
            _solution(
                _choice(101, 1, "A1", "18:00", "18:30"),
                _choice(202, 2, "C1", "18:30", "19:00"),
            ),
        ],
        time_headers=["18:00", "18:30"],
        last_sync_at="10:20:30",
    )


def test_build_board_query_from_booking_form_state() -> None:
    query = build_board_query(
        "default",
        BookingFormState(
            date="2026-03-28",
            start_time="18:30",
            slot_count=3,
            venue_site_id=99,
        ),
    )

    assert query.profile_name == "default"
    assert query.venue_site_id == 99
    assert query.date == "2026-03-28"
    assert query.start_time == "18:30"
    assert query.slot_count == 3


def test_build_selection_state_supports_stepwise_solution_selection() -> None:
    board_state = _build_board_state(slot_count=2)

    first = build_selection_state(board_state, row=0, col=0)
    assert first == SelectionState(
        choices=[_choice(101, 1, "A1", "18:00", "18:30")]
    )

    second = build_selection_state(board_state, row=1, col=1, current_selection=first)
    assert second == SelectionState(
        choices=[
            _choice(101, 1, "A1", "18:00", "18:30"),
            _choice(201, 2, "B1", "18:30", "19:00", fee=30.0),
        ]
    )


def test_resolve_enabled_choice_keys_advances_with_prefix() -> None:
    board_state = _build_board_state(slot_count=2)

    initial_keys = resolve_enabled_choice_keys(board_state, None)
    assert initial_keys == {(101, 1)}

    next_keys = resolve_enabled_choice_keys(
        board_state,
        SelectionState(choices=[_choice(101, 1, "A1", "18:00", "18:30")]),
    )
    assert next_keys == {(101, 1), (201, 2), (202, 2)}


def test_build_reserve_request_uses_selected_solution_or_recommended_solution() -> None:
    board_state = _build_board_state(slot_count=2)
    manual = SelectionState(
        choices=[
            _choice(101, 1, "A1", "18:00", "18:30"),
            _choice(202, 2, "C1", "18:30", "19:00"),
        ]
    )
    request = build_reserve_request(
        "default",
        BookingFormState(
            date="2026-03-30",
            start_time="18:30",
            slot_count=2,
            venue_site_id=57,
        ),
        board_state,
        manual,
    )

    assert request is not None
    assert request.profile_name == "default"
    assert request.venue_site_id == 57
    assert request.date == "2026-03-27"
    assert request.solution.choices[0].space_id == 101
    assert request.solution.choices[1].space_id == 202

    fallback = build_reserve_request(
        "default",
        BookingFormState(
            date="2026-03-30",
            start_time="18:30",
            slot_count=2,
            venue_site_id=57,
        ),
        board_state,
        None,
    )
    assert fallback is not None
    assert resolve_active_solution(board_state, None) == board_state.solutions[0]
    assert fallback.solution == board_state.solutions[0]


def test_build_reserve_request_returns_none_for_partial_manual_selection() -> None:
    board_state = _build_board_state(slot_count=2)
    partial = SelectionState(
        choices=[_choice(101, 1, "A1", "18:00", "18:30")]
    )

    request = build_reserve_request(
        "default",
        BookingFormState(
            date="2026-03-30",
            start_time="18:30",
            slot_count=2,
            venue_site_id=57,
        ),
        board_state,
        partial,
    )

    assert request is None


def test_build_reserve_request_accepts_optional_display_name_keyword() -> None:
    board_state = _build_board_state(slot_count=2)

    request = build_reserve_request(
        "default",
        BookingFormState(
            date="2026-03-30",
            start_time="18:30",
            slot_count=2,
            venue_site_id=57,
        ),
        board_state,
        None,
        display_name="Alice",
    )

    assert request is not None
    assert request.display_name == "Alice"


def test_resolve_effective_buddy_ids_preserves_selected_ids_within_buddy_max() -> None:
    board_state = _build_board_state()
    board_state.buddy_num_min = 1
    board_state.buddy_num_max = 3
    board_state.available_buddies = [
        BuddyOption(id="1", name="Alice"),
        BuddyOption(id="2", name="Bob"),
        BuddyOption(id="3", name="Carol"),
    ]

    assert resolve_effective_buddy_ids(
        SettingsFormState(profile_name="default", buddy_ids="1,2"),
        board_state,
    ) == ["1", "2"]


def test_resolve_effective_buddy_ids_truncates_selected_ids_to_buddy_max() -> None:
    board_state = _build_board_state()
    board_state.buddy_num_min = 1
    board_state.buddy_num_max = 2
    board_state.available_buddies = [
        BuddyOption(id="1", name="Alice"),
        BuddyOption(id="2", name="Bob"),
        BuddyOption(id="3", name="Carol"),
    ]

    assert resolve_effective_buddy_ids(
        SettingsFormState(profile_name="default", buddy_ids="1,2,3"),
        board_state,
    ) == ["1", "2"]
