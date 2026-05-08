from types import SimpleNamespace

import pytest

from app.core.exceptions import BadRequestException
from app.models.social import FlatmateSuperLikeUsage
from app.services.flatmates.matching import (
    SUPER_LIKE_DAILY_CAP,
    _consume_super_like_quota,
)


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar(self):
        return self.value


class _FakeDb:
    def __init__(self, *, existing_usage=None, used_count=0):
        self.responses = [existing_usage, used_count]
        self.statements = []
        self.added = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _ScalarResult(self.responses.pop(0))

    def add(self, obj):
        self.added.append(obj)


@pytest.mark.asyncio
async def test_super_like_quota_adds_usage_when_under_daily_cap():
    db = _FakeDb(used_count=SUPER_LIKE_DAILY_CAP - 1)

    await _consume_super_like_quota(db, user_id=1, target_user_id=2)

    assert len(db.added) == 1
    assert isinstance(db.added[0], FlatmateSuperLikeUsage)
    assert db.added[0].user_id == 1
    assert db.added[0].target_user_id == 2


@pytest.mark.asyncio
async def test_super_like_quota_rejects_when_daily_cap_reached():
    db = _FakeDb(used_count=SUPER_LIKE_DAILY_CAP)

    with pytest.raises(BadRequestException) as exc_info:
        await _consume_super_like_quota(db, user_id=1, target_user_id=2)

    assert "Daily super like limit" in exc_info.value.detail
    assert db.added == []


@pytest.mark.asyncio
async def test_super_like_quota_does_not_double_count_existing_super_like():
    db = _FakeDb()
    existing_swipe = SimpleNamespace(swipe_action="super_like")

    await _consume_super_like_quota(
        db,
        user_id=1,
        target_user_id=2,
        existing_swipe=existing_swipe,
    )

    assert db.statements == []
    assert db.added == []
