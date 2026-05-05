"""
Seed data script for flatmates end-to-end QA.

Creates:
- 10 flatmate test users with varied profiles
- 5 matches between users
- 5 conversations with messages (varied lengths)
- 3 visits (1 scheduled, 1 confirmed, 1 completed)
- 2 blocks
- 1 report

Idempotent: checks if data exists before creating.
Runnable via: ``python scripts/seed_flatmates_data.py``
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

# Ensure the project root is on sys.path so ``app`` is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.enums import (
    ConversationSource,
    FlatmatesMode,
    FlatmatesProfileStatus,
    MessageType,
    UserMatchStatus,
    UserReportReason,
    VisitContext,
    VisitStatus,
)
from app.models.properties import Property, Visit
from app.models.social import (
    UserBlock,
    UserConversation,
    UserMatch,
    UserMessage,
    UserReport,
)
from app.models.users import User, UserSwipe

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Seed user definitions
# ---------------------------------------------------------------------------

PLACEHOLDER_PHOTO = "https://placehold.co/400x400/EEE/31343C?text=Flatmate"

USERS: list[dict[str, Any]] = [
    {
        "phone": "+91999990001",
        "email": "flatmate.seed.01@360ghar.test",
        "full_name": "Arjun Sharma",
        "profile_image_url": PLACEHOLDER_PHOTO,
        "flatmates_mode": FlatmatesMode.seeker.value,
        "flatmates_bio": "Software engineer looking for a chill flat in Koramangala. Clean, respectful, love cooking.",
        "flatmates_budget_min": 8000,
        "flatmates_budget_max": 15000,
        "flatmates_move_in_timeline": "immediately",
        "flatmates_city": "Bangalore",
        "flatmates_locality": "Koramangala",
        "flatmates_sleep_schedule": "night_owl",
        "flatmates_cleanliness": "balanced",
        "flatmates_food_habits": "non_veg",
        "flatmates_smoking_drinking": "occasionally",
        "flatmates_guests_policy": "occasionally",
        "flatmates_work_style": "hybrid",
    },
    {
        "phone": "+91999990002",
        "email": "flatmate.seed.02@360ghar.test",
        "full_name": "Priya Patel",
        "profile_image_url": PLACEHOLDER_PHOTO,
        "flatmates_mode": FlatmatesMode.room_poster.value,
        "flatmates_bio": "Have a 2BHK in HSR Layout, looking for a female flatmate. The apartment is fully furnished with AC and WiFi.",
        "flatmates_budget_min": 10000,
        "flatmates_budget_max": 18000,
        "flatmates_move_in_timeline": "within_2_weeks",
        "flatmates_city": "Bangalore",
        "flatmates_locality": "HSR Layout",
        "flatmates_sleep_schedule": "early_bird",
        "flatmates_cleanliness": "meticulous",
        "flatmates_food_habits": "veg",
        "flatmates_smoking_drinking": "never",
        "flatmates_guests_policy": "rarely",
        "flatmates_work_style": "wfh",
    },
    {
        "phone": "+91999990003",
        "email": "flatmate.seed.03@360ghar.test",
        "full_name": "Rahul Verma",
        "profile_image_url": PLACEHOLDER_PHOTO,
        "flatmates_mode": FlatmatesMode.co_hunter.value,
        "flatmates_bio": "Looking to team up and find a place together in Indiranagar. Working at a startup, easy going.",
        "flatmates_budget_min": 12000,
        "flatmates_budget_max": 20000,
        "flatmates_move_in_timeline": "within_1_month",
        "flatmates_city": "Bangalore",
        "flatmates_locality": "Indiranagar",
        "flatmates_sleep_schedule": "night_owl",
        "flatmates_cleanliness": "laid_back",
        "flatmates_food_habits": "non_veg",
        "flatmates_smoking_drinking": "regularly",
        "flatmates_guests_policy": "comfortable",
        "flatmates_work_style": "office",
    },
    {
        "phone": "+91999990004",
        "email": "flatmate.seed.04@360ghar.test",
        "full_name": "Neha Gupta",
        "profile_image_url": PLACEHOLDER_PHOTO,
        "flatmates_mode": FlatmatesMode.seeker.value,
        "flatmates_bio": "Designer who loves plants, coffee, and good conversations. Looking for a creative space.",
        "flatmates_budget_min": 10000,
        "flatmates_budget_max": 16000,
        "flatmates_move_in_timeline": "flexible",
        "flatmates_city": "Bangalore",
        "flatmates_locality": "JP Nagar",
        "flatmates_sleep_schedule": "early_bird",
        "flatmates_cleanliness": "meticulous",
        "flatmates_food_habits": "veg",
        "flatmates_smoking_drinking": "never",
        "flatmates_guests_policy": "occasionally",
        "flatmates_work_style": "hybrid",
    },
    {
        "phone": "+91999990005",
        "email": "flatmate.seed.05@360ghar.test",
        "full_name": "Vikram Singh",
        "profile_image_url": PLACEHOLDER_PHOTO,
        "flatmates_mode": FlatmatesMode.room_poster.value,
        "flatmates_bio": "Have a spacious room in Whitefield near ITPL. Gated community with gym and pool. Looking for a professional flatmate.",
        "flatmates_budget_min": 9000,
        "flatmates_budget_max": 14000,
        "flatmates_move_in_timeline": "immediately",
        "flatmates_city": "Bangalore",
        "flatmates_locality": "Whitefield",
        "flatmates_sleep_schedule": "night_owl",
        "flatmates_cleanliness": "balanced",
        "flatmates_food_habits": "non_veg",
        "flatmates_smoking_drinking": "occasionally",
        "flatmates_guests_policy": "comfortable",
        "flatmates_work_style": "office",
    },
    {
        "phone": "+91999990006",
        "email": "flatmate.seed.06@360ghar.test",
        "full_name": "Ananya Iyer",
        "profile_image_url": PLACEHOLDER_PHOTO,
        "flatmates_mode": FlatmatesMode.open_to_both.value,
        "flatmates_bio": "Flexible and friendly. Can either share my place or join yours. Big on yoga and cooking.",
        "flatmates_budget_min": 7000,
        "flatmates_budget_max": 13000,
        "flatmates_move_in_timeline": "within_2_weeks",
        "flatmates_city": "Bangalore",
        "flatmates_locality": "BTM Layout",
        "flatmates_sleep_schedule": "early_bird",
        "flatmates_cleanliness": "meticulous",
        "flatmates_food_habits": "veg",
        "flatmates_smoking_drinking": "never",
        "flatmates_guests_policy": "rarely",
        "flatmates_work_style": "wfh",
    },
    {
        "phone": "+91999990007",
        "email": "flatmate.seed.07@360ghar.test",
        "full_name": "Karan Mehta",
        "profile_image_url": PLACEHOLDER_PHOTO,
        "flatmates_mode": FlatmatesMode.seeker.value,
        "flatmates_bio": "Data scientist, gym enthusiast, and Netflix binger. Looking for a flat near Marathahalli.",
        "flatmates_budget_min": 8000,
        "flatmates_budget_max": 15000,
        "flatmates_move_in_timeline": "within_1_month",
        "flatmates_city": "Bangalore",
        "flatmates_locality": "Marathahalli",
        "flatmates_sleep_schedule": "night_owl",
        "flatmates_cleanliness": "laid_back",
        "flatmates_food_habits": "non_veg",
        "flatmates_smoking_drinking": "occasionally",
        "flatmates_guests_policy": "occasionally",
        "flatmates_work_style": "hybrid",
    },
    {
        "phone": "+91999990008",
        "email": "flatmate.seed.08@360ghar.test",
        "full_name": "Sneha Reddy",
        "profile_image_url": PLACEHOLDER_PHOTO,
        "flatmates_mode": FlatmatesMode.room_poster.value,
        "flatmates_bio": "3BHK in Electronic City with a gorgeous balcony. Want a flatmate who loves pets -- I have a cat!",
        "flatmates_budget_min": 6000,
        "flatmates_budget_max": 11000,
        "flatmates_move_in_timeline": "flexible",
        "flatmates_city": "Bangalore",
        "flatmates_locality": "Electronic City",
        "flatmates_sleep_schedule": "early_bird",
        "flatmates_cleanliness": "balanced",
        "flatmates_food_habits": "veg",
        "flatmates_smoking_drinking": "never",
        "flatmates_guests_policy": "occasionally",
        "flatmates_work_style": "wfh",
    },
    {
        "phone": "+91999990009",
        "email": "flatmate.seed.09@360ghar.test",
        "full_name": "Deepak Nair",
        "profile_image_url": PLACEHOLDER_PHOTO,
        "flatmates_mode": FlatmatesMode.co_hunter.value,
        "flatmates_bio": "Music producer by night, product manager by day. Want to find a cool pad in Jayanagar with someone.",
        "flatmates_budget_min": 10000,
        "flatmates_budget_max": 18000,
        "flatmates_move_in_timeline": "within_2_weeks",
        "flatmates_city": "Bangalore",
        "flatmates_locality": "Jayanagar",
        "flatmates_sleep_schedule": "night_owl",
        "flatmates_cleanliness": "laid_back",
        "flatmates_food_habits": "non_veg",
        "flatmates_smoking_drinking": "regularly",
        "flatmates_guests_policy": "comfortable",
        "flatmates_work_style": "hybrid",
    },
    {
        "phone": "+91999990010",
        "email": "flatmate.seed.10@360ghar.test",
        "full_name": "Meera Joshi",
        "profile_image_url": PLACEHOLDER_PHOTO,
        "flatmates_mode": FlatmatesMode.seeker.value,
        "flatmates_bio": "Recent grad joining an MNC. Looking for a female flatmate near Hebbal. Love reading and baking!",
        "flatmates_budget_min": 9000,
        "flatmates_budget_max": 16000,
        "flatmates_move_in_timeline": "within_1_month",
        "flatmates_city": "Bangalore",
        "flatmates_locality": "Hebbal",
        "flatmates_sleep_schedule": "early_bird",
        "flatmates_cleanliness": "meticulous",
        "flatmates_food_habits": "veg",
        "flatmates_smoking_drinking": "never",
        "flatmates_guests_policy": "rarely",
        "flatmates_work_style": "office",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_or_create_user(db: AsyncSession, data: dict[str, Any]) -> tuple[User, bool]:
    """Return (user, was_created) — existing user by email or create a new one."""
    stmt = select(User).where(User.email == data["email"])
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        return existing, False

    user = User(
        supabase_user_id=str(uuid.uuid4()),
        is_active=True,
        is_verified=True,
        role="user",
        flatmates_onboarding_completed=True,
        flatmates_profile_status=FlatmatesProfileStatus.active.value,
        flatmates_last_active_at=datetime.now(timezone.utc),
        preferences={},
        notification_settings={},
        privacy_settings={},
        **data,
    )
    db.add(user)
    await db.flush()
    return user, True


async def _get_or_create_match(
    db: AsyncSession, user_one_id: int, user_two_id: int
) -> UserMatch:
    """Return existing match or create a new active one."""
    u1, u2 = (user_one_id, user_two_id) if user_one_id < user_two_id else (user_two_id, user_one_id)
    stmt = select(UserMatch).where(
        UserMatch.user_one_id == u1,
        UserMatch.user_two_id == u2,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        return existing

    match = UserMatch(
        user_one_id=u1,
        user_two_id=u2,
        status=UserMatchStatus.active.value,
    )
    db.add(match)
    await db.flush()
    return match


async def _get_or_create_conversation(
    db: AsyncSession,
    user_one_id: int,
    user_two_id: int,
    *,
    created_by_user_id: int,
    source: str = ConversationSource.profile_match.value,
) -> UserConversation:
    """Return existing conversation or create a new one."""
    u1, u2 = (user_one_id, user_two_id) if user_one_id < user_two_id else (user_two_id, user_one_id)
    stmt = select(UserConversation).where(
        UserConversation.user_one_id == u1,
        UserConversation.user_two_id == u2,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        return existing

    conv = UserConversation(
        user_one_id=u1,
        user_two_id=u2,
        created_by_user_id=created_by_user_id,
        source=source,
        status="active",
    )
    db.add(conv)
    await db.flush()
    return conv


async def _add_message(
    db: AsyncSession,
    conversation_id: int,
    sender_id: int,
    body: str,
    minutes_ago: int = 0,
) -> UserMessage:
    """Add a single message to a conversation."""
    msg = UserMessage(
        conversation_id=conversation_id,
        sender_id=sender_id,
        body=body,
        message_type=MessageType.text.value,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
    )
    db.add(msg)
    await db.flush()
    return msg


async def _count_rows(db: AsyncSession, model) -> int:
    stmt = select(func.count(model.id))
    result = await db.execute(stmt)
    return int(result.scalar() or 0)


# ---------------------------------------------------------------------------
# Main seed function
# ---------------------------------------------------------------------------

async def seed_flatmates_data() -> dict[str, int]:
    """Create flatmates seed data. Returns counts of created entities."""
    stats: dict[str, int] = {
        "users": 0,
        "matches": 0,
        "conversations": 0,
        "messages": 0,
        "visits": 0,
        "blocks": 0,
        "reports": 0,
    }

    async with AsyncSessionLocal() as db:
        try:
            # -----------------------------------------------------------------
            # 1. Create users
            # -----------------------------------------------------------------
            user_objects: list[User] = []
            for user_data in USERS:
                user, was_created = await _get_or_create_user(db, user_data)
                user_objects.append(user)
                if was_created:
                    stats["users"] += 1

            logger.info(f"Ensured {len(user_objects)} seed users exist")

            # -----------------------------------------------------------------
            # 2. Create reciprocal swipes & 5 matches
            # -----------------------------------------------------------------
            match_pairs = [
                (0, 1),  # Arjun <-> Priya
                (2, 3),  # Rahul <-> Neha
                (4, 5),  # Vikram <-> Ananya
                (6, 7),  # Karan <-> Sneha
                (8, 9),  # Deepak <-> Meera
            ]

            matches: list[UserMatch] = []
            for i, j in match_pairs:
                u_a = user_objects[i]
                u_b = user_objects[j]

                # Create reciprocal swipes
                for swiper, target in [(u_a, u_b), (u_b, u_a)]:
                    stmt = select(UserSwipe).where(
                        UserSwipe.user_id == swiper.id,
                        UserSwipe.target_user_id == target.id,
                    )
                    existing_swipe = (await db.execute(stmt)).scalar_one_or_none()
                    if not existing_swipe:
                        db.add(UserSwipe(
                            user_id=swiper.id,
                            target_user_id=target.id,
                            target_type="user",
                            swipe_action="like",
                            is_liked=True,
                        ))

                match = await _get_or_create_match(db, u_a.id, u_b.id)
                matches.append(match)
                stats["matches"] += 1

            await db.flush()

            # -----------------------------------------------------------------
            # 3. Create 5 conversations with varied message counts
            # -----------------------------------------------------------------
            conv_configs = [
                # (user_i, user_j, source, message_count)
                (0, 1, ConversationSource.listing_interest.value, 1),
                (2, 3, ConversationSource.profile_match.value, 3),
                (4, 5, ConversationSource.profile_match.value, 5),
                (6, 7, ConversationSource.listing_interest.value, 10),
                (8, 9, ConversationSource.profile_match.value, 15),
            ]

            conversations: list[UserConversation] = []
            for i, j, source, msg_count in conv_configs:
                conv = await _get_or_create_conversation(
                    db,
                    user_objects[i].id,
                    user_objects[j].id,
                    created_by_user_id=user_objects[i].id,
                    source=source,
                )
                conversations.append(conv)

                # Simple check: if this conversation already has messages, skip
                existing = (await db.execute(
                    select(func.count(UserMessage.id)).where(
                        UserMessage.conversation_id == conv.id
                    )
                )).scalar() or 0
                if existing > 0:
                    continue

                # Generate messages
                sample_messages = [
                    "Hey! Saw your profile, looks like we'd be great flatmates!",
                    "Thanks for reaching out! What's your typical day like?",
                    "I usually work from home, so I'm around most of the time.",
                    "That works for me. Do you have any pets?",
                    "No pets, but I love animals. Are you okay with occasional guests?",
                    "Sure, as long as it's not too frequent. What about cooking?",
                    "I cook a lot, mostly Indian food. You're welcome to share!",
                    "That sounds perfect. When are you looking to move?",
                    "I'm flexible, ideally within the next 2 weeks.",
                    "Let me check my schedule and get back to you.",
                    "Sounds good, no rush!",
                    "By the way, is the apartment furnished?",
                    "Yes, fully furnished with AC and WiFi included.",
                    "Great, that's exactly what I need.",
                    "Let's plan a visit this weekend?",
                ]
                for m_idx in range(min(msg_count, len(sample_messages))):
                    sender = user_objects[i] if m_idx % 2 == 0 else user_objects[j]
                    await _add_message(
                        db,
                        conv.id,
                        sender.id,
                        sample_messages[m_idx],
                        minutes_ago=(msg_count - m_idx) * 5,
                    )
                    stats["messages"] += 1

                # Update last message preview
                conv.last_message_at = datetime.now(timezone.utc) - timedelta(minutes=5)
                conv.last_message_preview = sample_messages[min(msg_count, len(sample_messages)) - 1][:100]

            stats["conversations"] = len(conversations)
            await db.flush()

            # -----------------------------------------------------------------
            # 4. Create 3 visits (1 scheduled, 1 confirmed, 1 completed)
            # -----------------------------------------------------------------
            now = datetime.now(timezone.utc)
            property_id = (
                await db.execute(select(Property.id).order_by(Property.id.asc()).limit(1))
            ).scalar_one_or_none()

            visit_configs = [
                # (user_i, user_j, status, days_offset)
                (0, 1, VisitStatus.scheduled.value, 5),
                (2, 3, VisitStatus.confirmed.value, 3),
                (4, 5, VisitStatus.completed.value, -7),
            ]

            if property_id is None:
                logger.warning("Skipping flatmate visit seeds because no property exists")

            visit_seed_configs = visit_configs if property_id is not None else []
            for i, j, status, days_offset in visit_seed_configs:
                # Check if visit already exists between these users
                u1, u2 = user_objects[i].id, user_objects[j].id
                existing_visit = (await db.execute(
                    select(Visit).where(
                        Visit.user_id == u1,
                        Visit.counterparty_user_id == u2,
                    )
                )).scalar_one_or_none()
                if existing_visit:
                    continue

                visit = Visit(
                    user_id=u1,
                    property_id=property_id,
                    counterparty_user_id=u2,
                    visit_context=VisitContext.flatmate_meet.value,
                    scheduled_date=now + timedelta(days=days_offset),
                    actual_date=now + timedelta(days=days_offset) if status == VisitStatus.completed.value else None,
                    status=status,
                )
                db.add(visit)
                stats["visits"] += 1

            await db.flush()

            # -----------------------------------------------------------------
            # 5. Create 2 blocks
            # -----------------------------------------------------------------
            block_pairs = [(0, 2), (3, 6)]  # Arjun blocks Rahul, Neha blocks Karan
            for blocker_idx, blocked_idx in block_pairs:
                blocker_id = user_objects[blocker_idx].id
                blocked_id = user_objects[blocked_idx].id
                existing_block = (await db.execute(
                    select(UserBlock).where(
                        UserBlock.blocker_user_id == blocker_id,
                        UserBlock.blocked_user_id == blocked_id,
                    )
                )).scalar_one_or_none()
                if existing_block:
                    continue

                db.add(UserBlock(
                    blocker_user_id=blocker_id,
                    blocked_user_id=blocked_id,
                ))
                stats["blocks"] += 1

            await db.flush()

            # -----------------------------------------------------------------
            # 6. Create 1 report
            # -----------------------------------------------------------------
            existing_report = (await db.execute(
                select(UserReport).where(
                    UserReport.reporter_user_id == user_objects[0].id,
                    UserReport.reported_user_id == user_objects[6].id,
                )
            )).scalar_one_or_none()
            if not existing_report:
                db.add(UserReport(
                    reporter_user_id=user_objects[0].id,
                    reported_user_id=user_objects[6].id,
                    reason=UserReportReason.fake_profile.value,
                    notes="Profile seems fake -- no real photos, inconsistent bio",
                ))
                stats["reports"] += 1

            await db.flush()
            await db.commit()

            logger.info("Flatmates seed data created", extra=stats)
            return stats

        except Exception:
            await db.rollback()
            raise


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    """Run the seed and print results."""
    from app.core.logging import setup_logging
    setup_logging()

    logger.info("Seeding flatmates data...")
    stats = await seed_flatmates_data()
    logger.info("Seed complete", extra=stats)
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
