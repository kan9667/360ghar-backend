"""
Abstract base classes for AI provider integration.

This module provides a unified interface for different AI providers (Gemini, GLM, OpenAI, etc.)
enabling easy switching between providers and reuse across different AI-powered features.
"""

from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any

import httpx
from pydantic import BaseModel, Field
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# Retry configuration for AI provider HTTP requests
AI_MAX_RETRIES = 3
AI_RETRY_MIN_WAIT = 2  # seconds
AI_RETRY_MAX_WAIT = 8  # seconds

# Delays at or above this are treated as hard quota windows: fail fast to
# the next provider instead of burning short retries.
_HARD_QUOTA_THRESHOLD_SECONDS = 60.0

# HTTP status codes that are transient and worth retrying (when not hard-quota)
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# Process-local cooldown after hard quota so concurrent requests skip the
# exhausted provider instead of spamming logs for the rest of the window.
_provider_cooldown_until: dict[str, float] = {}

_RETRY_IN_SECONDS_RE = re.compile(
    r"(?:please\s+)?retry\s+in\s+(\d+(?:\.\d+)?)\s*s",
    re.IGNORECASE,
)
_RESET_AT_RE = re.compile(
    r"(?:limit will )?reset at\s+(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})",
    re.IGNORECASE,
)
_HOURS_WINDOW_RE = re.compile(
    r"usage limit reached for\s+(\d+(?:\.\d+)?)\s*hour",
    re.IGNORECASE,
)


def _parse_reset_at_delta_seconds(body: str) -> float | None:
    """Best-effort seconds until a 'reset at YYYY-MM-DD HH:MM:SS' timestamp."""
    reset_match = _RESET_AT_RE.search(body or "")
    if not reset_match:
        return None
    stamp = reset_match.group(1).replace("T", " ")
    try:
        reset_dt = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    # Providers emit naive wall-clock (often their region local time). Use
    # local now as a best-effort; prefer multi-hour window when both exist.
    delta = (reset_dt - datetime.now()).total_seconds()
    return delta if delta > 0 else None


def _parse_hours_window_seconds(body: str) -> float | None:
    """Parse 'Usage limit reached for N hour' into seconds."""
    hours_match = _HOURS_WINDOW_RE.search(body or "")
    if not hours_match:
        return None
    try:
        return max(0.0, float(hours_match.group(1)) * 3600.0)
    except (TypeError, ValueError):
        return None


def _parse_retry_after_seconds(headers: httpx.Headers | dict[str, str], body: str) -> float | None:
    """Extract a retry delay in seconds from headers and/or response body."""
    raw_header = None
    if hasattr(headers, "get"):
        raw_header = headers.get("Retry-After") or headers.get("retry-after")
    if raw_header:
        try:
            return max(0.0, float(raw_header))
        except (TypeError, ValueError):
            pass

    match = _RETRY_IN_SECONDS_RE.search(body or "")
    if match:
        try:
            return max(0.0, float(match.group(1)))
        except (TypeError, ValueError):
            pass

    # Prefer multi-hour usage window over naive "reset at" timestamps (TZ-ambiguous).
    # When both are present, take the shorter positive delay so we do not
    # over-cool beyond the actual reset when the window is an upper bound.
    hours_delay = _parse_hours_window_seconds(body)
    reset_delay = _parse_reset_at_delta_seconds(body)
    if hours_delay is not None and reset_delay is not None:
        return min(hours_delay, reset_delay)
    if hours_delay is not None:
        return hours_delay
    if reset_delay is not None:
        return reset_delay

    body_lower = (body or "").lower()
    if _body_signals_quota_exhaustion(body_lower):
        # Known long-window signals without a parseable duration.
        if "hour" in body_lower or "free_tier" in body_lower or "resource_exhausted" in body_lower:
            return _HARD_QUOTA_THRESHOLD_SECONDS

    return None


def _body_signals_quota_exhaustion(body_lower: str) -> bool:
    """Match Gemini/GLM phrasing for quota / usage exhaustion."""
    return (
        "usage limit reached" in body_lower
        or "quota exceeded" in body_lower
        or "exceeded your current quota" in body_lower
        or "resource_exhausted" in body_lower
        or "free_tier" in body_lower
    )


def _is_hard_quota(status_code: int, retry_after: float | None, body: str) -> bool:
    """True when the provider is in a long quota window — do not short-retry."""
    if status_code != 429:
        return False
    if retry_after is not None and retry_after >= _HARD_QUOTA_THRESHOLD_SECONDS:
        return True
    body_lower = (body or "").lower()
    if "usage limit reached" in body_lower:
        return True
    if _body_signals_quota_exhaustion(body_lower):
        # Free-tier / RESOURCE_EXHAUSTED: fail over instead of thrashing short
        # retries (Gemini often asks for 11–46s which exceeds our soft window).
        return True
    return False


