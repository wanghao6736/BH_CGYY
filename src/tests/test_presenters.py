from src.presenters.format import format_submit_result
from src.parsers.order import SubmitParsed


def test_format_submit_result_includes_display_name_and_profile() -> None:
    text = format_submit_result(
        True,
        "OK",
        SubmitParsed(
            order_id=1,
            trade_no="D1",
            reservation_start_date="2026-03-21 19:00",
            reservation_end_date="2026-03-21 20:00",
        ),
        display_name="Alice",
        profile_name="alice",
    )

    assert "预定人 Alice | profile alice" in text
