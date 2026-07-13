"""Tests for Vastu LLM output coercion and parsing."""

from app.services.ai.vastu.analyzer import _parse_analysis_result
from app.services.ai.vastu.schemas import (
    VastuAnalysisResult,
    coerce_string_list,
)


class TestCoerceStringList:
    def test_plain_strings(self):
        assert coerce_string_list(["a", "b"]) == ["a", "b"]

    def test_dict_with_suggestion(self):
        raw = [
            {"suggestion": "Ensure the entrance allows flow of positive energy."},
            {"suggestion": "In the Master bedroom, face East while sleeping."},
            {"suggestion": "Keep heavy items around the Earth energy."},
        ]
        assert coerce_string_list(raw) == [
            "Ensure the entrance allows flow of positive energy.",
            "In the Master bedroom, face East while sleeping.",
            "Keep heavy items around the Earth energy.",
        ]

    def test_mixed_strings_and_dicts(self):
        assert coerce_string_list([
            "plain tip",
            {"text": "from text key"},
            {"improvement": "from improvement key"},
            {"description": "from description"},
            {"other": "fallback value"},
            "",
            None,
            {"empty": ""},
        ]) == [
            "plain tip",
            "from text key",
            "from improvement key",
            "from description",
            "fallback value",
        ]

    def test_none_and_empty(self):
        assert coerce_string_list(None) == []
        assert coerce_string_list([]) == []
        assert coerce_string_list("") == []

    def test_single_string(self):
        assert coerce_string_list("one tip") == ["one tip"]


class TestVastuAnalysisResultCoercion:
    def test_improvements_dict_shape_from_production(self):
        result = VastuAnalysisResult(
            floor_plan_analysis={"rooms": []},
            vastu_score=6,
            score_explanation="ok",
            disclaimer="info only",
            improvements=[
                {"suggestion": "Ensure the entrance allows flow of positive energy."},
                {"suggestion": "In the Master bedroom, face East while sleeping."},
                {"suggestion": "Keep heavy items around the Earth energy."},
            ],
        )
        assert all(isinstance(i, str) for i in result.improvements)
        assert len(result.improvements) == 3

    def test_assumptions_coerced(self):
        result = VastuAnalysisResult(
            floor_plan_analysis={"rooms": []},
            vastu_score=5,
            score_explanation="ok",
            disclaimer="info",
            assumptions=[{"text": "North assumed at top"}],
        )
        assert result.assumptions == ["North assumed at top"]


class TestParseAnalysisResult:
    def test_production_improvements_shape(self):
        payload = {
            "floor_plan_analysis": {
                "rooms": [{"name": "Kitchen", "direction": "SE"}],
            },
            "vastu_score": 7,
            "score_explanation": "Good overall layout with minor improvements needed",
            "improvements": [
                {"suggestion": "Ensure the entrance allows flow of positive energy."},
                {"suggestion": "In the Master bedroom, face East while sleeping."},
                {"suggestion": "Keep heavy items around the Earth energy."},
            ],
            "is_valid_floor_plan": True,
            "analysis_confidence": 0.9,
        }
        result = _parse_analysis_result(payload)
        assert result.vastu_score == 7
        assert result.improvements == [
            "Ensure the entrance allows flow of positive energy.",
            "In the Master bedroom, face East while sleeping.",
            "Keep heavy items around the Earth energy.",
        ]
