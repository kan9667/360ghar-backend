"""Unit tests for city alias helpers used by property search filters."""

from __future__ import annotations

from app.utils.geo import city_match_names, escape_like_pattern, normalize_city


class TestNormalizeCity:
    def test_gurgaon_canonical(self) -> None:
        assert normalize_city("Gurgaon") == "Gurugram"
        assert normalize_city("gurgaon") == "Gurugram"
        assert normalize_city("Gurugram") == "Gurugram"

    def test_unknown_title_cases(self) -> None:
        assert normalize_city("mysore") == "Mysore"


class TestCityMatchNames:
    def test_gurgaon_includes_both_spellings(self) -> None:
        names = {n.lower() for n in city_match_names("Gurgaon")}
        assert "gurugram" in names
        assert "gurgaon" in names

    def test_gurugram_includes_gurgaon_alias(self) -> None:
        names = {n.lower() for n in city_match_names("Gurugram")}
        assert "gurugram" in names
        assert "gurgaon" in names

    def test_delhi_does_not_include_gurugram(self) -> None:
        names = {n.lower() for n in city_match_names("Delhi")}
        assert "delhi" in names
        assert "new delhi" in names
        assert "gurugram" not in names
        assert "gurgaon" not in names
        # Ultra-short alias "ncr" is intentionally omitted as a LIKE token
        assert "ncr" not in names

    def test_bangalore_includes_bengaluru(self) -> None:
        names = {n.lower() for n in city_match_names("bangalore")}
        assert "bengaluru" in names
        assert "bangalore" in names

    def test_empty_and_whitespace(self) -> None:
        assert city_match_names("") == []
        assert city_match_names("   ") == []

    def test_canonical_is_first(self) -> None:
        names = city_match_names("Gurgaon")
        assert names[0] == "Gurugram"


class TestEscapeLikePattern:
    def test_escapes_wildcards(self) -> None:
        assert escape_like_pattern("100%_fun") == r"100\%\_fun"
