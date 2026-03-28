"""
AOS Gateway — Authentication Middleware
Bearer Token auth with constant-time comparison.
"""
import hmac
from fastapi import Header, HTTPException

from aos.config import AOS_API_KEY


async def verify_token(authorization: str = Header(None)):
    """Bearer Token auth. Skipped if AOS_API_KEY is not set (dev mode)."""
    if not AOS_API_KEY:
        return
    expected = f"Bearer {AOS_API_KEY}"
    # FIX #47: constant-time compare to prevent timing attacks
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
