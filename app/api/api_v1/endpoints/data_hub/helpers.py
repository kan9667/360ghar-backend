"""Shared dependencies and helpers for data hub endpoints."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.data_hub import DataHubMeta

_STAMP_DUTY_RATES: dict[str, float] = {"male": 7.0, "female": 5.0, "joint": 6.0}


def _paginate(total: int, page: int, limit: int) -> dict[str, Any]:
    total_pages = max(1, (total + limit - 1) // limit)
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


async def _meta_from_table(db: AsyncSession, model) -> DataHubMeta:
    """Query max updated_at for a table and return a DataHubMeta."""
    result = await db.execute(select(func.max(model.updated_at)))
    last_updated = result.scalar_one_or_none()
    return DataHubMeta(last_updated=last_updated)
