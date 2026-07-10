"""Unit tests for the flatmates compatibility engine."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.flatmates.compatibility import (
    calculate_compatibility,
    calculate_compatibility_score,
    user_has_lifestyle_profile,
)


def _user(**kwargs: object) -> SimpleNamespace:
    defaults = {
        "id": 1,
        "flatmates_sleep_schedule": None,
        "flatmates_cleanliness": None,
        "flatmates_food_habits": None,
        "flatmates_smoking_drinking": None,
        "flatmates_guests_policy": None,
        "flatmates_work_style": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestCompatibilityIncompleteProfiles:
    def test_no_comparable_dimensions_returns_none_percentage(self):
        a = _user(id=1)
        b = _user(id=2)
        result = calculate_compatibility(a, b)  # type: ignore[arg-type]
        assert result["percentage"] is None
        assert result["dimensions"]
        assert all("not enough data" in s for s in result["summary"])
        assert calculate_compatibility_score(a, b) is None  # type: ignore[arg-type]

    def test_partial_profile_renormalizes_over_comparable_dims(self):
        a = _user(
            id=1,
            flatmates_sleep_schedule="early_bird",
            flatmates_cleanliness="tidy",
        )
        b = _user(
            id=2,
            flatmates_sleep_schedule="early_bird",
            flatmates_cleanliness="tidy",
        )
        result = calculate_compatibility(a, b)  # type: ignore[arg-type]
        # Only sleep (0.2) and cleanliness (0.2) comparable — both 100 → 100%
        assert result["percentage"] == 100
        assert result["color"] == "green"
        assert calculate_compatibility_score(a, b) == 100.0  # type: ignore[arg-type]

    def test_missing_on_one_side_excluded_from_score(self):
        a = _user(
            id=1,
            flatmates_sleep_schedule="early_bird",
            flatmates_food_habits="vegetarian",
        )
        b = _user(
            id=2,
            flatmates_sleep_schedule="night_owl",
            # food_habits missing on peer — must not drag score to 0 overall
        )
        result = calculate_compatibility(a, b)  # type: ignore[arg-type]
        # Only sleep comparable: distance 2 on ordered scale → 0
        assert result["percentage"] == 0
        assert result["color"] == "red"

    def test_user_has_lifestyle_profile(self):
        empty = _user(id=1)
        filled = _user(id=2, flatmates_work_style="remote")
        assert user_has_lifestyle_profile(empty) is False  # type: ignore[arg-type]
        assert user_has_lifestyle_profile(filled) is True  # type: ignore[arg-type]
        assert user_has_lifestyle_profile(None) is False
