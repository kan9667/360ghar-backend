"""Shared APScheduler singleton for all background cron jobs.

All scheduler modules register their jobs on the single shared
``AsyncIOScheduler`` instance returned by ``get_scheduler()``.

Lifecycle:
    - ``start_scheduler()`` — called once from ``app/infrastructure/lifespan.py``
    - ``shutdown_scheduler()`` — called once on app teardown

Individual scheduler modules no longer create their own
``AsyncIOScheduler``; they call ``get_scheduler()`` to add jobs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.config import settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = get_logger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Return the shared scheduler instance (creates it lazily)."""
    global _scheduler
    if _scheduler is None:
        # Imported lazily so the heavy ``apscheduler`` package (and its
        # tzdata/deps) do not load at app import time — only when a
        # scheduler is actually requested (never in serverless mode).
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        tz = getattr(settings, "NOTIF_SCHED_TZ", None) or "Asia/Kolkata"
        _scheduler = AsyncIOScheduler(timezone=tz)
    return _scheduler


def start_scheduler() -> None:
    """Start the shared scheduler if not already running."""
    sched = get_scheduler()
    if sched.running:
        logger.info("Shared scheduler already running")
        return
    sched.start()
    logger.info(
        "Shared scheduler started",
        extra={"timezone": sched.timezone},
    )


def shutdown_scheduler() -> None:
    """Shut down the shared scheduler. Called during app lifespan teardown."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Shared scheduler shut down")
