import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.cache import cache_manager
from app.core.config import settings
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security import RequestIDMiddleware, SecurityHeadersMiddleware


def test_request_id_middleware_generates_and_echoes_request_id() -> None:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    client = TestClient(app)

    r1 = client.get("/ping")
    assert r1.status_code == 200
    request_id = r1.headers.get("X-Request-ID")
    assert request_id
    uuid.UUID(request_id)  # raises ValueError if invalid

    r2 = client.get("/ping", headers={"X-Request-ID": "test-request-id"})
    assert r2.status_code == 200
    assert r2.headers.get("X-Request-ID") == "test-request-id"


def test_security_headers_middleware_applies_expected_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    client = TestClient(app)

    monkeypatch.setattr(settings, "ENVIRONMENT", "development", raising=False)
    r = client.get("/ping")
    assert r.status_code == 200
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-XSS-Protection"] == "1; mode=block"
    assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Strict-Transport-Security" not in r.headers
    assert "Content-Security-Policy" not in r.headers

    monkeypatch.setattr(settings, "ENVIRONMENT", "production", raising=False)
    r_prod = client.get("/ping")
    assert r_prod.status_code == 200
    assert "Strict-Transport-Security" in r_prod.headers
    assert "Content-Security-Policy" in r_prod.headers


def test_rate_limit_middleware_enforces_limits_in_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    RateLimitMiddleware._memory_store = {}
    monkeypatch.setattr(cache_manager, "redis_client", None, raising=False)

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, calls=2, period=60, scope="test")

    @app.get("/limited")
    async def limited():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    client = TestClient(app)

    assert client.get("/limited").status_code == 200
    assert client.get("/limited").status_code == 200

    blocked = client.get("/limited")
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Rate limit exceeded"
    assert blocked.headers.get("Retry-After") == "60"
    assert blocked.headers.get("X-RateLimit-Limit") == "2"
    assert blocked.headers.get("X-RateLimit-Period") == "60"

    # Exempt endpoints should remain accessible
    for _ in range(5):
        assert client.get("/health").status_code == 200

