from app.services.flatmates.profiles import _move_in_profile_values


def test_move_in_profile_values_normalize_catalog_aliases():
    assert _move_in_profile_values("immediate") == {
        "immediate",
        "immediately",
        "now",
    }
    assert _move_in_profile_values("within_1_month") == {
        "this_month",
        "within_1_month",
        "within_a_month",
    }


def test_move_in_profile_values_ignore_flexible_and_unknown_values():
    assert _move_in_profile_values("flexible") == set()
    assert _move_in_profile_values("unknown") == set()
