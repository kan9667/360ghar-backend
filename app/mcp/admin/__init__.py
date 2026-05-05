"""
Admin MCP Server Package - For agents and administrators.

Re-exports the ``admin_mcp`` FastMCP instance for backward compatibility.
"""

from app.mcp.admin.server import admin_mcp

__all__ = ["admin_mcp"]
