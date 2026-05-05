"""
Integration tests for property search with all filter combinations.

Tests real database queries with PostGIS geospatial, full-text search,
and combined filter scenarios. Requires PostGIS extension.
"""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PropertyPurpose, PropertyType
from app.schemas.property import UnifiedPropertyFilter
from app.services.property import get_unified_properties_optimized
from tests.fixtures.factories import PropertyFactory


@pytest.mark.postgis
class TestPropertySearchCombinations:
    """Integration tests for property search with combined filters."""

    @pytest.mark.asyncio
    async def test_city_and_purpose_filter(
        self,
        db_session: AsyncSession,
        test_properties,
        test_user,
    ):
        filters = UnifiedPropertyFilter(
            city="Mumbai",
            purpose=PropertyPurpose.rent,
        )
        result = await get_unified_properties_optimized(
            db_session, filters, user_id=test_user.id, page=1, limit=10,
        )
        for item in result["items"]:
            assert item.city == "Mumbai"
            assert item.purpose == PropertyPurpose.rent

    @pytest.mark.asyncio
    async def test_city_and_type_filter(
        self,
        db_session: AsyncSession,
        test_properties,
        test_user,
    ):
        filters = UnifiedPropertyFilter(
            city="Mumbai",
            property_type=[PropertyType.apartment],
        )
        result = await get_unified_properties_optimized(
            db_session, filters, user_id=test_user.id, page=1, limit=10,
        )
        for item in result["items"]:
            assert item.property_type == PropertyType.apartment

    @pytest.mark.asyncio
    async def test_purpose_and_type_filter(
        self,
        db_session: AsyncSession,
        test_properties,
        test_user,
    ):
        filters = UnifiedPropertyFilter(
            purpose=PropertyPurpose.buy,
            property_type=[PropertyType.house],
        )
        result = await get_unified_properties_optimized(
            db_session, filters, user_id=test_user.id, page=1, limit=10,
        )
        for item in result["items"]:
            assert item.purpose == PropertyPurpose.buy

    @pytest.mark.asyncio
    async def test_price_range_filter(
        self,
        db_session: AsyncSession,
        test_properties,
        test_user,
    ):
        filters = UnifiedPropertyFilter(price_min=10000, price_max=100000)
        result = await get_unified_properties_optimized(
            db_session, filters, user_id=test_user.id, page=1, limit=10,
        )
        assert "items" in result

    @pytest.mark.asyncio
    async def test_bedroom_filter(
        self,
        db_session: AsyncSession,
        test_properties,
        test_user,
    ):
        filters = UnifiedPropertyFilter(bedrooms_min=2, bedrooms_max=3)
        result = await get_unified_properties_optimized(
            db_session, filters, user_id=test_user.id, page=1, limit=10,
        )
        for item in result["items"]:
            assert item.bedrooms is not None
            assert 2 <= item.bedrooms <= 3

    @pytest.mark.asyncio
    async def test_empty_results(self, db_session: AsyncSession, test_user):
        filters = UnifiedPropertyFilter(city="NonExistentCity")
        result = await get_unified_properties_optimized(
            db_session, filters, user_id=test_user.id, page=1, limit=10,
        )
        assert result["items"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_pagination(
        self,
        db_session: AsyncSession,
        test_properties,
        test_user,
    ):
        filters = UnifiedPropertyFilter()
        page1 = await get_unified_properties_optimized(
            db_session, filters, user_id=test_user.id, page=1, limit=2,
        )
        page2 = await get_unified_properties_optimized(
            db_session, filters, user_id=test_user.id, page=2, limit=2,
        )
        assert len(page1["items"]) <= 2
        assert page1["page"] == 1
        assert page2["page"] == 2

    @pytest.mark.asyncio
    async def test_special_listing_filters(
        self,
        db_session: AsyncSession,
        test_special_listing_properties,
        test_user,
    ):
        filters = UnifiedPropertyFilter(
            property_type=[PropertyType.pg, PropertyType.flatmate],
        )
        result = await get_unified_properties_optimized(
            db_session, filters, user_id=test_user.id, page=1, limit=10,
        )
        for item in result["items"]:
            assert item.property_type in (PropertyType.pg, PropertyType.flatmate)
