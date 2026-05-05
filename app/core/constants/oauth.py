"""OAuth 2.1 constants for token and code lifecycle."""

# Authorization code TTL (seconds)
AUTH_CODE_TTL: int = 600  # 10 minutes

# Access token TTL (seconds)
ACCESS_TOKEN_TTL: int = 3600  # 1 hour

# Refresh token TTL (seconds)
REFRESH_TOKEN_TTL: int = 2_592_000  # 30 days

# Device code TTL (seconds)
DEVICE_CODE_TTL: int = 1800  # 30 minutes

# Client registration cache TTL (seconds)
CLIENT_REGISTRATION_CACHE_TTL: int = 315_360_000  # 10 years
