"""
Regression guard for HTTP method aliases on tour/scene endpoints.

Wave 1 added method aliases so the frontend can use either verb:
- PATCH + PUT  /api/v1/tours/{tour_id}        (update_tour)
- PATCH + PUT  /api/v1/scenes/{scene_id}      (update_scene)
- POST  + PUT  /api/v1/tours/{tour_id}/scenes/reorder (reorder_scenes)

These tests inspect the app route table (cheap, no DB required) and run a
request-level smoke test with the service layer mocked to ensure routing and
request validation accept a partial PATCH body.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.factory import create_app


def _methods_by_path(app) -> dict[str, set[str]]:
    """Collect the union of HTTP methods registered for each route path."""
    methods: dict[str, set[str]] = {}
    for route in app.routes:
        if isinstance(route, APIRoute):
            methods.setdefault(route.path, set()).update(route.methods or set())
    return methods


@pytest.fixture(scope="module")
def route_methods() -> dict[str, set[str]]:
    return _methods_by_path(create_app(testing=True))


# =============================================================================
# Route-table contract
# =============================================================================

def test_update_tour_supports_patch_and_put(route_methods):
    methods = route_methods.get("/api/v1/tours/{tour_id}", set())
    assert "PATCH" in methods, "PATCH /api/v1/tours/{tour_id} alias is missing"
    assert "PUT" in methods, "PUT /api/v1/tours/{tour_id} is missing"


def test_update_scene_supports_patch_and_put(route_methods):
    methods = route_methods.get("/api/v1/scenes/{scene_id}", set())
    assert "PATCH" in methods, "PATCH /api/v1/scenes/{scene_id} alias is missing"
    assert "PUT" in methods, "PUT /api/v1/scenes/{scene_id} is missing"


def test_reorder_scenes_supports_post_and_put(route_methods):
    methods = route_methods.get("/api/v1/tours/{tour_id}/scenes/reorder", set())
    assert "POST" in methods, "POST /api/v1/tours/{tour_id}/scenes/reorder is missing"
    assert "PUT" in methods, "PUT /api/v1/tours/{tour_id}/scenes/reorder alias is missing"


def test_create_scene_route_is_not_shadowed(route_methods):
    """POST /tours/{tour_id}/scenes (scene creation) must remain a distinct route."""
    methods = route_methods.get("/api/v1/tours/{tour_id}/scenes", set())
    assert "POST" in methods, "POST /api/v1/tours/{tour_id}/scenes (create_scene) is missing"
    assert "GET" in methods, "GET /api/v1/tours/{tour_id}/scenes (list_scenes) is missing"


# =============================================================================
# Request-level smoke test (routing + validation only; service layer mocked)
# =============================================================================

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

_TOUR_PAYLOAD = {
    "id": "tour-123",
    "user_id": 1,
    "title": "Updated Title",
    "description": None,
    "status": "draft",
    "is_public": False,
    "visibility": "private",
    "is_featured": False,
    "view_count": 0,
    "like_count": 0,
    "share_count": 0,
    "thumbnail_url": None,
    "published_at": None,
    "archived_at": None,
    "created_at": _NOW,
    "updated_at": _NOW,
    "deleted_at": None,
    "scenes": None,
    "scene_count": 0,
}


@pytest.fixture
def aliased_client():
    """TestClient with auth + db overridden and tour service update mocked."""
    from app.api.api_v1.dependencies.auth import get_current_active_user
    from app.core.database import get_db
    from app.schemas.user import User as UserSchema

    app = create_app(testing=True)

    user = UserSchema(
        id=1,
        supabase_user_id="00000000-0000-0000-0000-000000000001",
        role="user",
        is_active=True,
        is_verified=True,
        created_at=_NOW,
    )

    app.dependency_overrides[get_current_active_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.parametrize("method", ["patch", "put"])
def test_update_tour_partial_body_routes_and_validates(aliased_client, method):
    """A partial body must not 405 (method missing) or 422 (validation)."""
    with patch(
        "app.services.tour.update_tour",
        new=AsyncMock(return_value=_TOUR_PAYLOAD),
    ) as mock_update:
        response = getattr(aliased_client, method)(
            "/api/v1/tours/tour-123",
            json={"title": "Updated Title"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Updated Title"
    mock_update.assert_awaited_once()
