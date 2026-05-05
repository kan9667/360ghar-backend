"""Report and block logic."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.models.enums import ConversationStatus, UserMatchStatus
from app.models.social import UserBlock, UserConversation, UserMatch, UserReport
from app.models.users import User
from app.schemas.flatmates import ReportCreate
from app.services.flatmates.helpers import _canonical_pair


async def list_blocks(db: AsyncSession, user_id: int) -> list[dict[str, Any]]:
    stmt = (
        select(UserBlock, User)
        .join(User, User.id == UserBlock.blocked_user_id)
        .where(UserBlock.blocker_user_id == user_id)
        .order_by(UserBlock.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": block.id,
            "blocked_user_id": block.blocked_user_id,
            "created_at": block.created_at,
            "user": {
                "id": blocked_user.id,
                "full_name": blocked_user.full_name,
                "profile_image_url": blocked_user.profile_image_url,
                "city": blocked_user.flatmates_city,
                "locality": blocked_user.flatmates_locality,
            },
        }
        for block, blocked_user in rows
    ]


async def delete_block(db: AsyncSession, user_id: int, blocked_user_id: int) -> dict[str, Any]:
    stmt = select(UserBlock).where(
        UserBlock.blocker_user_id == user_id,
        UserBlock.blocked_user_id == blocked_user_id,
    )
    block = (await db.execute(stmt)).scalar_one_or_none()
    if block is None:
        raise BadRequestException(detail="Blocked user not found")
    await db.delete(block)
    await db.flush()
    return {"ok": True, "blocked_user_id": blocked_user_id}


async def create_block(db: AsyncSession, user_id: int, blocked_user_id: int) -> UserBlock:
    if blocked_user_id == user_id:
        raise BadRequestException(detail="Cannot block yourself")
    if await db.get(User, blocked_user_id) is None:
        raise BadRequestException(detail="User not found")
    stmt = select(UserBlock).where(
        UserBlock.blocker_user_id == user_id,
        UserBlock.blocked_user_id == blocked_user_id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        return existing

    block = UserBlock(blocker_user_id=user_id, blocked_user_id=blocked_user_id)
    db.add(block)

    user_one_id, user_two_id = _canonical_pair(user_id, blocked_user_id)
    conversation_stmt = select(UserConversation).where(
        UserConversation.user_one_id == user_one_id,
        UserConversation.user_two_id == user_two_id,
    )
    conversation = (await db.execute(conversation_stmt)).scalar_one_or_none()
    if conversation:
        conversation.status = ConversationStatus.blocked.value

    match_stmt = select(UserMatch).where(
        UserMatch.user_one_id == user_one_id,
        UserMatch.user_two_id == user_two_id,
    )
    match = (await db.execute(match_stmt)).scalar_one_or_none()
    if match:
        match.status = UserMatchStatus.blocked.value

    await db.flush()
    return block


async def create_report(db: AsyncSession, user_id: int, payload: ReportCreate) -> UserReport:
    if payload.reported_user_id == user_id:
        raise BadRequestException(detail="Cannot report yourself")
    if await db.get(User, payload.reported_user_id) is None:
        raise BadRequestException(detail="Reported user not found")
    report = UserReport(
        reporter_user_id=user_id,
        reported_user_id=payload.reported_user_id,
        conversation_id=payload.conversation_id,
        property_id=payload.property_id,
        reason=payload.reason.value,
        notes=payload.notes,
    )
    db.add(report)
    await db.flush()
    await db.refresh(report)
    return report
