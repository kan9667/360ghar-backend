from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.api_v1.endpoints import auth
from app.core.auth import AuthFailureReason, _make_failure
from app.core.exceptions import BadRequestException, ServiceUnavailableException


def _request() -> MagicMock:
    request = MagicMock()
    request.method = "POST"
    request.url.path = "/api/v1/auth/link-identity"
    request.client.host = "127.0.0.1"
    request.headers = {}
    return request


@pytest.mark.asyncio
async def test_link_identity_provider_unreachable_is_503() -> None:
    current_user = SimpleNamespace(supabase_user_id="sid-1")
    body = auth.LinkIdentityRequest(provider="google", id_token="tok")

    with patch(
        "app.api.api_v1.endpoints.auth._auth_mutation_limiter.check_rate_limit",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.api.api_v1.endpoints.auth.admin_link_identity",
        new=AsyncMock(
            return_value=_make_failure(
                AuthFailureReason.PROVIDER_UNREACHABLE,
                "dns fail",
            )
        ),
    ):
        with pytest.raises(ServiceUnavailableException) as exc_info:
            await auth.link_identity(
                request=_request(), body=body, current_user=current_user
            )

    assert "temporarily unreachable" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_link_identity_provider_error_is_400_with_distinct_message() -> None:
    current_user = SimpleNamespace(supabase_user_id="sid-1")
    body = auth.LinkIdentityRequest(provider="google", id_token="tok")

    with patch(
        "app.api.api_v1.endpoints.auth._auth_mutation_limiter.check_rate_limit",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.api.api_v1.endpoints.auth.admin_link_identity",
        new=AsyncMock(
            return_value=_make_failure(
                AuthFailureReason.PROVIDER_ERROR,
                "already linked",
            )
        ),
    ):
        with pytest.raises(BadRequestException) as exc_info:
            await auth.link_identity(
                request=_request(), body=body, current_user=current_user
            )

    detail = str(exc_info.value.detail)
    assert "temporarily unreachable" not in detail
    assert "already be linked" in detail


@pytest.mark.asyncio
async def test_link_identity_false_is_400_with_distinct_message() -> None:
    current_user = SimpleNamespace(supabase_user_id="sid-1")
    body = auth.LinkIdentityRequest(provider="google", id_token="tok")

    with patch(
        "app.api.api_v1.endpoints.auth._auth_mutation_limiter.check_rate_limit",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.api.api_v1.endpoints.auth.admin_link_identity",
        new=AsyncMock(return_value=False),
    ):
        with pytest.raises(BadRequestException) as exc_info:
            await auth.link_identity(
                request=_request(), body=body, current_user=current_user
            )

    detail = str(exc_info.value.detail)
    assert "temporarily unreachable" not in detail
    assert "already be linked" in detail


@pytest.mark.asyncio
async def test_link_identity_success() -> None:
    current_user = SimpleNamespace(supabase_user_id="sid-1")
    body = auth.LinkIdentityRequest(provider="google", id_token="tok")

    with patch(
        "app.api.api_v1.endpoints.auth._auth_mutation_limiter.check_rate_limit",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.api.api_v1.endpoints.auth.admin_link_identity",
        new=AsyncMock(return_value=True),
    ):
        result = await auth.link_identity(
            request=_request(), body=body, current_user=current_user
        )

    assert result.linked is True
