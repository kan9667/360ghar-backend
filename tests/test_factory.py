from app.factory import create_app
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security import RequestIDMiddleware, SecurityHeadersMiddleware


def test_create_app_testing_mode_skips_rate_limit_middleware() -> None:
    app = create_app(testing=True)

    middleware_classes = {m.cls for m in app.user_middleware}
    assert RateLimitMiddleware not in middleware_classes
    assert SecurityHeadersMiddleware in middleware_classes
    assert RequestIDMiddleware in middleware_classes


def test_create_app_mounts_mcp() -> None:
    app = create_app(testing=True)

    assert any(getattr(r, "path", None) == "/mcp" for r in app.routes)

