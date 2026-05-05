from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    ConversationSource,
    ConversationStatus,
    FlatmatesMode,
    FlatmatesProfileStatus,
    MessageType,
    SwipeAction,
    SwipeTargetType,
    UserMatchStatus,
    UserReportReason,
    UserReportStatus,
    VisitStatus,
)


class DiscoverProfilesQuery(BaseModel):
    """Query parameters for the discovery profiles endpoint."""

    city: str | None = None
    budget_min: int | None = Field(default=None, ge=0)
    budget_max: int | None = Field(default=None, ge=0)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class FlatmatesProfileUpdate(BaseModel):
    full_name: str | None = None
    profile_image_url: str | None = None
    mode: FlatmatesMode | None = None
    profile_status: FlatmatesProfileStatus | None = None
    onboarding_completed: bool | None = None
    bio: str | None = None
    age: int | None = Field(default=None, ge=18, le=100)
    profession: str | None = None
    budget_min: float | None = Field(default=None, ge=0)
    budget_max: float | None = Field(default=None, ge=0)
    move_in_timeline: str | None = None
    city: str | None = None
    locality: str | None = None
    sleep_schedule: str | None = None
    cleanliness: str | None = None
    food_habits: str | None = None
    smoking_drinking: str | None = None
    guests_policy: str | None = None
    work_style: str | None = None
    gender: str | None = None
    gender_preference: str | None = None
    preferences: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_budget_range(self):
        if (
            self.budget_min is not None
            and self.budget_max is not None
            and self.budget_max < self.budget_min
        ):
            raise ValueError("budget_max must be greater than or equal to budget_min")
        return self


class FlatmatesProfile(BaseModel):
    id: int
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    profile_image_url: str | None = None
    mode: FlatmatesMode | None = None
    profile_status: FlatmatesProfileStatus = FlatmatesProfileStatus.draft
    onboarding_completed: bool = False
    bio: str | None = None
    age: int | None = None
    profession: str | None = None
    budget_min: float | None = None
    budget_max: float | None = None
    move_in_timeline: str | None = None
    city: str | None = None
    locality: str | None = None
    sleep_schedule: str | None = None
    cleanliness: str | None = None
    food_habits: str | None = None
    smoking_drinking: str | None = None
    guests_policy: str | None = None
    work_style: str | None = None
    gender: str | None = None
    gender_preference: str | None = None
    preferences: dict[str, Any] = Field(default_factory=dict)
    last_active_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CatalogEntry(BaseModel):
    key: str
    version: int
    payload: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class FlatmatesBootstrap(BaseModel):
    profile: FlatmatesProfile
    catalogs: list[CatalogEntry]
    active_listing_count: int
    conversation_count: int
    unread_message_count: int


class FlatmatesPeer(BaseModel):
    id: int
    full_name: str | None = None
    profile_image_url: str | None = None
    mode: FlatmatesMode | None = None
    city: str | None = None
    locality: str | None = None
    age: int | None = None
    profession: str | None = None
    match_percentage: float | None = None
    phone_number: str | None = None


class ConversationPropertyContext(BaseModel):
    id: int
    title: str
    locality: str | None = None
    city: str | None = None
    monthly_rent: float | None = None
    main_image_url: str | None = None
    owner_name: str | None = None
    owner_image_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ConversationSummary(BaseModel):
    id: int
    source: ConversationSource
    status: ConversationStatus
    peer: FlatmatesPeer
    context_property: ConversationPropertyContext | None = None
    last_message_preview: str | None = None
    last_message_at: datetime | None = None
    unread_count: int = 0
    matched_at: datetime | None = None


class MessageCreate(BaseModel):
    body: str | None = None
    attachment_url: str | None = None
    message_type: MessageType = MessageType.text

    @model_validator(mode="after")
    def validate_content(self):
        if not (self.body and self.body.strip()) and not self.attachment_url:
            raise ValueError("body or attachment_url is required")
        return self


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    body: str | None = None
    attachment_url: str | None = None
    message_type: MessageType
    read_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MatchSummary(BaseModel):
    id: int
    status: UserMatchStatus
    peer: FlatmatesPeer
    context_property: ConversationPropertyContext | None = None
    created_at: datetime


class SwipeRequest(BaseModel):
    target_type: SwipeTargetType
    action: SwipeAction
    property_id: int | None = None
    target_user_id: int | None = None
    context_property_id: int | None = None

    @model_validator(mode="after")
    def validate_target(self):
        if self.target_type == SwipeTargetType.property and self.property_id is None:
            raise ValueError("property_id is required for property swipes")
        if self.target_type == SwipeTargetType.user and self.target_user_id is None:
            raise ValueError("target_user_id is required for user swipes")
        return self


class SwipeResult(BaseModel):
    stored: bool = True
    action: SwipeAction
    target_type: SwipeTargetType
    conversation_id: int | None = None
    match_id: int | None = None
    did_match: bool = False


class ReportCreate(BaseModel):
    reported_user_id: int
    reason: UserReportReason
    conversation_id: int | None = None
    property_id: int | None = None
    notes: str | None = None


class ReportOut(BaseModel):
    id: int
    reporter_user_id: int
    reported_user_id: int
    reason: UserReportReason
    status: UserReportStatus
    notes: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BlockCreate(BaseModel):
    blocked_user_id: int
    unmatch_only: bool = False


class BlockOut(BaseModel):
    id: int
    blocker_user_id: int
    blocked_user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FlatmatesNotificationOut(BaseModel):
    id: str
    type: str = "general"
    title: str
    body: str
    is_read: bool = False
    reference_id: int | None = None
    route: str | None = None
    created_at: datetime


class FlatmatesNotificationUpdate(BaseModel):
    is_read: bool | None = None
    mark_all_read: bool | None = None


class FlatmateVisitUpdate(BaseModel):
    status: VisitStatus | None = None
    scheduled_date: datetime | None = None


class QnAAnswers(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_keys(self):
        for key in self.answers:
            try:
                idx = int(key)
            except ValueError as exc:
                raise ValueError(f"Answer index must be an integer, got '{key}'") from exc
            if idx < 0 or idx > 2:
                raise ValueError(f"Answer index must be between 0 and 2, got {idx}")
        return self
