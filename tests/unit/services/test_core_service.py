"""
Tests for CoreService page methods.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.exc import InternalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Page
from app.models.enums import PageFormat
from app.schemas.core import PageUpdate
from app.services.core import CoreService


@pytest.fixture
def core_service(db_session: AsyncSession) -> CoreService:
    """CoreService bound to the test session."""
    return CoreService(db_session)


async def _create_public_page(
    session: AsyncSession,
    unique_name: str | None = None,
    view_count: int = 0,
) -> Page:
    """Create a public, active page and commit the savepoint.

    The page is committed in the current session so it survives service-level
    rollbacks while still being rolled back by the test fixture's outer
    transaction.
    """
    unique_name = unique_name or f"privacy-policy-{uuid.uuid4().hex[:8]}"
    page = Page(
        unique_name=unique_name,
        title="Privacy Policy",
        content="<p>Privacy content</p>",
        format=PageFormat.html,
        is_active=True,
        is_draft=False,
        is_private=False,
        view_count=view_count,
    )
    session.add(page)
    await session.commit()
    await session.refresh(page)
    return page


class TestCoreServicePagePublic:
    """Tests for public page access."""

    @pytest.mark.asyncio
    async def test_get_page_public_increments_view_count(
        self, db_session: AsyncSession, core_service: CoreService
    ):
        """Public page fetch should increment view_count when the transaction is writable."""
        page = await _create_public_page(db_session)

        response = await core_service.get_page_public(page.unique_name)

        assert response is not None
        assert response.view_count == 1
        assert response.unique_name == page.unique_name

    @pytest.mark.asyncio
    async def test_get_page_public_returns_page_when_view_count_commit_fails(
        self, db_session: AsyncSession, core_service: CoreService
    ):
        """A read-only transaction (or any DB error) during view count update must not break the response."""
        page = await _create_public_page(db_session)
        original_view_count = page.view_count
        unique_name = page.unique_name

        # Simulate the hosted-pooler read-only scenario: commit() raises.
        err = InternalError(
            "cannot execute UPDATE in a read-only transaction",
            None,
            Exception("read-only"),
        )
        with patch.object(db_session, "commit", AsyncMock(side_effect=err)):
            response = await core_service.get_page_public(unique_name)

        assert response is not None
        assert response.unique_name == unique_name
        # The response should reflect the persisted value; the in-memory increment was rolled back.
        assert response.view_count == original_view_count

    @pytest.mark.asyncio
    async def test_get_page_public_returns_none_for_missing_page(
        self, core_service: CoreService
    ):
        """Public page fetch returns None for a non-existent page."""
        response = await core_service.get_page_public("does-not-exist")
        assert response is None


class TestCoreServiceGetPageByUniqueName:
    """Tests for get_page_by_unique_name (admin/read path)."""

    @pytest.mark.asyncio
    async def test_get_page_by_unique_name_is_pure_read(
        self, db_session: AsyncSession, core_service: CoreService
    ):
        """get_page_by_unique_name must not modify view_count."""
        page = await _create_public_page(db_session)
        original_view_count = page.view_count

        response = await core_service.get_page_by_unique_name(page.unique_name)

        assert response is not None
        assert response.unique_name == page.unique_name
        assert response.view_count == original_view_count

        # Re-fetch from DB to be sure no side effect persisted.
        db_page = (await db_session.execute(select(Page).where(Page.id == page.id))).scalar_one()
        assert db_page.view_count == original_view_count


class TestCoreServiceUpdatePage:
    """Tests for update_page."""

    @pytest.mark.asyncio
    async def test_update_page_updates_updated_at(
        self, db_session: AsyncSession, core_service: CoreService
    ):
        """update_page should set updated_at manually because Core UPDATE does not fire ORM onupdate."""
        page = await _create_public_page(db_session)
        original_updated_at = page.updated_at

        update_data = PageUpdate(title="Updated Privacy Policy")
        response = await core_service.update_page(page.unique_name, update_data)

        assert response is not None
        assert response.title == "Updated Privacy Policy"
        assert response.updated_at is not None
        if original_updated_at is not None:
            assert response.updated_at > original_updated_at
