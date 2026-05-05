"""
Tests for app.schemas.booking module — BookingCreate, BookingReview.
"""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas.booking import BookingCreate, BookingReview


class TestBookingCreate:
    """Tests for BookingCreate schema validation."""

    def test_valid_booking(self):
        data = BookingCreate(
            property_id=1,
            check_in_date=datetime.now(timezone.utc) + timedelta(days=7),
            check_out_date=datetime.now(timezone.utc) + timedelta(days=10),
            guests=2,
            primary_guest_name="Test Guest",
            primary_guest_phone="+919876543210",
            primary_guest_email="guest@test.com",
        )
        assert data.guests == 2

    def test_checkout_before_checkin_rejected(self):
        with pytest.raises(ValidationError, match="Check-out date"):
            BookingCreate(
                property_id=1,
                check_in_date=datetime.now(timezone.utc) + timedelta(days=7),
                check_out_date=datetime.now(timezone.utc) + timedelta(days=5),
                guests=2,
                primary_guest_name="Guest",
                primary_guest_phone="+919876543210",
                primary_guest_email="guest@test.com",
            )

    def test_same_day_checkin_checkout_rejected(self):
        same_time = datetime.now(timezone.utc) + timedelta(days=7)
        with pytest.raises(ValidationError, match="Check-out date"):
            BookingCreate(
                property_id=1,
                check_in_date=same_time,
                check_out_date=same_time,
                guests=1,
                primary_guest_name="Guest",
                primary_guest_phone="+919876543210",
                primary_guest_email="guest@test.com",
            )

    def test_invalid_email_rejected(self):
        with pytest.raises(ValidationError):
            BookingCreate(
                property_id=1,
                check_in_date=datetime.now(timezone.utc) + timedelta(days=7),
                check_out_date=datetime.now(timezone.utc) + timedelta(days=10),
                guests=2,
                primary_guest_name="Guest",
                primary_guest_phone="+919876543210",
                primary_guest_email="not-an-email",
            )


class TestBookingReview:
    """Tests for BookingReview schema validation."""

    @pytest.mark.parametrize("rating", [1, 2, 3, 4, 5])
    def test_valid_ratings(self, rating):
        review = BookingReview(booking_id=1, guest_rating=rating)
        assert review.guest_rating == rating

    @pytest.mark.parametrize("rating", [0, -1, 6, 10])
    def test_invalid_ratings_rejected(self, rating):
        with pytest.raises(ValidationError, match="Rating must be between 1 and 5"):
            BookingReview(booking_id=1, guest_rating=rating)

    def test_review_with_text(self):
        review = BookingReview(
            booking_id=1,
            guest_rating=5,
            guest_review="Excellent stay!",
        )
        assert review.guest_review == "Excellent stay!"
