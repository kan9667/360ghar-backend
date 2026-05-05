"""Shared imports for Admin MCP agent sub-modules."""

from app.core.logging import get_logger
from app.core.utils import make_tz_aware, utc_now, utc_now_iso
from app.mcp.apps_sdk import AuthRequiredError, MCP_SECURITY_SCHEMES_MIXED
from app.mcp.errors import (
    MCPErrorCode,
    MCPResponse,
    internal_error_response,
    invalid_input_response,
    not_found_response,
)
from app.mcp.utils import (
    get_db,
    get_user_role,
    serialize_property_basic,
    serialize_property_full,
    serialize_booking,
    serialize_lease,
    serialize_maintenance_request,
    serialize_user_basic,
)
from app.mcp.admin.server import admin_mcp, _get_user, _require_auth, _require_agent_or_admin

logger = get_logger(__name__)
