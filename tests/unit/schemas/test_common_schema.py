"""
Tests for app.schemas.common module — PaginationParams, make_paginated, NotificationSettings.
"""

import pytest
from pydantic import ValidationError

from app.schemas.common import (
    NotificationSettings,
    PaginationParams,
    PrivacySettings,
    make_paginated,
)


class TestPaginationParams:
    """Tests for PaginationParams schema."""

    def test_defaults(self):
        p = PaginationParams()
        assert p.page == 1
        assert p.limit == 20

    def test_get_offset(self):
        p = PaginationParams(page=3, limit=10)
        assert p.get_offset() == 20

    def test_get_offset_first_page(self):
        p = PaginationParams(page=1, limit=20)
        assert p.get_offset() == 0

    @pytest.mark.parametrize("page,limit,expected_offset", [
        (1, 10, 0),
        (2, 10, 10),
        (5, 20, 80),
        (1, 1, 0),
    ])
    def test_offset_calculations(self, page, limit, expected_offset):
        p = PaginationParams(page=page, limit=limit)
        assert p.get_offset() == expected_offset


class TestMakePaginated:
    """Tests for make_paginated helper function."""

    def test_basic_pagination(self):
        result = make_paginated(items=[1, 2, 3], total=10, page=1, limit=3)
        assert result["items"] == [1, 2, 3]
        assert result["total"] == 10
        assert result["page"] == 1
        assert result["limit"] == 3
        assert result["total_pages"] == 4
        assert result["has_next"] is True
        assert result["has_prev"] is False

    def test_last_page(self):
        result = make_paginated(items=[10], total=10, page=4, limit=3)
        assert result["has_next"] is False
        assert result["has_prev"] is True

    def test_single_page(self):
        result = make_paginated(items=[1, 2], total=2, page=1, limit=10)
        assert result["total_pages"] == 1
        assert result["has_next"] is False
        assert result["has_prev"] is False

    def test_empty_items(self):
        result = make_paginated(items=[], total=0, page=1, limit=10)
        assert result["total_pages"] == 0
        assert result["has_next"] is False

    def test_exact_page_boundary(self):
        result = make_paginated(items=list(range(10)), total=10, page=1, limit=10)
        assert result["total_pages"] == 1
        assert result["has_next"] is False


class TestNotificationSettings:
    """Tests for NotificationSettings schema."""

    def test_defaults(self):
        settings = NotificationSettings()
        assert settings.email_notifications is True
        assert settings.push_notifications is True
        assert settings.sms_notifications is False
        assert settings.promotional_emails is False

    def test_custom_values(self):
        settings = NotificationSettings(
            email_notifications=False,
            push_notifications=False,
            sms_notifications=True,
        )
        assert settings.email_notifications is False
        assert settings.sms_notifications is True

    def test_categories_default(self):
        settings = NotificationSettings()
        assert "promotions" in settings.categories
        assert "onboarding" in settings.categories


class TestPrivacySettings:
    """Tests for PrivacySettings schema."""

    def test_defaults(self):
        settings = PrivacySettings()
        assert settings.profile_visibility == "public"
        assert settings.location_sharing is True
        assert settings.contact_sharing is True

    def test_private_profile(self):
        settings = PrivacySettings(profile_visibility="private")
        assert settings.profile_visibility == "private"
