"""
Tests for app.schemas.flatmates module — FlatmatesProfileUpdate, SwipeRequest, MessageCreate, QnAAnswers.
"""

import pytest
from pydantic import ValidationError

from app.models.enums import FlatmatesMode, MessageType, SwipeAction, SwipeTargetType
from app.schemas.flatmates import (
    FlatmatesProfileUpdate,
    MessageCreate,
    QnAAnswers,
    SwipeRequest,
)


class TestFlatmatesProfileUpdate:
    """Tests for FlatmatesProfileUpdate schema validation."""

    def test_valid_update(self):
        data = FlatmatesProfileUpdate(
            bio="Looking for a flatmate",
            city="Mumbai",
            budget_min=10000,
            budget_max=25000,
        )
        assert data.bio == "Looking for a flatmate"

    def test_budget_range_valid(self):
        data = FlatmatesProfileUpdate(budget_min=10000, budget_max=25000)
        assert data.budget_min == 10000

    def test_budget_range_inverted_rejected(self):
        with pytest.raises(ValidationError, match="budget_max"):
            FlatmatesProfileUpdate(budget_min=30000, budget_max=10000)

    def test_budget_min_negative_rejected(self):
        with pytest.raises(ValidationError):
            FlatmatesProfileUpdate(budget_min=-1000)

    def test_age_below_18_rejected(self):
        with pytest.raises(ValidationError):
            FlatmatesProfileUpdate(age=15)

    def test_age_above_100_rejected(self):
        with pytest.raises(ValidationError):
            FlatmatesProfileUpdate(age=150)

    @pytest.mark.parametrize("age", [18, 25, 50, 99, 100])
    def test_valid_ages(self, age):
        data = FlatmatesProfileUpdate(age=age)
        assert data.age == age

    def test_limit_bounds(self):
        from app.schemas.flatmates import DiscoverProfilesQuery

        with pytest.raises(ValidationError):
            DiscoverProfilesQuery(limit=0)
        with pytest.raises(ValidationError):
            DiscoverProfilesQuery(limit=101)


class TestSwipeRequest:
    """Tests for SwipeRequest schema validation."""

    def test_property_swipe_requires_property_id(self):
        data = SwipeRequest(
            target_type=SwipeTargetType.property,
            action=SwipeAction.like,
            property_id=42,
        )
        assert data.property_id == 42

    def test_property_swipe_without_property_id_rejected(self):
        with pytest.raises(ValidationError, match="property_id"):
            SwipeRequest(
                target_type=SwipeTargetType.property,
                action=SwipeAction.like,
            )

    def test_user_swipe_requires_target_user_id(self):
        data = SwipeRequest(
            target_type=SwipeTargetType.user,
            action=SwipeAction.super_like,
            target_user_id=99,
        )
        assert data.target_user_id == 99

    def test_user_swipe_without_target_user_id_rejected(self):
        with pytest.raises(ValidationError, match="target_user_id"):
            SwipeRequest(
                target_type=SwipeTargetType.user,
                action=SwipeAction.like,
            )


class TestMessageCreate:
    """Tests for MessageCreate schema validation."""

    def test_text_message(self):
        data = MessageCreate(body="Hello there!")
        assert data.body == "Hello there!"

    def test_image_message(self):
        data = MessageCreate(attachment_url="https://example.com/img.jpg")
        assert data.attachment_url is not None

    def test_empty_body_and_no_attachment_rejected(self):
        with pytest.raises(ValidationError, match="body or attachment_url"):
            MessageCreate(body="   ")

    def test_default_message_type_is_text(self):
        data = MessageCreate(body="Hi")
        assert data.message_type == MessageType.text


class TestQnAAnswers:
    """Tests for QnAAnswers schema validation."""

    def test_valid_answers(self):
        data = QnAAnswers(answers={"1": "Yes", "2": "No"})
        assert data.answers["1"] == "Yes"

    def test_non_integer_key_rejected(self):
        with pytest.raises(ValidationError, match="integer"):
            QnAAnswers(answers={"abc": "Yes"})

    def test_empty_answers_valid(self):
        data = QnAAnswers()
        assert data.answers == {}
