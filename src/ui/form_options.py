from __future__ import annotations

from PySide6.QtCore import QDate

ANY_TIME_OPTION = "-"


def build_date_options(*, today: QDate | None = None, days: int = 7) -> list[str]:
    current_day = today or QDate.currentDate()
    options: list[str] = []
    for offset in range(days):
        candidate = current_day.addDays(offset)
        if offset == 0:
            options.append("今天")
        elif offset == 1:
            options.append("明天")
        else:
            options.append(candidate.toString("MM-dd"))
    return options


def build_time_options(
    *,
    start_hour: int = 8,
    end_hour: int = 22,
    include_any: bool = False,
) -> list[str]:
    options: list[str] = [ANY_TIME_OPTION] if include_any else []
    hour = start_hour
    while hour < end_hour:
        options.append(f"{hour:02d}:00")
        options.append(f"{hour:02d}:30")
        hour += 1
    return options


def with_any_time_option(options: list[str]) -> list[str]:
    return [ANY_TIME_OPTION, *[item for item in options if item != ANY_TIME_OPTION]]


def normalize_time_option(value: str) -> str:
    return "" if value == ANY_TIME_OPTION else value


def resolve_request_date(date_text: str, today: QDate | None = None) -> str:
    current_day = today or QDate.currentDate()
    if not date_text:
        return current_day.toString("yyyy-MM-dd")
    exact_date = QDate.fromString(date_text, "yyyy-MM-dd")
    if exact_date.isValid():
        return exact_date.toString("yyyy-MM-dd")

    if date_text in ("今天", "明天"):
        offset = 0 if date_text == "今天" else 1
        return current_day.addDays(offset).toString("yyyy-MM-dd")

    month, day = map(int, date_text.split("-"))
    candidate = QDate(current_day.year(), month, day)
    if candidate.isValid() and candidate < current_day:
        candidate = candidate.addYears(1)
    return candidate.toString("yyyy-MM-dd") if candidate.isValid() else current_day.toString("yyyy-MM-dd")


def apply_date_to_combo(combo, value: str, *, today: QDate | None = None, default_index: int = 0) -> None:
    exact_index = combo.findText(value)
    if exact_index >= 0:
        combo.setCurrentIndex(exact_index)
        return

    if combo.count() > 0 and QDate.fromString(combo.itemText(0), "yyyy-MM-dd").isValid():
        combo.setCurrentIndex(default_index if 0 <= default_index < combo.count() else 0)
        return

    parsed = QDate.fromString(value, "yyyy-MM-dd")
    if not parsed.isValid():
        combo.setCurrentIndex(default_index)
        return

    current_day = today or QDate.currentDate()
    days_diff = current_day.daysTo(parsed)
    if days_diff == 0:
        combo.setCurrentIndex(0)
    elif days_diff == 1:
        combo.setCurrentIndex(1)
    elif 0 <= days_diff < 7:
        combo.setCurrentIndex(days_diff)
    else:
        combo.setCurrentIndex(default_index)


def apply_time_to_combo(combo, value: str, *, default_text: str = "18:00") -> None:
    if not value:
        any_index = combo.findText(ANY_TIME_OPTION)
        if any_index >= 0:
            combo.setCurrentIndex(any_index)
            return

    target = value or default_text
    index = combo.findText(target)
    if index >= 0:
        combo.setCurrentIndex(index)
        return

    default_index = combo.findText(default_text)
    combo.setCurrentIndex(default_index if default_index >= 0 else 0)
