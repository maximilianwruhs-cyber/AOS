"""
AOS Test Suite — Shared Fixtures
Provides isolated mock objects for all test modules.
"""
import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def isolate_filesystem(tmp_path, monkeypatch):
    """Prevent tests from touching real filesystem paths."""
    monkeypatch.setenv("AOS_VAULT_PATH", str(tmp_path / "vault"))
    monkeypatch.setenv("AOS_DATA_DIR", str(tmp_path / "data"))
