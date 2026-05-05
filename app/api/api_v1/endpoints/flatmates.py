from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.api_v1.dependencies.auth import get_current_active_user
from app.core.database import get_db
from app.models.enums import PropertyPurpose, PropertyType
from app.models.properties import Property
from app.models.social import MatchQnAAnswer, UserMatch, UserReport
from app.models.users import User
from app.schemas.flatmates import (
    BlockCreate,
    BlockOut,
    CatalogEntry,
    ConversationSummary,
    FlatmatesBootstrap,
    FlatmatesNotificationOut,
    FlatmatesNotificationUpdate,
    FlatmatesPeer,
    FlatmatesProfile,
    FlatmatesProfileUpdate,
    FlatmateVisitUpdate,
    MatchSummary,
    MessageCreate,
    MessageOut,
    QnAAnswers,
    ReportCreate,
    ReportOut,
    SwipeRequest,
    SwipeResult,
)
from app.schemas.user import User as UserSchema
from app.services.flatmates import (
    create_block,
    create_report,
    delete_block,
    get_bootstrap,
    get_conversation,
    get_conversation_summary,
    get_flatmates_profile,
    list_blocks,
    list_catalogs,
    list_conversations,
    list_discoverable_profiles,
    list_flatmates_notifications,
    list_matches,
    list_messages,
    mark_all_flatmates_notifications_read,
    mark_flatmates_notification_read,
    record_swipe,
    send_message,
    unmatch_match,
    unmatch_user_pair,
    update_flatmates_profile,
)

router = APIRouter()


FLATMATE_LISTING_TYPES = (PropertyType.flatmate, PropertyType.pg)


def _is_admin_user(user: UserSchema) -> bool:
    return bool(getattr(user, "is_admin", False) or getattr(user, "role", None) == "admin")


def _listing_moderation_status_expr():
    return func.coalesce(
        Property.listing_preferences["moderation_status"].as_string(),
        "pending_review",
    )


def _flatmate_listing_filters(status: str):
    return (
        Property.property_type.in_(FLATMATE_LISTING_TYPES),
        Property.purpose == PropertyPurpose.rent,
        _listing_moderation_status_expr() == status,
    )


def _serialize_flatmate_listing(listing: Property) -> dict[str, Any]:
    preferences = (
        dict(listing.listing_preferences) if isinstance(listing.listing_preferences, dict) else {}
    )
    moderation_status = preferences.get("moderation_status", "pending_review")
    raw_features = listing.features or []
    if isinstance(raw_features, list):
        features = [str(feature) for feature in raw_features]
    elif isinstance(raw_features, dict):
        features = [str(key) for key, value in raw_features.items() if value]
    else:
        features = []
    return {
        "id": listing.id,
        "title": listing.title,
        "description": listing.description,
        "property_type": listing.property_type,
        "purpose": listing.purpose,
        "property_status": listing.status,
        "moderation_status": moderation_status,
        "status": moderation_status,
        "monthly_rent": listing.monthly_rent,
        "security_deposit": listing.security_deposit,
        "maintenance_charges": listing.maintenance_charges,
        "area_sqft": listing.area_sqft,
        "bedrooms": listing.bedrooms,
        "bathrooms": listing.bathrooms,
        "features": features,
        "city": listing.city,
        "locality": listing.locality,
        "main_image_url": listing.main_image_url,
        "owner_id": listing.owner_id,
        "is_available": listing.is_available,
        "listing_preferences": preferences,
        "created_at": listing.created_at,
        "updated_at": listing.updated_at,
    }


def _serialize_user_summary(user: User | None) -> dict[str, Any] | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "profile_image_url": user.profile_image_url,
    }


def _serialize_report(
    report: UserReport,
    user_map: dict[int, User] | None = None,
) -> dict[str, Any]:
    user_map = user_map or {}
    return {
        "id": report.id,
        "reporter_user_id": report.reporter_user_id,
        "reported_user_id": report.reported_user_id,
        "conversation_id": report.conversation_id,
        "property_id": report.property_id,
        "reason": report.reason,
        "status": report.status,
        "notes": report.notes,
        "description": report.notes,
        "admin_notes": report.notes,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
        "reporter": _serialize_user_summary(user_map.get(report.reporter_user_id)),
        "reported_user": _serialize_user_summary(user_map.get(report.reported_user_id)),
    }


async def _dispatch_moderation_notification(
    db: AsyncSession,
    *,
    recipient_db_id: int,
    title: str,
    body: str,
    type_key: str,
    deep_link: str = "/post",
) -> None:
    """Send a push notification for listing moderation events."""
    from app.services.push_notification import _dispatch

    await _dispatch(
        db,
        user_db_id=recipient_db_id,
        type_key=type_key,
        title=title,
        body=body,
        data={"route": deep_link},
        deep_link=deep_link,
    )


