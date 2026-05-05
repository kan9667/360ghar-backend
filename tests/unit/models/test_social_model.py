"""
Tests for app.models.social module — UserMatch, UserConversation, UserMessage, etc.
"""

import pytest

from app.models.social import (
    AppCatalog,
    MatchQnAAnswer,
    UserBlock,
    UserConversation,
    UserMessage,
    UserMatch,
    UserReport,
)


class TestUserMatchModel:
    """Tests for UserMatch model."""

    def test_tablename(self):
        assert UserMatch.__tablename__ == "user_matches"

    def test_default_status(self):
        assert UserMatch.status.default.arg == "active"

    def test_has_required_columns(self):
        columns = {c.name for c in UserMatch.__table__.columns}
        assert {"user_one_id", "user_two_id", "status"}.issubset(columns)


class TestUserConversationModel:
    """Tests for UserConversation model."""

    def test_tablename(self):
        assert UserConversation.__tablename__ == "user_conversations"

    def test_default_source(self):
        assert UserConversation.source.default.arg == "listing_interest"

    def test_default_status(self):
        assert UserConversation.status.default.arg == "active"

    def test_has_required_columns(self):
        columns = {c.name for c in UserConversation.__table__.columns}
        assert {"user_one_id", "user_two_id", "created_by_user_id", "source", "status"}.issubset(columns)


class TestUserMessageModel:
    """Tests for UserMessage model."""

    def test_tablename(self):
        assert UserMessage.__tablename__ == "user_messages"

    def test_default_message_type(self):
        assert UserMessage.message_type.default.arg == "text"

    def test_has_required_columns(self):
        columns = {c.name for c in UserMessage.__table__.columns}
        assert {"conversation_id", "sender_id", "body", "message_type"}.issubset(columns)


class TestUserBlockModel:
    """Tests for UserBlock model."""

    def test_tablename(self):
        assert UserBlock.__tablename__ == "user_blocks"

    def test_has_required_columns(self):
        columns = {c.name for c in UserBlock.__table__.columns}
        assert {"blocker_user_id", "blocked_user_id"}.issubset(columns)


class TestUserReportModel:
    """Tests for UserReport model."""

    def test_tablename(self):
        assert UserReport.__tablename__ == "user_reports"

    def test_default_reason(self):
        assert UserReport.reason.default.arg == "other"

    def test_default_status(self):
        assert UserReport.status.default.arg == "open"

    def test_has_required_columns(self):
        columns = {c.name for c in UserReport.__table__.columns}
        assert {"reporter_user_id", "reported_user_id", "reason", "status"}.issubset(columns)


class TestAppCatalogModel:
    """Tests for AppCatalog model."""

    def test_tablename(self):
        assert AppCatalog.__tablename__ == "app_catalogs"

    def test_default_version(self):
        assert AppCatalog.version.default.arg == 1

    def test_default_is_active(self):
        assert AppCatalog.is_active.default.arg is True


class TestMatchQnAAnswerModel:
    """Tests for MatchQnAAnswer model."""

    def test_tablename(self):
        assert MatchQnAAnswer.__tablename__ == "match_qna_answers"

    def test_has_required_columns(self):
        columns = {c.name for c in MatchQnAAnswer.__table__.columns}
        assert {"match_id", "user_id", "q1", "q2", "q3"}.issubset(columns)
