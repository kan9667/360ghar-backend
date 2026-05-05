"""Application-wide size and dimension limits."""

# Image processing limits
THUMBNAIL_MAX_SIZE_PX: int = 512
WEBP_MAX_DIMENSION_PX: int = 4096

# FCM token refresh buffer (seconds before actual expiry)
FCM_TOKEN_REFRESH_BUFFER_SECONDS: int = 300  # 5 minutes
