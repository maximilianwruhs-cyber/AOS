"""
AOS Core — Path Constants
All filesystem paths resolved relative to the project root.
This module has ZERO business logic — purely structural.
"""
from pathlib import Path

# settings.py lives at src/aos/core/paths.py → parents[3] = AOS/ (project root)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
AGENTS_DIR = PROJECT_ROOT / "core_identity"
DATA_DIR = PROJECT_ROOT / "data"
TOOLS_DIR = PROJECT_ROOT / "src" / "aos" / "tools"
DOCS_DIR = PROJECT_ROOT / "docs"
CONFIG_DIR = PROJECT_ROOT / "config"
REMOTE_HOSTS_FILE = CONFIG_DIR / "remote_hosts.json"

# Ensure data dir exists at import time
DATA_DIR.mkdir(exist_ok=True)
