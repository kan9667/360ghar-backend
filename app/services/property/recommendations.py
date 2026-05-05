"""Property recommendation logic."""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db_resilience import execute_with_transient_retry
from app.core.logging import get_logger
from app.models.enums import PG_FLATMATE_TYPES
from app.models.properties import Property
from app.schemas.property import Property as PropertySchema

logger = get_logger(__name__)


async def get_property_recommendations(db: AsyncSession, user_id: int | None, limit: int = 10):
    """Get property recommendations for a user"""
    logger.info("Getting property recommendations for user %s, limit: %s", user_id, limit)

    try:
        # Simple recommendation: get available properties
        # TODO: Implement proper recommendation algorithm based on user preferences
        query = (
            select(Property)
            .options(selectinload(Property.images))
            .where(
                Property.is_available,
                or_(
                    Property.property_type.notin_(PG_FLATMATE_TYPES),
                    func.coalesce(
                        Property.listing_preferences["moderation_status"].as_string(),
                        "live",
                    )
                    == "live",
                ),
            )
            .limit(limit)
        )

        result = await execute_with_transient_retry(
            db,
            lambda: db.execute(query),
            operation_name="property_recommendations_query",
        )
        properties = result.scalars().all()

        logger.info("Found %s recommended properties for user %s", len(properties), user_id)

        return [PropertySchema.model_validate(prop) for prop in properties]
    except Exception as e:
        logger.error("Failed to get recommendations for user %s: %s", user_id, e, exc_info=True)
        raise
