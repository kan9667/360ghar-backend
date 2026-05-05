"""OAuth endpoints package — re-exports routers and helpers for backward compatibility."""

from .helpers import (
    CHATGPT_REDIRECT_PREFIXES,
    CHATGPT_REDIRECT_URIS,
    OAUTH_ACCESS_TOKEN_LIFETIME,
    OAUTH_AUTHORIZATION_CODE_LIFETIME,
    OAUTH_REFRESH_TOKEN_LIFETIME,
    OAuthAuthorizeRequest,
    OAuthTokenRequest,
    fetch_client_metadata,
    generate_access_token,
    generate_auth_code,
    generate_refresh_token,
    is_loopback_redirect_uri,
    is_redirect_uri_allowed_for_client,
    render_consent_html,
    validate_client,
)
from .pkce import verify_pkce
from .registration import ClientRegistrationRequest
from .router import oauth_mcp_router, oauth_wellknown_router, router

__all__ = [
    # Routers
    "router",
    "oauth_mcp_router",
    "oauth_wellknown_router",
    # Constants
    "OAUTH_AUTHORIZATION_CODE_LIFETIME",
    "OAUTH_ACCESS_TOKEN_LIFETIME",
    "OAUTH_REFRESH_TOKEN_LIFETIME",
    "CHATGPT_REDIRECT_URIS",
    "CHATGPT_REDIRECT_PREFIXES",
    # Schemas
    "OAuthAuthorizeRequest",
    "OAuthTokenRequest",
    "ClientRegistrationRequest",
    # Helpers
    "generate_auth_code",
    "generate_access_token",
    "generate_refresh_token",
    "is_loopback_redirect_uri",
    "is_redirect_uri_allowed_for_client",
    "render_consent_html",
    "fetch_client_metadata",
    "validate_client",
    # PKCE
    "verify_pkce",
]
