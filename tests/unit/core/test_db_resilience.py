from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.db_resilience import (
    execute_with_transient_retry,
    extract_db_error_code,
    is_transient_db_error,
)


@pytest.mark.asyncio
async def test_execute_with_transient_retry_succeeds_on_second_attempt() -> None:
    session = AsyncMock()
    attempts = {"count": 0}

    async def flaky_operation():
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise Exception("(EDBHANDLEREXITED) connection to database closed")
        return "ok"

    result = await execute_with_transient_retry(
        session,
        flaky_operation,
        operation_name="unit_test_transient_retry",
    )

    assert result == "ok"
    assert attempts["count"] == 2
    session.rollback.assert_awaited()
    session.invalidate.assert_awaited()


@pytest.mark.asyncio
async def test_execute_with_transient_retry_does_not_retry_non_transient() -> None:
    session = AsyncMock()
    operation = AsyncMock(side_effect=SQLAlchemyError("syntax error near FROM"))

    with pytest.raises(SQLAlchemyError):
        await execute_with_transient_retry(
            session,
            operation,
            operation_name="unit_test_non_transient",
        )

    assert operation.await_count == 1
    session.rollback.assert_not_awaited()
    session.invalidate.assert_not_awaited()


def test_transient_db_error_detection_and_code_extraction() -> None:
    exc = Exception("(ECHECKOUTTIMEOUT) unable to check out connection from the pool")
    assert is_transient_db_error(exc) is True
    assert extract_db_error_code(exc) == "ECHECKOUTTIMEOUT"
