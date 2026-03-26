"""
Obolus — Centralized Configuration
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
PROJECT_ROOT = Path(__file__).parent.resolve()
AGENTS_DIR = PROJECT_ROOT / "agents"
DATA_DIR = PROJECT_ROOT / "data"
TOOLS_DIR = PROJECT_ROOT / "tools"
DOCS_DIR = PROJECT_ROOT / "docs"

# Ensure data dir exists at runtime
DATA_DIR.mkdir(exist_ok=True)

# ─── Ollama ───────────────────────────────────────────────────────────────────
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OBULUS_MODEL", "llama3:latest")

# ─── Arena Defaults ───────────────────────────────────────────────────────────
TOTAL_TOKENS_PER_ROUND = int(os.getenv("OBULUS_TOKENS_PER_ROUND", "2048"))
INITIAL_AGENT_BALANCE = float(os.getenv("OBULUS_INITIAL_BALANCE", "100.0"))
