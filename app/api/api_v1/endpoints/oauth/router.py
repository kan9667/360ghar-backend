from __future__ import annotations

from fastapi import APIRouter

from .authorization import auth_router
from .discovery import mcp_discovery_router, wellknown_router
from .registration import registration_router
from .token import token_router

# Main router — mounted under /api/v1 in api.py
router = APIRouter()
router.include_router(auth_router)
router.include_router(token_router)
router.include_router(registration_router)

# Separate router for well-known endpoints that need to be mounted at root level.
# MCP clients expect these at /.well-known/... not /api/v1/.well-known/...
oauth_wellknown_router = APIRouter()
oauth_wellknown_router.include_router(wellknown_router)

# Router for MCP OAuth endpoints at root level (/mcp/oauth/*).
oauth_mcp_router = APIRouter()
oauth_mcp_router.include_router(auth_router)
oauth_mcp_router.include_router(token_router)
oauth_mcp_router.include_router(registration_router)
oauth_mcp_router.include_router(mcp_discovery_router)
