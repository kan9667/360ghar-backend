"""
Centralized property filter and sort query builder.

Eliminates duplicated filter/sort logic across property search, swipe history,
and other Property-targeted queries. Prefer this builder over reimplementing
filters inline.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import cast, false, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.db_resilience import execute_with_transient_retry
from app.core.logging import get_logger
from app.models.enums import PG_FLATMATE_TYPES
from app.models.properties import Amenity, Property, PropertyAmenity
from app.schemas.property import SortBy, UnifiedPropertyFilter
from app.utils.geo import city_match_names, escape_like_pattern

logger = get_logger(__name__)


def property_ts_vector_column() -> ColumnElement[Any]:
    """Return the trigger-maintained indexed FTS column for property search."""
    return Property.__table__.c["__ts_vector__"]


class PropertyQueryBuilder:
    """Builds SQLAlchemy where-clauses and order-by expressions from a UnifiedPropertyFilter.

    Usage::

        builder = PropertyQueryBuilder(filters)
        conditions, distance_expr, search_meta = await builder.build(db)

        # conditions can be applied to any query that targets Property
        query = query.where(and_(*conditions))
        query = builder.apply_sort(
            query,
            sort_by=filters.sort_by or SortBy.newest,
            distance_expr=distance_expr,
            text_rank_expr=search_meta.get("text_rank_expr"),
        )
    """

    def __init__(self, filters: UnifiedPropertyFilter) -> None:
        self.filters = filters

    async def build(
        self,
        db: AsyncSession,
        *,
        include_unavailable: bool = False,
        hard_filter_text: bool = True,
    ) -> tuple[
        list[Any],  # conditions
        Any | None,  # distance_expr (SQLAlchemy column)
        dict[str, Any],  # search_meta: {search_query_obj, search_vector, text_rank_expr}
    ]:
        """Build and return all filter components.

        Returns (conditions, distance_expr, search_meta).

        conditions: list of SQLAlchemy where-expressions targeting Property columns.
        distance_expr: ST_Distance column (or None).
        search_meta: dict with keys search_query_obj, search_vector, text_rank_expr.
        """
        f = self.filters
        conditions: list[Any] = []

        # --- availability (parity with main property search / swipe history) ---
        if not include_unavailable:
            conditions.append(Property.is_available)
            conditions.append(
                or_(
                    Property.property_type.notin_(PG_FLATMATE_TYPES),
                    func.coalesce(
                        Property.listing_preferences["moderation_status"].as_string(),
                        "live",
                    )
                    == "live",
                )
            )

        # --- location / geo ---
        distance_expr = self._build_geo_conditions(f, conditions)

        # --- full-text search ---
        search_meta = self._build_fts_conditions(
            f, conditions, hard_filter_text=hard_filter_text
        )

        # --- property IDs ---
        if f.property_ids:
            conditions.append(Property.id.in_(f.property_ids))

        # --- property type ---
        if f.property_type:
            if isinstance(f.property_type, list) and len(f.property_type) > 0:
                conditions.append(Property.property_type.in_(f.property_type))
            elif not isinstance(f.property_type, list):
                conditions.append(Property.property_type == f.property_type)

        # --- purpose ---
        if f.purpose:
            conditions.append(Property.purpose == f.purpose)

        # --- price range ---
        if f.price_min is not None:
            conditions.append(Property.base_price >= f.price_min)
        if f.price_max is not None:
            conditions.append(Property.base_price <= f.price_max)

        # --- bedrooms ---
        if f.bedrooms_min is not None:
            conditions.append(Property.bedrooms >= f.bedrooms_min)
        if f.bedrooms_max is not None:
            conditions.append(Property.bedrooms <= f.bedrooms_max)

        # --- bathrooms ---
        if f.bathrooms_min is not None:
            conditions.append(Property.bathrooms >= f.bathrooms_min)
        if f.bathrooms_max is not None:
            conditions.append(Property.bathrooms <= f.bathrooms_max)

        # --- area ---
        if f.area_min is not None:
            conditions.append(Property.area_sqft >= f.area_min)
        if f.area_max is not None:
            conditions.append(Property.area_sqft <= f.area_max)

        # --- city / locality / pincode ---
        # Match canonical city + all aliases (e.g. Gurgaon/Gurugram). LIKE so
        # "New Delhi" still matches "Delhi"; alias sets keep Gurugram out of Delhi.
        if f.city:
            match_names = city_match_names(f.city)
            city_clauses = [
                func.lower(Property.city).like(
                    f"%{escape_like_pattern(name.lower())}%",
                    escape="\\",
                )
                for name in match_names
            ]
            if len(city_clauses) == 1:
                conditions.append(city_clauses[0])
            elif city_clauses:
                conditions.append(or_(*city_clauses))
        if f.locality:
            conditions.append(
                Property.locality.ilike(
                    f"%{escape_like_pattern(f.locality)}%",
                    escape="\\",
                )
            )
        if f.pincode:
            conditions.append(Property.pincode == f.pincode)

        # --- parking / floor / age ---
        if f.parking_spaces_min is not None:
            conditions.append(Property.parking_spaces >= f.parking_spaces_min)
        if f.floor_number_min is not None:
            conditions.append(Property.floor_number >= f.floor_number_min)
        if f.floor_number_max is not None:
            conditions.append(Property.floor_number <= f.floor_number_max)
        if f.age_max is not None:
            conditions.append(Property.age_of_property <= f.age_max)

        # --- amenities ---
        await self._build_amenity_condition(f, db, conditions)

        # --- listing preferences (PG / flatmate) — stored in JSON, not columns ---
        listing_preferences_json = cast(Property.listing_preferences, JSONB)
        if f.gender_preference is not None:
            conditions.append(
                listing_preferences_json["gender_preference"].astext
                == f.gender_preference.value
            )
        if f.sharing_type is not None:
            conditions.append(
                listing_preferences_json["sharing_type"].astext == f.sharing_type.value
            )

        # --- features (object or string-array JSON shapes) ---
        if f.features:
            for feature in f.features:
                conditions.append(
                    or_(
                        Property.features.op("@>")(cast(json.dumps({feature: True}), JSONB)),
                        Property.features.op("@>")(cast(json.dumps([feature]), JSONB)),
                    )
                )

        # --- guests / max_occupancy ---
        if f.guests is not None:
            conditions.append(Property.max_occupancy >= f.guests)

        return conditions, distance_expr, search_meta

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_geo_conditions(
        self,
        f: UnifiedPropertyFilter,
        conditions: list[Any],
    ) -> Any | None:
        """Add geo filter conditions. Returns distance expression or None."""
        if f.latitude is None or f.longitude is None or not f.radius_km:
            return None

        user_location = func.ST_SetSRID(
            func.ST_MakePoint(f.longitude, f.latitude), 4326
        )
        radius_m = f.radius_km * 1000
        conditions.append(func.ST_DWithin(Property.location, user_location, radius_m))

        distance_expr = func.ST_Distance(Property.location, user_location) / 1000
        return distance_expr

    def _build_fts_conditions(
        self,
        f: UnifiedPropertyFilter,
        conditions: list[Any],
        *,
        hard_filter_text: bool = True,
    ) -> dict[str, Any]:
        """Build full-text search expressions using the indexed __ts_vector__ column."""
        search_meta: dict[str, Any] = {
            "search_query_obj": None,
            "search_vector": None,
            "text_rank_expr": None,
        }

        if not f.search_query:
            return search_meta

        search_query_obj = func.plainto_tsquery("english", f.search_query)
        search_vector = property_ts_vector_column()

        if hard_filter_text:
            conditions.append(search_vector.op("@@")(search_query_obj))

        search_meta["search_query_obj"] = search_query_obj
        search_meta["search_vector"] = search_vector
        search_meta["text_rank_expr"] = func.ts_rank(search_vector, search_query_obj)
        return search_meta

    async def _build_amenity_condition(
        self,
        f: UnifiedPropertyFilter,
        db: AsyncSession,
        conditions: list[Any],
    ) -> None:
        """Add amenity subquery filter if amenities specified."""
        if not f.amenities:
            return

        amenity_ids: list[int] = []
        amenity_names: list[str] = []

        for amenity in f.amenities:
            if isinstance(amenity, int) or (isinstance(amenity, str) and amenity.isdigit()):
                amenity_ids.append(int(amenity))
            else:
                amenity_names.append(amenity)

        if amenity_names:
            # Case-insensitive name match (parity with property search).
            amenity_stmt = select(Amenity.id).where(
                func.lower(Amenity.title).in_([n.lower() for n in amenity_names])
            )
            result = await execute_with_transient_retry(
                db,
                lambda: db.execute(amenity_stmt),
                operation_name="property_query_builder_amenities",
            )
            amenity_ids.extend(row[0] for row in result.fetchall())

        if amenity_ids:
            subquery = (
                select(PropertyAmenity.property_id)
                .where(PropertyAmenity.amenity_id.in_(amenity_ids))
                .group_by(PropertyAmenity.property_id)
                .having(func.count(PropertyAmenity.amenity_id) >= len(amenity_ids))
            )
            conditions.append(Property.id.in_(subquery))
        elif amenity_names:
            # Unresolvable amenity names should match nothing, not drop the filter.
            conditions.append(false())

    def apply_sort(
        self,
        query: Any,
        sort_by: SortBy | None,
        distance_expr: Any = None,
        text_rank_expr: Any = None,
        combined_relevance_expr: Any = None,
        *,
        newest_column: Any = None,
    ) -> Any:
        """Apply sorting to a query. Returns the modified query.

        ``newest_column`` overrides the default Property.created_at for newest
        sort (e.g. UserSwipe.created_at for swipe history).
        """
        if sort_by is None:
            sort_by = SortBy.newest

        newest_expr = newest_column if newest_column is not None else Property.created_at

        if sort_by == SortBy.distance:
            if distance_expr is not None:
                return query.order_by(distance_expr)
            # No geo context: fall back to newest without warning noise.
            return query.order_by(newest_expr.desc())
        if sort_by == SortBy.price_low:
            return query.order_by(Property.base_price.asc())
        if sort_by == SortBy.price_high:
            return query.order_by(Property.base_price.desc())
        if sort_by == SortBy.newest:
            return query.order_by(newest_expr.desc())
        if sort_by == SortBy.popular:
            return query.order_by(Property.like_count.desc(), Property.view_count.desc())
        if sort_by == SortBy.relevance:
            if combined_relevance_expr is not None:
                return query.order_by(combined_relevance_expr.desc())
            if text_rank_expr is not None:
                return query.order_by(text_rank_expr.desc())
            return query.order_by(newest_expr.desc())

        logger.warning("Unsupported sort option: %s, defaulting to newest", sort_by)
        return query.order_by(newest_expr.desc())
