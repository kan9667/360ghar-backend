"""
Tests for app.schemas.visit module — VisitCreate, VisitReschedule, VisitCancel.
"""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.models.enums import VisitContext
from app.schemas.visit import VisitCancel, VisitCreate, VisitReschedule


class TestVisitCreate:
    """Tests for VisitCreate schema validation."""

    def test_valid_visit(self):
        data = VisitCreate(
            property_id=1,
            scheduled_date=datetime.now(timezone.utc) + timedelta(days=3),
        )
        assert data.property_id == 1

    def test_default_visit_context(self):
        data = VisitCreate(
            property_id=1,
            scheduled_date=datetime.now(timezone.utc) + timedelta(days=3),
        )
        assert data.visit_context == VisitContext.property_tour

    def test_flatmate_meet_context(self):
        data = VisitCreate(
            property_id=1,
            scheduled_date=datetime.now(timezone.utc) + timedelta(days=3),
            visit_context=VisitContext.flatmate_meet,
        )
        assert data.visit_context == VisitContext.flatmate_meet

    def test_with_counterparty_user(self):
        data = VisitCreate(
            property_id=1,
            scheduled_date=datetime.now(timezone.utc) + timedelta(days=3),
            counterparty_user_id=42,
        )
        assert data.counterparty_user_id == 42


class TestVisitReschedule:
    """Tests for VisitReschedule schema validation."""

    def test_valid_reschedule(self):
        data = VisitReschedule(
            new_date=datetime.now(timezone.utc) + timedelta(days=7),
            reason="Schedule conflict",
        )
        assert data.reason == "Schedule conflict"

    def test_reschedule_without_reason(self):
        data = VisitReschedule(
            new_date=datetime.now(timezone.utc) + timedelta(days=7),
        )
        assert data.reason is None


class TestVisitCancel:
    """Tests for VisitCancel schema validation."""

    def test_valid_cancel(self):
        data = VisitCancel(reason="Changed my mind")
        assert data.reason == "Changed my mind"

    def test_reason_is_required(self):
        with pytest.raises(ValidationError):
            VisitCancel()
