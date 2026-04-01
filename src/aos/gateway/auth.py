"""
AOS Gateway — Auth (BACKWARD COMPATIBILITY SHIM)
Real implementation moved to aos.core.auth.
This file will be deleted in Phase 4 of the DDD migration.
"""
from aos.core.auth import verify_token  # noqa: F401

# Legacy import support
from aos.core.settings import get_settings as _get_settings
AOS_API_KEY = _get_settings().aos_api_key
