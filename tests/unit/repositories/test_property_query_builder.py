"""
Tests for app.repositories.property_query_builder module.

Most condition-building tests require a real database with PostGIS extension
and are marked with @pytest.mark.postgis. FTS compile checks need no DB.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models.enums import PropertyPurpose, PropertyType
from app.models.properties import Property
from app.repositories.property_query_builder import (
    PropertyQueryBuilder,
    property_ts_vector_column,
)
from app.schemas.property import UnifiedPropertyFilter


class TestPropertyQueryBuilderInit:
    """Tests for PropertyQueryBuilder initialization (no DB needed)."""

    def test_stores_filters(self):
        filters = UnifiedPropertyFilter(city="Mumbai")
        builder = PropertyQueryBuilder(filters)
        assert builder.filters is filters


class TestPropertyQueryBuilderFtsCompile:
    """FTS must use the named indexed column, never dynamic to_tsvector."""

    def test_property_ts_vector_column_is_named_table_column(self):
        col = property_ts_vector_column()
        assert col.name == "__ts_vector__"
        assert col.table is Property.__table__

    def test_fts_conditions_compile_to_indexed_tsvector(self):
        filters = UnifiedPropertyFilter(search_query="apartment near metro")
        builder = PropertyQueryBuilder(filters)
        conditions: list = []
        search_meta = builder._build_fts_conditions(filters, conditions, hard_filter_text=True)

        assert search_meta["search_vector"] is not None
        assert search_meta["text_rank_expr"] is not None
        assert len(conditions) == 1

        statement = (
            select(Property.id)
            .where(*conditions)
            .order_by(search_meta["text_rank_expr"].desc())
        )
        compiled = str(statement.compile(dialect=postgresql.dialect()))

        assert "properties.__ts_vector__ @@ plainto_tsquery" in compiled
        assert "ts_rank(properties.__ts_vector__, plainto_tsquery" in compiled
        assert "to_tsvector(" not in compiled

    def test_hard_filter_text_false_skips_where_but_keeps_rank(self):
        filters = UnifiedPropertyFilter(search_query="villa")
        builder = PropertyQueryBuilder(filters)
        conditions: list = []
        search_meta = builder._build_fts_conditions(filters, conditions, hard_filter_text=False)

        assert conditions == []
        assert search_meta["search_query_obj"] is not None
        assert search_meta["text_rank_expr"] is not None

    @pytest.mark.asyncio
    async def test_features_and_listing_prefs_use_json_not_missing_columns(self):
        """Regression: features/gender/sharing live in JSON fields, not Property columns."""
        from unittest.mock import AsyncMock

        from app.models.enums import ListingGenderPreference, ListingSharingType

        filters = UnifiedPropertyFilter(
            features=["wifi", "parking"],
            gender_preference=ListingGenderPreference.female,
            sharing_type=ListingSharingType.private_room,
        )
        builder = PropertyQueryBuilder(filters)
        conditions, _, _ = await builder.build(AsyncMock())

        statement = select(Property.id).where(*conditions)
        compiled = str(statement.compile(dialect=postgresql.dialect()))

        assert "listing_preferences" in compiled
        assert "CAST(properties.listing_preferences AS JSONB)" in compiled
        assert "properties.features" in compiled
        assert "@>" in compiled
        # Must not reference non-existent scalar columns
        assert "properties.gender_preference" not in compiled
        assert "properties.sharing_type" not in compiled


@pytest.mark.postgis
class TestPropertyQueryBuilderConditions:
    """Tests for filter condition building (requires PostGIS)."""

    @pytest.mark.asyncio
    async def test_city_filter(self, db_session):
        filters = UnifiedPropertyFilter(city="Mumbai")
        builder = PropertyQueryBuilder(filters)
        conditions, _, _ = await builder.build(db_session)
        assert len(conditions) >= 1

    @pytest.mark.asyncio
    async def test_purpose_filter(self, db_session):
        filters = UnifiedPropertyFilter(purpose=PropertyPurpose.rent)
        builder = PropertyQueryBuilder(filters)
        conditions, _, _ = await builder.build(db_session)
        assert len(conditions) >= 1

    @pytest.mark.asyncio
    async def test_property_type_filter(self, db_session):
        filters = UnifiedPropertyFilter(property_type=[PropertyType.apartment])
        builder = PropertyQueryBuilder(filters)
        conditions, _, _ = await builder.build(db_session)
        assert len(conditions) >= 1

    @pytest.mark.asyncio
    async def test_empty_filters(self, db_session):
        filters = UnifiedPropertyFilter()
        builder = PropertyQueryBuilder(filters)
        conditions, _, _ = await builder.build(db_session)
        # Should at least have availability filter
        assert len(conditions) >= 1

    @pytest.mark.asyncio
    async def test_include_unavailable(self, db_session):
        filters = UnifiedPropertyFilter()
        builder = PropertyQueryBuilder(filters)
        conditions_with, _, _ = await builder.build(db_session, include_unavailable=True)
        conditions_without, _, _ = await builder.build(db_session, include_unavailable=False)
        # include_unavailable=True should have fewer conditions
        assert len(conditions_with) <= len(conditions_without)

    @pytest.mark.asyncio
    async def test_property_ids_filter(self, db_session):
        filters = UnifiedPropertyFilter(property_ids=[1, 2, 3])
        builder = PropertyQueryBuilder(filters)
        conditions, _, _ = await builder.build(db_session)
        assert len(conditions) >= 1

    @pytest.mark.asyncio
    async def test_combined_filters(self, db_session):
        filters = UnifiedPropertyFilter(
            city="Mumbai",
            purpose=PropertyPurpose.rent,
            property_type=[PropertyType.apartment],
        )
        builder = PropertyQueryBuilder(filters)
        conditions, _, _ = await builder.build(db_session)
        # Should have availability + city + purpose + type = at least 4
        assert len(conditions) >= 4

    @pytest.mark.asyncio
    async def test_price_range_filters(self, db_session):
        filters = UnifiedPropertyFilter(price_min=10000, price_max=100000)
        builder = PropertyQueryBuilder(filters)
        conditions, _, _ = await builder.build(db_session)
        assert len(conditions) >= 2

    @pytest.mark.asyncio
    async def test_search_meta_returned(self, db_session):
        filters = UnifiedPropertyFilter()
        builder = PropertyQueryBuilder(filters)
        _, _, search_meta = await builder.build(db_session)
        assert isinstance(search_meta, dict)
        assert "search_query_obj" in search_meta
        assert "search_vector" in search_meta
        assert "text_rank_expr" in search_meta
