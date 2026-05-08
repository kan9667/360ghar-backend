"""Shared dependencies and helpers for data hub endpoints."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.schemas.data_hub import DataHubMeta

logger = get_logger(__name__)

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
    try:
        result = await db.execute(select(func.max(model.updated_at)))
        last_updated = result.scalar_one_or_none()
        return DataHubMeta(last_updated=last_updated)
    except (ProgrammingError, OperationalError) as exc:
        logger.error("Data-hub meta query failed for %s: %s", model.__name__, exc)
        return DataHubMeta()


async def _safe_list_query(db: AsyncSession, model, count_q, data_q, offset: int, limit: int, page: int):
    """Execute count + data queries, returning empty results on DB errors."""
    try:
        total = (await db.execute(count_q)).scalar_one()
        rows = (await db.execute(data_q.offset(offset).limit(limit))).scalars().all()
        meta = await _meta_from_table(db, model)
    except (ProgrammingError, OperationalError) as exc:
        logger.error("Data-hub table query failed for %s (tables may not exist yet): %s", model.__name__, exc)
        total = 0
        rows = []
        meta = DataHubMeta()
    return rows, total, meta
