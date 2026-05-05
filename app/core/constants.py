"""
Application-wide constants.

Values are sourced from settings (env vars) with hardcoded fallbacks so that
a single source of truth is available for models, providers, and other defaults
that must not drift across modules.
"""

from app.core.config import settings

# Valid vision provider identifiers
VALID_VISION_PROVIDERS: tuple[str, ...] = ("gemini", "glm")


def __getattr__(name: str):
    """Lazily resolve constants from settings to avoid stale import-time values."""
    _LAZY_CONSTANTS = {
        "DEFAULT_VISION_MODEL_GEMINI": lambda: settings.GEMINI_MODEL or "gemini-3-flash-preview",
        "DEFAULT_VISION_MODEL_GLM": lambda: settings.GLM_MODEL or "glm-4.6v-flash",
        "DEFAULT_VISION_PROVIDER": lambda: settings.VASTU_DEFAULT_PROVIDER or "glm",
        "VASTU_FALLBACK_PROVIDER": lambda: settings.VASTU_FALLBACK_PROVIDER or "",
    }
    if name in _LAZY_CONSTANTS:
        return _LAZY_CONSTANTS[name]()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