def _set_provider_cooldown(provider_name: str, retry_after: float | None) -> None:
    """Record a process-local cooldown for an exhausted provider."""
    seconds = retry_after if retry_after is not None else _HARD_QUOTA_THRESHOLD_SECONDS
    # Cap cooldown bookkeeping so a bad parse cannot cool down for days.
    seconds = min(max(seconds, _HARD_QUOTA_THRESHOLD_SECONDS), 6 * 3600.0)
    _provider_cooldown_until[provider_name] = time.monotonic() + seconds
    logger.warning(
        "AI provider '%s' entering cooldown for %.0fs after hard quota",
        provider_name,
        seconds,
    )


def _check_provider_cooldown(provider_name: str) -> None:
    """Raise immediately if this provider is still in hard-quota cooldown."""
    until = _provider_cooldown_until.get(provider_name)
    if until is None:
        return
    remaining = until - time.monotonic()
    if remaining <= 0:
        _provider_cooldown_until.pop(provider_name, None)
        return
    raise AIProviderError(
        message=f"Provider in hard-quota cooldown; retry after {remaining:.0f}s",
        provider=provider_name,
        status_code=429,
        retryable=False,
        retry_after_seconds=remaining,
    )


def clear_provider_cooldowns() -> None:
    """Clear process-local cooldowns (for tests)."""
    _provider_cooldown_until.clear()


def _is_retryable_error(exc: BaseException) -> bool:
    """Determine if an exception is transient and worth retrying."""
    # All httpx network-level errors (TimeoutException, ConnectError,
    # SendError, ReceiveError, PoolTimeout, etc.) are transient
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, AIProviderError):
        if exc.retryable is False:
            return False
        if exc.status_code in _RETRYABLE_STATUS_CODES:
            return True
    return False


