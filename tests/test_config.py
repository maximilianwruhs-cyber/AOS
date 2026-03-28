"""
Tests for AOS Config — Path resolution and host management
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from aos.config import PROJECT_ROOT, CONFIG_DIR, REMOTE_HOSTS_FILE
from aos.config import load_remote_hosts, switch_active_host, list_hosts


class TestConfigPaths:
    """Verify path constants resolve correctly."""

    def test_project_root_is_aos_directory(self):
        assert PROJECT_ROOT.name == "AOS"
        assert PROJECT_ROOT.is_dir()

    def test_config_dir_exists(self):
        assert CONFIG_DIR == PROJECT_ROOT / "config"
        assert CONFIG_DIR.is_dir()

    def test_remote_hosts_file_exists(self):
        assert REMOTE_HOSTS_FILE.exists()
        assert REMOTE_HOSTS_FILE.name == "remote_hosts.json"


class TestRemoteHosts:
    """Test host loading, switching, and listing."""

    def test_load_remote_hosts_returns_tuple(self):
        url, fallback, key = load_remote_hosts()
        assert isinstance(url, str)
        assert url.startswith("http")
        assert isinstance(key, str)

    def test_list_hosts_returns_dict(self):
        hosts, active = list_hosts()
        assert isinstance(hosts, dict)
        assert "local" in hosts

    def test_switch_to_unknown_host_returns_false(self):
        result = switch_active_host("nonexistent-host-xyz")
        assert result is False

    def test_switch_and_restore(self):
        """Switch to a known host and restore the original."""
        _, _, original_key = load_remote_hosts()
        try:
            # Switch to a different known host
            hosts, _ = list_hosts()
            other_keys = [k for k in hosts if k != original_key]
            if other_keys:
                assert switch_active_host(other_keys[0]) is True
                _, _, new_key = load_remote_hosts()
                assert new_key == other_keys[0]
        finally:
            # Always restore
            switch_active_host(original_key)
