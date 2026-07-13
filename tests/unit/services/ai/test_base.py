from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.ai.base import (
    AIProvider,
    AIProviderConfig,
    AIProviderError,
    _is_hard_quota,
    _is_retryable_error,
    _parse_retry_after_seconds,
    clear_provider_cooldowns,
)


@pytest.fixture(autouse=True)
def _clear_cooldowns():
    """Prevent hard-quota cooldown state from leaking across tests, even on failure."""
    clear_provider_cooldowns()
    try:
        yield
    finally:
        clear_provider_cooldowns()


class _DummyProvider(AIProvider):
    @property
    def name(self) -> str:
        return "dummy"

    @property
    def supports_vision(self) -> bool:
        return False

    @property
    def supports_json_mode(self) -> bool:
        return True

    async def complete(self, messages, vision_input=None) -> str:
        raise NotImplementedError

    async def complete_json(self, messages, vision_input=None, json_schema=None):
        raise NotImplementedError


def test_parse_json_response_recovers_nested_object_from_wrapped_text():
    provider = _DummyProvider(AIProviderConfig(api_key="test", model="dummy"))

    result = provider._parse_json_response(
        'prefix {"floor_plan_analysis": {"rooms": [{"name": "Kitchen"}]}, "vastu_score": 8} suffix'
    )

    assert result["floor_plan_analysis"]["rooms"][0]["name"] == "Kitchen"
    assert result["vastu_score"] == 8


class TestRetryAfterParsing:
    def test_retry_in_seconds_from_gemini_body(self):
        body = (
            'You exceeded your current quota... Please retry in 11.29336209s. '
            'Quota exceeded for metric: ... free_tier_requests'
        )
        assert _parse_retry_after_seconds({}, body) == pytest.approx(11.29336209)

    def test_retry_after_header(self):
        assert _parse_retry_after_seconds({"Retry-After": "30"}, "") == 30.0

    def test_glm_five_hour_window(self):
        body = (
            '{"error":{"code":"1308","message":'
            '"Usage limit reached for 5 hour. Your limit will reset at 2026-07-11 04:46:29"}}'
        )
        delay = _parse_retry_after_seconds({}, body)
        assert delay is not None
        assert delay >= 60

    def test_glm_prefers_hours_window_over_reset_timestamp(self):
        # The hours window has no timezone ambiguity; always prefer it over
        # the naive "reset at" timestamp when both are present.
        body = (
            "Usage limit reached for 5 hour. "
            "Your limit will reset at 2099-01-01 00:00:00"
        )
        delay = _parse_retry_after_seconds({}, body)
        assert delay == pytest.approx(5 * 3600.0)

    def test_glm_hours_window_wins_over_sooner_reset_timestamp(self):
        # A TZ-skewed "reset at" timestamp that lands sooner than the stated
        # window must not shorten the trusted, unambiguous window.
        reset_soon = (datetime.now() + timedelta(minutes=90)).strftime("%Y-%m-%d %H:%M:%S")
        body = f"Usage limit reached for 5 hour. Your limit will reset at {reset_soon}"
        delay = _parse_retry_after_seconds({}, body)
        assert delay == pytest.approx(5 * 3600.0)


class TestHardQuotaClassification:
    def test_glm_usage_limit_is_hard(self):
        body = "Usage limit reached for 5 hour. Your limit will reset at 2026-07-11 04:46:29"
        assert _is_hard_quota(429, 5 * 3600, body) is True

    def test_gemini_free_tier_is_hard(self):
        body = (
            "You exceeded your current quota... free_tier_requests "
            "RESOURCE_EXHAUSTED Please retry in 11.29s."
        )
        assert _is_hard_quota(429, 11.29, body) is True

    def test_503_is_not_hard_quota(self):
        body = "This model is currently experiencing high demand."
        assert _is_hard_quota(503, None, body) is False

    def test_short_429_without_quota_signals_not_hard(self):
        # Generic rate limit with short delay stays soft/retryable.
        assert _is_hard_quota(429, 5.0, "Too many requests, slow down") is False


class TestIsRetryableError:
    def test_hard_quota_error_not_retryable(self):
        exc = AIProviderError(
            message="Hard quota",
            provider="glm",
            status_code=429,
            retryable=False,
        )
        assert _is_retryable_error(exc) is False

    def test_soft_429_is_retryable(self):
        exc = AIProviderError(
            message="Retryable HTTP 429",
            provider="gemini",
            status_code=429,
            retryable=True,
        )
        assert _is_retryable_error(exc) is True

    def test_503_is_retryable(self):
        exc = AIProviderError(
            message="Retryable HTTP 503",
            provider="gemini",
            status_code=503,
            retryable=True,
        )
        assert _is_retryable_error(exc) is True


@pytest.mark.asyncio
async def test_make_request_fail_fast_on_hard_quota():
    provider = _DummyProvider(AIProviderConfig(api_key="test", model="dummy"))

    glm_body = (
        '{"error":{"code":"1308","message":'
        '"Usage limit reached for 5 hour. Your limit will reset at 2026-07-11 20:04:36"}}'
    )
    response = MagicMock(spec=httpx.Response)
    response.status_code = 429
    response.text = glm_body
    response.headers = httpx.Headers({})

    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=response)

    with pytest.raises(AIProviderError) as exc_info:
        await provider._make_request(client, "https://example.com", {}, {})

    assert exc_info.value.status_code == 429
    assert exc_info.value.retryable is False
    # Fail-fast: only one HTTP call (no tenacity thrash)
    assert client.post.await_count == 1

    # Cooldown blocks subsequent calls without hitting the network
    client.post.reset_mock()
    with pytest.raises(AIProviderError) as cooled:
        await provider._make_request(client, "https://example.com", {}, {})
    assert cooled.value.retryable is False
    assert client.post.await_count == 0


@pytest.mark.asyncio
async def test_make_request_retries_soft_503():
    provider = _DummyProvider(AIProviderConfig(api_key="test", model="dummy"))

    fail = MagicMock(spec=httpx.Response)
    fail.status_code = 503
    fail.text = "high demand"
    fail.headers = httpx.Headers({})

    ok = MagicMock(spec=httpx.Response)
    ok.status_code = 200
    ok.text = "{}"
    ok.headers = httpx.Headers({})

    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=[fail, ok])

    result = await provider._make_request(client, "https://example.com", {}, {})
    assert result.status_code == 200
    assert client.post.await_count == 2