@router.get("/bootstrap", response_model=FlatmatesBootstrap)
async def get_flatmates_bootstrap(
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_bootstrap(db, current_user.id)


@router.get("/catalogs", response_model=list[CatalogEntry])
async def get_flatmates_catalogs(
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    del current_user
    return await list_catalogs(db)


@router.get("/profile", response_model=FlatmatesProfile)
async def get_profile(
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_flatmates_profile(db, current_user.id)


@router.put("/profile", response_model=FlatmatesProfile)
async def update_profile(
    payload: FlatmatesProfileUpdate,
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await update_flatmates_profile(db, current_user.id, payload)


@router.get("/profiles", response_model=list[FlatmatesPeer])
async def get_discoverable_profiles(
    city: str | None = Query(default=None),
    budget_min: int | None = Query(default=None),
    budget_max: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_discoverable_profiles(
        db,
        current_user.id,
        city=city,
        budget_min=budget_min,
        budget_max=budget_max,
        limit=limit,
        offset=offset,
    )


@router.post("/swipes", response_model=SwipeResult)
async def swipe(
    payload: SwipeRequest,
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await record_swipe(db, current_user.id, payload)


@router.get("/conversations", response_model=list[ConversationSummary])
async def get_conversations(
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_conversations(db, current_user.id)


@router.get("/conversations/{conversation_id}", response_model=ConversationSummary)
async def get_conversation_detail(
    conversation_id: int,
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_conversation_summary(db, conversation_id, current_user.id)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def get_conversation_messages(
    conversation_id: int,
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_messages(db, conversation_id, current_user.id)


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut)
async def post_conversation_message(
    conversation_id: int,
    payload: MessageCreate,
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await send_message(db, conversation_id, current_user.id, payload)


@router.get("/matches", response_model=list[MatchSummary])
async def get_matches(
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_matches(db, current_user.id)


@router.put("/matches/{match_id}/unmatch")
async def unmatch(
    match_id: int,
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await unmatch_match(db, current_user.id, match_id)


@router.get("/blocks")
async def get_blocked_users(
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_blocks(db, current_user.id)


@router.delete("/blocks/{blocked_user_id}", response_model=dict[str, Any])
async def unblock_user(
    blocked_user_id: int,
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await delete_block(db, current_user.id, blocked_user_id)


@router.post("/blocks", response_model=BlockOut | dict[str, Any])
async def block_user(
    payload: BlockCreate,
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.unmatch_only:
        return await unmatch_user_pair(db, current_user.id, payload.blocked_user_id)
    return await create_block(db, current_user.id, payload.blocked_user_id)


@router.post("/reports", response_model=ReportOut)
async def report_user(
    payload: ReportCreate,
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await create_report(db, current_user.id, payload)


@router.get("/notifications", response_model=list[FlatmatesNotificationOut])
async def get_flatmates_notifications(
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_flatmates_notifications(db, current_user.id)


@router.put("/notifications", response_model=dict[str, Any])
async def mark_flatmates_notifications(
    payload: FlatmatesNotificationUpdate,
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    del payload
    return await mark_all_flatmates_notifications_read(db, current_user.id)


@router.put("/notifications/{notification_id}", response_model=dict[str, Any])
async def mark_flatmates_notification(
    notification_id: str,
    payload: FlatmatesNotificationUpdate,
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    del payload
    return await mark_flatmates_notification_read(db, current_user.id, notification_id)


@router.put("/visits/{visit_id}")
async def update_flatmate_visit(
    visit_id: int,
    payload: FlatmateVisitUpdate,
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.flatmates import update_visit_status

    return await update_visit_status(db, current_user.id, visit_id, payload)


@router.post("/conversations/{conversation_id}/mark-read")
async def mark_conversation_as_read(
    conversation_id: int,
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all messages in a conversation as read for the current user."""
    from app.models.social import UserMessage

    await get_conversation(db, conversation_id, current_user.id)

    now = datetime.now(timezone.utc)
    await db.execute(
        update(UserMessage)
        .where(
            UserMessage.conversation_id == conversation_id,
            UserMessage.sender_id != current_user.id,
            UserMessage.read_at.is_(None),
        )
        .values(read_at=now)
    )

    # Update conversation last_message_at to trigger UI update
    from app.models.social import UserConversation

    await db.execute(
        update(UserConversation)
        .where(UserConversation.id == conversation_id)
        .values(last_message_at=now)
    )

    await db.commit()

    return {"status": "success"}


@router.post("/conversations/{conversation_id}/qa")
@router.post("/conversations/{conversation_id}/qna")
async def save_qna_answers(
    conversation_id: int,
    payload: QnAAnswers,
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Save Q&A answers for a match. Answers is a dict with question_index as key."""
    # Get the conversation to find the match
    from app.models.social import UserConversation

    result = await db.execute(
        select(UserConversation).where(
            UserConversation.id == conversation_id,
            (UserConversation.user_one_id == current_user.id)
            | (UserConversation.user_two_id == current_user.id),
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    other_user_id = (
        conversation.user_two_id
        if conversation.user_one_id == current_user.id
        else conversation.user_one_id
    )

    # Get or create the match
    match_result = await db.execute(
        select(UserMatch).where(
            ((UserMatch.user_one_id == current_user.id) & (UserMatch.user_two_id == other_user_id))
            | (
                (UserMatch.user_two_id == current_user.id)
                & (UserMatch.user_one_id == other_user_id)
            )
        )
    )
    user_match = match_result.scalar_one_or_none()

    if not user_match:
        # Create a match if it doesn't exist (shouldn't happen in normal flow)
        user_one_id, user_two_id = (
            (current_user.id, other_user_id)
            if current_user.id < other_user_id
            else (other_user_id, current_user.id)
        )
        user_match = UserMatch(
            user_one_id=user_one_id,
            user_two_id=user_two_id,
            context_property_id=conversation.context_property_id,
            status="active",
        )
        db.add(user_match)
        await db.flush()

    existing = await db.execute(
        select(MatchQnAAnswer).where(
            MatchQnAAnswer.match_id == user_match.id,
            MatchQnAAnswer.user_id == current_user.id,
        )
    )
    qna_answer = existing.scalar_one_or_none()
    if qna_answer is None:
        qna_answer = MatchQnAAnswer(
            match_id=user_match.id,
            user_id=current_user.id,
        )
        db.add(qna_answer)

    answer_fields = {
        0: "q1",
        1: "q2",
        2: "q3",
    }

    for idx_str, answer_text in payload.answers.items():
        idx = int(idx_str)
        answer_field = answer_fields.get(idx)
        if answer_field is None:
            continue
        setattr(qna_answer, answer_field, str(answer_text))

    await db.commit()

    return {"status": "success", "match_id": user_match.id}


# Admin moderation endpoints
@router.get("/moderation/listings")
async def get_pending_listings(
    status: str = Query(default="pending_review", description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get listings pending moderation review. Requires admin role."""
    # Check if user has admin role
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")

    result = await db.execute(
        select(Property)
        .where(*_flatmate_listing_filters(status))
        .order_by(Property.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    listings = result.scalars().all()

    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(Property).where(*_flatmate_listing_filters(status))
    )
    total = count_result.scalar()

    return {
        "listings": [_serialize_flatmate_listing(listing) for listing in listings],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.put("/moderation/listings/{listing_id}")
async def moderate_listing(
    listing_id: int,
    payload: dict[str, Any],
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Moderate a listing: approve, reject, or request edit. Requires admin role."""
    # Check if user has admin role
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")

    action = payload.get("action")  # "approve", "reject", "request_edit"
    reason = payload.get("reason", "")

    if action not in ["approve", "reject", "request_edit"]:
        raise HTTPException(status_code=400, detail="Invalid action")

    # Get the listing
    result = await db.execute(
        select(Property).where(
            Property.id == listing_id,
            Property.property_type.in_(FLATMATE_LISTING_TYPES),
            Property.purpose == PropertyPurpose.rent,
        )
    )
    listing = result.scalar_one_or_none()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Update status based on action
    status_map = {
        "approve": "live",
        "reject": "rejected",
        "request_edit": "pending_review",
    }
    moderation_status = status_map[action]
    listing.is_available = action == "approve"

    # Store rejection/request_edit reason
    preferences = (
        dict(listing.listing_preferences) if isinstance(listing.listing_preferences, dict) else {}
    )
    preferences["moderation_status"] = moderation_status
    preferences["moderated_by"] = current_user.id
    preferences["moderated_at"] = datetime.now(timezone.utc).isoformat()
    if reason:
        preferences["moderation_reason"] = reason
    listing.listing_preferences = preferences

    await db.commit()
    await db.refresh(listing)

    # Send push notification to listing owner
    from app.services.push_notification import notify_listing_approved

    if action == "approve":
        await notify_listing_approved(
            db,
            recipient_db_id=listing.owner_id,
            listing_title=listing.title or "Your listing",
        )
    elif action == "reject":
        await _dispatch_moderation_notification(
            db,
            recipient_db_id=listing.owner_id,
            title="Listing Rejected",
            body=f'Your listing "{listing.title or "Your listing"}" was not approved.'
            + (f" Reason: {reason}" if reason else ""),
            type_key="flatmate_listing_rejected",
            deep_link="/post",
        )

    return {
        "listing_id": listing_id,
        "action": action,
        "status": moderation_status,
        "reason": reason,
    }


@router.get("/moderation/reports")
async def get_pending_reports(
    status: str = Query(default="open", description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user reports pending review. Requires admin role."""
    # Check if user has admin role
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")

    result = await db.execute(
        select(UserReport)
        .where(UserReport.status == status)
        .order_by(UserReport.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    reports = result.scalars().all()
    user_ids = {
        user_id
        for report in reports
        for user_id in (report.reporter_user_id, report.reported_user_id)
    }
    user_map: dict[int, User] = {}
    if user_ids:
        users = (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        user_map = {user.id: user for user in users}

    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(UserReport).where(UserReport.status == status)
    )
    total = count_result.scalar()

    return {
        "reports": [_serialize_report(report, user_map) for report in reports],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.put("/moderation/reports/{report_id}")
async def moderate_report(
    report_id: int,
    payload: dict[str, Any],
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Moderate a user report. Requires admin role."""
    # Check if user has admin role
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")

    action = payload.get("action")  # "dismiss", "warn_user", "suspend_user"
    notes = payload.get("notes", "")

    if action not in ["dismiss", "warn_user", "suspend_user", "escalate"]:
        raise HTTPException(status_code=400, detail="Invalid action")

    # Get the report
    result = await db.execute(select(UserReport).where(UserReport.id == report_id))
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Update report status
    status_map = {
        "dismiss": "dismissed",
        "warn_user": "actioned",
        "suspend_user": "actioned",
        "escalate": "reviewed",
    }
    report.status = status_map[action]
    if notes:
        report.notes = notes

    # Take action on the reported user within the same transaction
    from app.services.push_notification import _dispatch

    if action == "suspend_user":
        # Suspend the reported user
        reported_user = await db.execute(select(User).where(User.id == report.reported_user_id))
        user = reported_user.scalar_one_or_none()
        if user:
            user.is_active = False

    # Flush all changes in a single transaction before committing
    await db.flush()
    await db.commit()
    await db.refresh(report)

    # Send push notifications (best-effort, after commit)
    if action == "suspend_user":
        # Notify reported user about suspension
        await _dispatch(
            db,
            user_db_id=report.reported_user_id,
            type_key="flatmate_account_suspended",
            title="Account Suspended",
            body="Your account has been suspended due to a policy violation.",
            data={"route": "/profile"},
            deep_link="/profile",
        )
        # Notify reporter that action was taken
        await _dispatch(
            db,
            user_db_id=report.reporter_user_id,
            type_key="flatmate_report_actioned",
            title="Report Actioned",
            body="We've taken action on your report. Thank you for keeping the community safe.",
            data={"route": "/chats"},
            deep_link="/chats",
        )
    elif action == "warn_user":
        # Notify reported user about warning
        await _dispatch(
            db,
            user_db_id=report.reported_user_id,
            type_key="flatmate_account_warned",
            title="Account Warning",
            body="You've received a warning regarding your behaviour. Please review our community guidelines.",
            data={"route": "/profile"},
            deep_link="/profile",
        )
        # Notify reporter that action was taken
        await _dispatch(
            db,
            user_db_id=report.reporter_user_id,
            type_key="flatmate_report_actioned",
            title="Report Actioned",
            body="We've reviewed your report and issued a warning. Thank you for keeping the community safe.",
            data={"route": "/chats"},
            deep_link="/chats",
        )
    elif action == "dismiss":
        # Notify reporter that report was dismissed
        await _dispatch(
            db,
            user_db_id=report.reporter_user_id,
            type_key="flatmate_report_dismissed",
            title="Report Dismissed",
            body="We've reviewed your report and found no policy violation at this time.",
            data={"route": "/chats"},
            deep_link="/chats",
        )

    return {
        "report_id": report_id,
        "action": action,
        "status": report.status,
        "notes": notes,
    }


@router.post("/moderation/prescreen/{listing_id}")
async def prescreen_listing(
    listing_id: int,
    current_user: UserSchema = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """AI pre-screening endpoint — placeholder for V2. Requires admin role."""
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return {"listing_id": listing_id, "prescreen_result": "pending", "flags": []}
