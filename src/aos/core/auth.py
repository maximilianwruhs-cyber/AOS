"""
AOS Core — Authentication Middleware
Bearer Token auth with constant-time comparison.
Moved from gateway/auth.py to core/ as a cross-cutting concern.
"""
import hmac
from fastapi import Header, HTTPException

from aos.core.settings import get_settings


async def verify_token(authorization: str = Header(None)):
    """Bearer Token auth. Skipped if AOS_API_KEY is not set (dev mode)."""
    api_key = get_settings().aos_api_key
    if not api_key:
        return
    expected = f"Bearer {api_key}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
