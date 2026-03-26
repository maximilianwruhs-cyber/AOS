"""
AOS — Centralized Configuration
All paths resolved relative to this file's location. Override via .env or environment variables.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv is optional; env vars still work

# ─── Paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
AGENTS_DIR = PROJECT_ROOT / "core_identity"
DATA_DIR = PROJECT_ROOT / "data"
TOOLS_DIR = PROJECT_ROOT / "src" / "tools"
DOCS_DIR = PROJECT_ROOT / "docs"

# Ensure data dir exists at runtime
DATA_DIR.mkdir(exist_ok=True)

# ─── Backend API ──────────────────────────────────────────────────────────────
# Pointing to LM Studio by default since the daemon uses LM Studio
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:1234/v1")
DEFAULT_MODEL = os.getenv("AOS_MODEL", "qwen2.5-coder-1.5b-instruct")

# ─── Arena Defaults ───────────────────────────────────────────────────────────
TOTAL_TOKENS_PER_ROUND = int(os.getenv("AOS_TOKENS_PER_ROUND", "2048"))
INITIAL_AGENT_BALANCE = float(os.getenv("AOS_INITIAL_BALANCE", "100.0"))
