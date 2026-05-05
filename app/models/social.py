from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserMatch(Base):
    __tablename__ = "user_matches"
    __table_args__ = (
        Index("idx_user_matches_unique_pair", "user_one_id", "user_two_id", unique=True),
        Index("idx_user_matches_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_one_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    user_two_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    context_property_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("properties.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    context_property: Mapped[Optional["Property"]] = relationship(
        "Property",
        foreign_keys=[context_property_id],
    )


class UserConversation(Base):
    __tablename__ = "user_conversations"
    __table_args__ = (
        Index("idx_user_conversations_unique_pair", "user_one_id", "user_two_id", unique=True),
        Index("idx_user_conversations_last_message", "last_message_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_one_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    user_two_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    context_property_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("properties.id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(32), default="listing_interest")
    status: Mapped[str] = mapped_column(String(32), default="active")
    last_message_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    context_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    context_property: Mapped[Optional["Property"]] = relationship(
        "Property",
        foreign_keys=[context_property_id],
    )
    messages: Mapped[list["UserMessage"]] = relationship(
        "UserMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="UserMessage.created_at",
    )


class UserMessage(Base):
    __tablename__ = "user_messages"
    __table_args__ = (
        Index("idx_user_messages_conversation", "conversation_id", "created_at"),
        Index("idx_user_messages_unread", "conversation_id", "read_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("user_conversations.id", ondelete="CASCADE")
    )
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attachment_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    message_type: Mapped[str] = mapped_column(String(32), default="text")
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    conversation: Mapped["UserConversation"] = relationship(back_populates="messages")


class UserBlock(Base):
    __tablename__ = "user_blocks"
    __table_args__ = (
        Index("idx_user_blocks_unique_pair", "blocker_user_id", "blocked_user_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    blocker_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    blocked_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserReport(Base):
    __tablename__ = "user_reports"
    __table_args__ = (
        Index("idx_user_reports_reported_user", "reported_user_id", "status"),
        Index("idx_user_reports_reporter_user", "reporter_user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reported_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    conversation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user_conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    property_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("properties.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason: Mapped[str] = mapped_column(String(32), default="other")
    status: Mapped[str] = mapped_column(String(32), default="open")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )


class AppCatalog(Base):
    __tablename__ = "app_catalogs"
    __table_args__ = (
        Index("idx_app_catalogs_key", "key", unique=True),
        Index("idx_app_catalogs_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )


class MatchQnAAnswer(Base):
    __tablename__ = "match_qna_answers"
    __table_args__ = (
        Index("idx_match_qna_match", "match_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("user_matches.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    q1: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    q2: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    q3: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
