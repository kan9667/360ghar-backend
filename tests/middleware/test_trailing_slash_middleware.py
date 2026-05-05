from __future__ import annotations

import pytest

from app.middleware.trailing_slash import MCP_MOUNT_PATHS, StripTrailingSlashMiddleware


async def _run_with_path(path: str, scope_type: str = "http") -> str:
    captured_path = {"value": ""}

    async def app(scope, receive, send):
        captured_path["value"] = scope["path"]

    middleware = StripTrailingSlashMiddleware(app)
    scope = {
        "type": scope_type,
        "path": path,
    }

    async def _receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def _send(_message):
        return None

    await middleware(scope, _receive, _send)
    return captured_path["value"]


class TestMCPMountPaths:
    """Tests for MCP mount path constants."""

    def test_mcp_mount_paths_do_not_include_sse(self):
        assert "/sse" not in MCP_MOUNT_PATHS
        assert MCP_MOUNT_PATHS == {"/mcp", "/mcp-admin"}


class TestTrailingSlashAddition:
    """Tests for adding trailing slashes to MCP mount paths."""

    @pytest.mark.asyncio
    async def test_adds_trailing_slash_for_mcp(self):
        assert await _run_with_path("/mcp") == "/mcp/"

    @pytest.mark.asyncio
    async def test_adds_trailing_slash_for_mcp_admin(self):
        assert await _run_with_path("/mcp-admin") == "/mcp-admin/"

    @pytest.mark.asyncio
    async def test_mcp_subpaths_unchanged(self):
        # /mcp/something should not become /mcp//something
        result = await _run_with_path("/mcp/something")
        assert result == "/mcp/something"


class TestTrailingSlashStripping:
    """Tests for stripping trailing slashes from API routes."""

    @pytest.mark.asyncio
    async def test_strips_trailing_slash_for_api_routes(self):
        assert await _run_with_path("/api/v1/properties/") == "/api/v1/properties"

    @pytest.mark.asyncio
    async def test_preserves_api_root(self):
        assert await _run_with_path("/api/") == "/api/"

    @pytest.mark.asyncio
    async def test_no_trailing_slash_unchanged(self):
        assert await _run_with_path("/api/v1/users") == "/api/v1/users"

    @pytest.mark.asyncio
    async def test_deep_api_path_stripped(self):
        assert await _run_with_path("/api/v1/properties/42/images/") == "/api/v1/properties/42/images"


class TestNonHTTPScopes:
    """Tests for non-HTTP scope types."""

    @pytest.mark.asyncio
    async def test_websocket_scope_unchanged(self):
        # WebSocket scopes should not be modified
        result = await _run_with_path("/api/v1/ws/", scope_type="websocket")
        assert result == "/api/v1/ws/"

    @pytest.mark.asyncio
    async def test_lifespan_scope_unchanged(self):
        result = await _run_with_path("/mcp", scope_type="lifespan")
        assert result == "/mcp"
