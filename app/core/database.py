import time
from collections.abc import AsyncGenerator

import sentry_sdk
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Base class for all models
class Base(DeclarativeBase):
    pass

# Log database connection info
logger.info("Connecting to database with psycopg for PgBouncer compatibility")

# Shared connection args for PgBouncer compatibility
_connect_args = {
    "application_name": "360ghar_backend",
    "prepare_threshold": None,  # Disable prepared statements for PgBouncer
}

_bg_connect_args = {
    "application_name": "360ghar_bg",
    "prepare_threshold": None,
}

# ── Main engine: HTTP/MCP request traffic ─────────────────────────────────────
# PgBouncer (Supabase) handles server-side pooling — keep the app-side
# pool small to avoid exhausting PgBouncer's transaction-mode slots.
engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

# ── Background engine: schedulers, scrapers, long-running tasks ───────────────
# Isolated from the main pool so background work can't starve API traffic.
bg_engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_size=settings.DB_BG_POOL_SIZE,
    max_overflow=settings.DB_BG_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,
    connect_args=_bg_connect_args,
)

# ── Slow-checkout logging ──────────────────────────────────────────────────────
_SLOW_CHECKOUT_THRESHOLD_S = 5.0


def _on_checkout(dbapi_conn, connection_record, connection_proxy):
    connection_record.info["_checkout_start"] = time.monotonic()


def _on_checkin(dbapi_conn, connection_record):
    start = connection_record.info.pop("_checkout_start", None)
    if start is not None:
        elapsed = time.monotonic() - start
        if elapsed > _SLOW_CHECKOUT_THRESHOLD_S:
            logger.warning(
                "Slow pool checkout: %.1fs (pool: %s)",
                elapsed,
                connection_record.info.get("pool_label", "unknown"),
            )


for _eng in (engine, bg_engine):
    event.listen(_eng.sync_engine, "checkout", _on_checkout)
    event.listen(_eng.sync_engine, "checkin", _on_checkin)

# ── Session factories ──────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

AsyncSessionLocalBG = async_sessionmaker(
    bg_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── FastAPI dependencies ───────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except HTTPException:
            # Propagate HTTP errors without logging as DB errors
            await session.rollback()
            raise
        except Exception as e:
            logger.error("Database session error: %s", e)
            sentry_sdk.set_context("database", {
                "error_type": type(e).__name__,
                "error_message": str(e),
            })
            await session.rollback()
            raise
        else:
            # Commit only if no exception occurred during the request
            await session.commit()


async def get_bg_db() -> AsyncGenerator[AsyncSession, None]:
    """Background task dependency — uses the isolated background pool."""
    async with AsyncSessionLocalBG() as session:
        try:
            yield session
        except HTTPException:
            await session.rollback()
            raise
        except Exception as e:
            logger.error("Background database session error: %s", e)
            sentry_sdk.set_context("database", {
                "error_type": type(e).__name__,
                "error_message": str(e),
            })
            await session.rollback()
            raise
        else:
            await session.commit()


def get_async_session_factory():
    """
    Get the async session factory for use in background tasks.

    This allows background tasks to create their own database sessions
    independent of the FastAPI request lifecycle.

    Returns:
        async_sessionmaker: The session factory
    """
    return AsyncSessionLocal


def get_bg_session_factory():
    """
    Get the background async session factory (isolated pool).

    Use this for schedulers, scrapers, and other long-running background
    tasks that should not compete with HTTP/MCP request traffic.

    Returns:
        async_sessionmaker: The background session factory
    """
    return AsyncSessionLocalBG
