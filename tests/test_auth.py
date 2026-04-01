"""
Tests for AOS Gateway — Authentication Middleware
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from aos.gateway.auth import verify_token


class TestVerifyToken:
    """Test Bearer token authentication."""

    @pytest.mark.asyncio
    async def test_auth_disabled_when_no_api_key(self):
        """When AOS_API_KEY is None, auth should be skipped entirely."""
        mock_settings = MagicMock()
        mock_settings.aos_api_key = None
        with patch("aos.core.auth.get_settings", return_value=mock_settings):
            result = await verify_token(authorization=None)
            assert result is None  # No exception = pass

    @pytest.mark.asyncio
    async def test_valid_token_passes(self):
        mock_settings = MagicMock()
        mock_settings.aos_api_key = "test-key"
        with patch("aos.core.auth.get_settings", return_value=mock_settings):
            result = await verify_token(authorization="Bearer test-key")
            assert result is None

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        mock_settings = MagicMock()
        mock_settings.aos_api_key = "test-key"
        with patch("aos.core.auth.get_settings", return_value=mock_settings):
            with pytest.raises(HTTPException) as exc_info:
                await verify_token(authorization="Bearer wrong-key")
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_token_raises_401(self):
        mock_settings = MagicMock()
        mock_settings.aos_api_key = "test-key"
        with patch("aos.core.auth.get_settings", return_value=mock_settings):
            with pytest.raises(HTTPException) as exc_info:
                await verify_token(authorization=None)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_token_raises_401(self):
        mock_settings = MagicMock()
        mock_settings.aos_api_key = "test-key"
        with patch("aos.core.auth.get_settings", return_value=mock_settings):
            with pytest.raises(HTTPException) as exc_info:
                await verify_token(authorization="test-key")  # Missing "Bearer " prefix
            assert exc_info.value.status_code == 401
