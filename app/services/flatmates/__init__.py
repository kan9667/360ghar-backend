"""Flatmates service package — re-exports all public symbols for backward compatibility."""

from __future__ import annotations

from app.services.flatmates.conversations import (
    get_conversation,
    get_conversation_summary,
    list_conversations,
    list_messages,
    send_message,
)
from app.services.flatmates.helpers import geocode_listing
from app.services.flatmates.matching import (
    list_matches,
    record_swipe,
    unmatch_match,
    unmatch_user_pair,
)
from app.services.flatmates.moderation import (
    create_block,
    create_report,
    delete_block,
    list_blocks,
)
from app.services.flatmates.profiles import (
    get_bootstrap,
    get_flatmates_profile,
    list_catalogs,
    list_discoverable_profiles,
    list_flatmates_notifications,
    mark_all_flatmates_notifications_read,
    mark_flatmates_notification_read,
    update_flatmates_profile,
)
from app.services.flatmates.visits import update_visit_status

__all__ = [
    # profiles
    "get_flatmates_profile",
    "list_discoverable_profiles",
    "update_flatmates_profile",
    "list_catalogs",
    "list_flatmates_notifications",
    "mark_flatmates_notification_read",
    "mark_all_flatmates_notifications_read",
    "get_bootstrap",
    # matching
    "record_swipe",
    "list_matches",
    "unmatch_user_pair",
    "unmatch_match",
    # conversations
    "get_conversation",
    "get_conversation_summary",
    "list_conversations",
    "list_messages",
    "send_message",
    # moderation
    "create_block",
    "delete_block",
    "list_blocks",
    "create_report",
    # visits
    "update_visit_status",
    # helpers
    "geocode_listing",
]
