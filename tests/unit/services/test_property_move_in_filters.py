from datetime import datetime, timezone

from app.services.property.search import _available_from_minimum, _move_in_window


def test_move_in_immediate_window_includes_today_and_next_seven_days():
    now = datetime(2026, 5, 7, 13, 30, tzinfo=timezone.utc)

    assert _move_in_window("immediate", now=now) == (
        None,
        datetime(2026, 5, 15, tzinfo=timezone.utc),
    )


def test_move_in_this_month_window_ends_at_next_month_start():
    now = datetime(2026, 5, 7, 13, 30, tzinfo=timezone.utc)

    assert _move_in_window("this_month", now=now) == (
        None,
        datetime(2026, 6, 1, tzinfo=timezone.utc),
    )


def test_move_in_next_month_window_uses_calendar_month_boundaries():
    now = datetime(2026, 12, 20, 13, 30, tzinfo=timezone.utc)

    assert _move_in_window("next_month", now=now) == (
        datetime(2027, 1, 1, tzinfo=timezone.utc),
        datetime(2027, 2, 1, tzinfo=timezone.utc),
    )


def test_move_in_flexible_and_unknown_values_do_not_filter():
    now = datetime(2026, 5, 7, 13, 30, tzinfo=timezone.utc)

    assert _move_in_window("flexible", now=now) is None
    assert _move_in_window("unknown_catalog_value", now=now) is None


def test_available_from_minimum_parses_date_at_utc_day_start():
    assert _available_from_minimum("2026-05-07") == datetime(
        2026,
        5,
        7,
        tzinfo=timezone.utc,
    )