class AIRole(str, Enum):
    """Message roles for AI conversations."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class AIMessage(BaseModel):
    """A message in an AI conversation."""
    role: AIRole
    content: str


class VisionInput(BaseModel):
    """Input for vision-capable AI models."""
    image_base64: str = Field(..., description="Base64-encoded image data")
    mime_type: str = Field(..., description="Image MIME type (image/jpeg, image/png, image/webp)")


class AIProviderConfig(BaseModel):
    """Configuration for an AI provider."""
    api_key: str = Field(..., description="API key for the provider")
    model: str = Field(..., description="Model name/ID to use")
    max_tokens: int = Field(default=4000, description="Maximum tokens in response")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    timeout: int = Field(default=120, description="Request timeout in seconds")


class AIProvider(ABC):
    """
    Abstract base class for AI providers.

    All AI providers (Gemini, GLM, OpenAI, Anthropic, etc.) should implement this interface
    to ensure consistent behavior across the application.

    Example usage:
        provider = get_ai_provider(AIProviderType.GEMINI)
        response = await provider.complete(messages, vision_input)
    """

    def __init__(self, config: AIProviderConfig):
        self.config = config
        self._http_client: httpx.AsyncClient | None = None

    def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create the reusable HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=self.config.timeout,
                follow_redirects=True,
                limits=httpx.Limits(
                    max_connections=5,
                    max_keepalive_connections=2,
                    keepalive_expiry=60,
                ),
            )
        return self._http_client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def _make_request(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> httpx.Response:
        """
        Execute an HTTP POST with automatic retries for transient errors.

        Uses tenacity with exponential backoff. Retries on:
        - Network errors (timeout, connect, send, receive)
        - HTTP 500, 502, 503, 504
        - Short-lived HTTP 429 (rate spikes within the retry window)

        Does NOT retry on:
        - Auth errors (401, 403) or client errors (400)
        - Hard quota 429s (multi-hour usage limits / free-tier exhaustion)
          so callers can fail over to another provider immediately

        All exceptions are normalised to ``AIProviderError`` before
        propagating so callers only need to handle that single type.
        """
        _check_provider_cooldown(self.name)

        @retry(
            stop=stop_after_attempt(AI_MAX_RETRIES),
            wait=wait_exponential(
                multiplier=1,
                min=AI_RETRY_MIN_WAIT,
                max=AI_RETRY_MAX_WAIT,
            ),
            retry=retry_if_exception(_is_retryable_error),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        async def _do_post() -> httpx.Response:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code in _RETRYABLE_STATUS_CODES:
                body = response.text[:1000]
                retry_after = _parse_retry_after_seconds(response.headers, body)
                hard = _is_hard_quota(response.status_code, retry_after, body)
                if hard:
                    _set_provider_cooldown(self.name, retry_after)
                    raise AIProviderError(
                        message=f"Hard quota HTTP {response.status_code}: {body[:500]}",
                        provider=self.name,
                        status_code=response.status_code,
                        response_body=body,
                        retryable=False,
                        retry_after_seconds=retry_after,
                    )
                raise AIProviderError(
                    message=f"Retryable HTTP {response.status_code}: {body[:500]}",
                    provider=self.name,
                    status_code=response.status_code,
                    response_body=body,
                    retryable=True,
                    retry_after_seconds=retry_after,
                )

            if response.status_code >= 400:
                raise AIProviderError(
                    message=f"API request failed: {response.text[:500]}",
                    provider=self.name,
                    status_code=response.status_code,
                    response_body=response.text[:1000],
                    retryable=False,
                )

            return response

        try:
            return await _do_post()
        except AIProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise AIProviderError(
                message=f"Request timed out after {AI_MAX_RETRIES} attempts: {exc}",
                provider=self.name,
            ) from exc
        except httpx.RequestError as exc:
            raise AIProviderError(
                message=f"Request failed after {AI_MAX_RETRIES} attempts: {exc}",
                provider=self.name,
            ) from exc

    def _extract_balanced_json_object(self, text: str) -> str | None:
        """Return the first balanced JSON object embedded in text."""
        start = text.find("{")
        while start != -1:
            depth = 0
            in_string = False
            escape = False

            for index in range(start, len(text)):
                char = text[index]

                if in_string:
                    if escape:
                        escape = False
                    elif char == "\\":
                        escape = True
                    elif char == '"':
                        in_string = False
                    continue

                if char == '"':
                    in_string = True
                elif char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        return text[start : index + 1]

            start = text.find("{", start + 1)

        return None

    def _parse_json_response(self, text: str) -> dict[str, Any]:
        """Parse JSON from AI response text.

        Tries, in order:
        1. Direct ``json.loads``
        2. Extraction from markdown code fences (```json ... ```)
        3. The first balanced JSON object embedded in the text
        """
        try:
            return dict[str, Any](json.loads(text))
        except json.JSONDecodeError:
            pass

        # Markdown code block
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fence_match:
            try:
                return dict[str, Any](json.loads(fence_match.group(1).strip()))
            except json.JSONDecodeError:
                pass

        # First balanced-brace JSON object
        json_object = self._extract_balanced_json_object(text)
        if json_object:
            try:
                return dict[str, Any](json.loads(json_object))
            except json.JSONDecodeError:
                pass

        raise AIProviderError(
            message="Failed to parse JSON from response",
            provider=self.name,
            response_body=text[:1000],
        )

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the provider."""
        pass

    @property
    @abstractmethod
    def supports_vision(self) -> bool:
        """Whether this provider supports vision/image inputs."""
        pass

    @property
    @abstractmethod
    def supports_json_mode(self) -> bool:
        """Whether this provider supports structured JSON output mode."""
        pass

    @abstractmethod
    async def complete(
        self,
        messages: list[AIMessage],
        vision_input: VisionInput | None = None,
    ) -> str:
        """
        Generate a text completion from the AI model.

        Args:
            messages: List of conversation messages
            vision_input: Optional image input for vision models

        Returns:
            Generated text response

        Raises:
            AIProviderError: If the API call fails
        """
        pass

    @abstractmethod
    async def complete_json(
        self,
        messages: list[AIMessage],
        vision_input: VisionInput | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Generate a structured JSON completion from the AI model.

        Args:
            messages: List of conversation messages
            vision_input: Optional image input for vision models
            json_schema: Optional JSON schema for structured output

        Returns:
            Parsed JSON response as a dictionary

        Raises:
            AIProviderError: If the API call fails or JSON parsing fails
        """
        pass


class AIProviderError(Exception):
    """Base exception for AI provider errors."""

    def __init__(
        self,
        message: str,
        provider: str,
        status_code: int | None = None,
        response_body: str | None = None,
        retryable: bool | None = None,
        retry_after_seconds: float | None = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.response_body = response_body
        # None = infer from status_code for backward compatibility
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds

    def __str__(self) -> str:
        base = f"[{self.provider}] {super().__str__()}"
        if self.status_code:
            base += f" (status: {self.status_code})"
        return base
