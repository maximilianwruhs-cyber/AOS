"""
AOS Core — Shared Kernel
Exports: Settings, paths, auth, and interface protocols.
All cross-feature concerns live here.
"""
from aos.core.settings import Settings, get_settings
from aos.core.paths import PROJECT_ROOT, DATA_DIR, CONFIG_DIR, TOOLS_DIR, DOCS_DIR, AGENTS_DIR
from aos.core.auth import verify_token

__all__ = [
    "Settings",
    "get_settings",
    "PROJECT_ROOT",
    "DATA_DIR",
    "CONFIG_DIR",
    "TOOLS_DIR",
    "DOCS_DIR",
    "AGENTS_DIR",
    "verify_token",
]
