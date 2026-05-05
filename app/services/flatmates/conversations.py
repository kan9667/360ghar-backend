"""Conversation and message CRUD."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestException
from app.core.logging import get_logger
from app.models.enums import ConversationSource, ConversationStatus
from app.models.social import UserConversation, UserMessage
from app.models.users import User
from app.schemas.flatmates import MessageCreate
from app.services.flatmates.helpers import (
    _build_peer_payload,
    _build_property_context,
    _canonical_pair,
)

logger = get_logger(__name__)


async def _ensure_conversation(
    db: AsyncSession,
    *,
    user_id: int,
    other_user_id: int,
    created_by_user_id: int,
    source: str,
    context_property_id: int | None = None,
) -> UserConversation:
    user_one_id, user_two_id = _canonical_pair(user_id, other_user_id)
    stmt = select(UserConversation).where(
        UserConversation.user_one_id == user_one_id,
        UserConversation.user_two_id == user_two_id,
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    if conversation:
        if context_property_id is not None:
            conversation.context_property_id = context_property_id
        if conversation.status != ConversationStatus.active.value:
            conversation.status = ConversationStatus.active.value
        if source == ConversationSource.profile_match.value:
            conversation.source = source
        return conversation

    conversation = UserConversation(
        user_one_id=user_one_id,
        user_two_id=user_two_id,
        created_by_user_id=created_by_user_id,
        context_property_id=context_property_id,
        source=source,
    )
    db.add(conversation)
    await db.flush()
    return conversation


async def _match_created_at(
    db: AsyncSession,
    user_id: int,
    peer_id: int,
) -> datetime | None:
    from app.models.social import UserMatch

    user_one_id, user_two_id = _canonical_pair(user_id, peer_id)
    result = await db.execute(
        select(UserMatch.created_at).where(
            UserMatch.user_one_id == user_one_id,
            UserMatch.user_two_id == user_two_id,
        )
    )
    return result.scalar_one_or_none()


async def get_conversation_summary(
    db: AsyncSession,
    conversation_id: int,
    user_id: int,
) -> dict[str, Any]:
    current_user = await db.get(User, user_id)
    conversation = await get_conversation(db, conversation_id, user_id)
    peer_id = (
        conversation.user_two_id
        if conversation.user_one_id == user_id
        else conversation.user_one_id
    )
    peer = await db.get(User, peer_id)
    if peer is None:
        raise BadRequestException(detail="Conversation not found")

    unread_count_stmt = select(func.count(UserMessage.id)).where(
        UserMessage.conversation_id == conversation.id,
        UserMessage.sender_id != user_id,
        UserMessage.read_at.is_(None),
    )
    unread_count = int((await db.execute(unread_count_stmt)).scalar() or 0)

    return {
        "id": conversation.id,
        "source": conversation.source,
        "status": conversation.status,
        "peer": _build_peer_payload(peer, current_user),
        "context_property": _build_property_context(conversation.context_property),
        "last_message_preview": conversation.last_message_preview,
        "last_message_at": conversation.last_message_at,
        "unread_count": unread_count,
        "matched_at": await _match_created_at(db, user_id, peer_id),
    }


async def list_conversations(db: AsyncSession, user_id: int) -> list[dict[str, Any]]:
    current_user = await db.get(User, user_id)
    stmt = (
        select(UserConversation)
        .options(selectinload(UserConversation.context_property))
        .where(
            or_(
                UserConversation.user_one_id == user_id,
                UserConversation.user_two_id == user_id,
            )
        )
        .order_by(
            func.coalesce(UserConversation.last_message_at, UserConversation.created_at).desc()
        )
    )
    conversations = list((await db.execute(stmt)).scalars().all())
    if not conversations:
        return []

    peer_ids = {
        conversation.user_two_id
        if conversation.user_one_id == user_id
        else conversation.user_one_id
        for conversation in conversations
    }
    users_stmt = select(User).where(User.id.in_(peer_ids))
    users = list((await db.execute(users_stmt)).scalars().all())
    user_map = {user.id: user for user in users}

    unread_stmt = (
        select(UserMessage.conversation_id, func.count(UserMessage.id))
        .where(
            UserMessage.conversation_id.in_([conversation.id for conversation in conversations]),
            UserMessage.sender_id != user_id,
            UserMessage.read_at.is_(None),
        )
        .group_by(UserMessage.conversation_id)
    )
    unread_rows = (await db.execute(unread_stmt)).all()
    unread_map = {conversation_id: int(count) for conversation_id, count in unread_rows}

    items: list[dict[str, Any]] = []
    for conversation in conversations:
        peer_id = (
            conversation.user_two_id
            if conversation.user_one_id == user_id
            else conversation.user_one_id
        )
        peer = user_map.get(peer_id)
        if peer is None:
            continue
        items.append(
            {
                "id": conversation.id,
                "source": conversation.source,
                "status": conversation.status,
                "peer": _build_peer_payload(peer, current_user),
                "context_property": _build_property_context(conversation.context_property),
                "last_message_preview": conversation.last_message_preview,
                "last_message_at": conversation.last_message_at,
                "unread_count": unread_map.get(conversation.id, 0),
                "matched_at": await _match_created_at(db, user_id, peer_id),
            }
        )
    return items


async def get_conversation(
    db: AsyncSession,
    conversation_id: int,
    user_id: int,
) -> UserConversation:
    stmt = (
        select(UserConversation)
        .options(selectinload(UserConversation.context_property))
        .where(UserConversation.id == conversation_id)
    )
    conversation = (await db.execute(stmt)).scalar_one_or_none()
    if conversation is None:
        raise BadRequestException(detail="Conversation not found")
    if user_id not in {conversation.user_one_id, conversation.user_two_id}:
        raise BadRequestException(detail="Conversation not found")
    return conversation


async def list_messages(
    db: AsyncSession,
    conversation_id: int,
    user_id: int,
) -> list[UserMessage]:
    await get_conversation(db, conversation_id, user_id)
    stmt = (
        select(UserMessage)
        .where(UserMessage.conversation_id == conversation_id)
        .order_by(UserMessage.created_at.asc())
    )
    messages = list((await db.execute(stmt)).scalars().all())
    now = datetime.now(timezone.utc)
    for message in messages:
        if message.sender_id != user_id and message.read_at is None:
            message.read_at = now
    await db.flush()
    return messages


async def send_message(
    db: AsyncSession,
    conversation_id: int,
    user_id: int,
    payload: MessageCreate,
) -> UserMessage:
    conversation = await get_conversation(db, conversation_id, user_id)
    if conversation.status != ConversationStatus.active.value:
        raise BadRequestException(detail="Conversation is not active")

    body = payload.body.strip() if payload.body else None
    message = UserMessage(
        conversation_id=conversation.id,
        sender_id=user_id,
        body=body,
        attachment_url=payload.attachment_url,
        message_type=payload.message_type.value,
    )
    db.add(message)
    await db.flush()
    conversation.last_message_at = datetime.now(timezone.utc)
    conversation.last_message_preview = body or payload.attachment_url or "Attachment"
    await db.flush()
    await db.refresh(message)

    # --- Push notification to peer ---
    peer_id = (
        conversation.user_two_id
        if conversation.user_one_id == user_id
        else conversation.user_one_id
    )
    try:
        from app.services.push_notification import notify_new_message

        sender = await db.get(User, user_id)
        sender_name = sender.full_name or "Someone"
        await notify_new_message(
            db,
            recipient_db_id=peer_id,
            sender_name=sender_name,
            conversation_id=conversation.id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Message notification failed (best-effort): %s", exc, exc_info=True)
        pass  # best-effort; never block message delivery

    return message
