from datetime import datetime, timezone
from types import SimpleNamespace

from app.models.enums import FlatmatesProfileStatus
from app.services.flatmates.moderation import apply_report_auto_pause


def _reported_user(status=FlatmatesProfileStatus.active, preferences=None):
    return SimpleNamespace(
        flatmates_profile_status=status,
        preferences=preferences if preferences is not None else {"flatmates": {"city": "Gurugram"}},
    )


def test_report_auto_pause_waits_until_threshold():
    user = _reported_user()

    paused = apply_report_auto_pause(user, report_count=2)

    assert paused is False
    assert user.flatmates_profile_status == FlatmatesProfileStatus.active
    assert "auto_paused_reason" not in user.preferences["flatmates"]


def test_report_auto_pause_pauses_profile_and_preserves_preferences():
    user = _reported_user()

    paused = apply_report_auto_pause(
        user,
        report_count=3,
        now=datetime(2026, 5, 7, tzinfo=timezone.utc),
    )

    assert paused is True
    assert user.flatmates_profile_status == FlatmatesProfileStatus.paused
    assert user.preferences["flatmates"]["city"] == "Gurugram"
    assert user.preferences["flatmates"]["auto_paused_reason"] == "repeat_reports"
    assert user.preferences["flatmates"]["auto_paused_report_count"] == 3
    assert user.preferences["flatmates"]["auto_paused_at"] == "2026-05-07T00:00:00+00:00"


def test_report_auto_pause_is_idempotent_for_already_paused_profile():
    user = _reported_user(status=FlatmatesProfileStatus.paused)

    paused = apply_report_auto_pause(user, report_count=5)

    assert paused is False
    assert user.flatmates_profile_status == FlatmatesProfileStatus.paused
