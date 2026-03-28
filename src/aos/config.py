"""
AOS — Centralized Configuration
All paths resolved relative to this file's location. Override via .env or environment variables.
"""
import os
import json
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass  # python-dotenv is optional; env vars still work

# ─── Paths ────────────────────────────────────────────────────────────────────
# config.py lives at src/aos/config.py → parents[2] = AOS/ (project root)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = PROJECT_ROOT / "core_identity"
DATA_DIR = PROJECT_ROOT / "data"
TOOLS_DIR = PROJECT_ROOT / "src" / "aos" / "tools"
DOCS_DIR = PROJECT_ROOT / "docs"
CONFIG_DIR = PROJECT_ROOT / "config"
REMOTE_HOSTS_FILE = CONFIG_DIR / "remote_hosts.json"

# Ensure data dir exists at runtime
DATA_DIR.mkdir(exist_ok=True)

# ─── Remote Host Switching ────────────────────────────────────────────────────
def load_remote_hosts():
    """Load remote hosts config. Returns active host URL and fallback URL."""
    if REMOTE_HOSTS_FILE.exists():
        with open(REMOTE_HOSTS_FILE) as f:
            config = json.load(f)
        hosts = config.get("hosts", {})
        active_key = config.get("active_host", "local")
        fallback_key = config.get("fallback_host", "ollama-local")
        active_url = hosts.get(active_key, {}).get("url", "http://localhost:1234/v1")
        fallback_url = hosts.get(fallback_key, {}).get("url", "http://localhost:11434/v1")
        return active_url, fallback_url, active_key
    return "http://localhost:1234/v1", "http://localhost:11434/v1", "local"

def switch_active_host(host_key: str):
    """Switch the active host in remote_hosts.json."""
    if REMOTE_HOSTS_FILE.exists():
        with open(REMOTE_HOSTS_FILE) as f:
            config = json.load(f)
        if host_key in config.get("hosts", {}):
            config["active_host"] = host_key
            with open(REMOTE_HOSTS_FILE, "w") as f:
                json.dump(config, f, indent=2)
            return True
    return False

def list_hosts():
    """List all available hosts."""
    if REMOTE_HOSTS_FILE.exists():
        with open(REMOTE_HOSTS_FILE) as f:
            config = json.load(f)
        return config.get("hosts", {}), config.get("active_host", "local")
    return {}, "local"

# ─── Backend API ──────────────────────────────────────────────────────────────
ACTIVE_BACKEND_URL, FALLBACK_BACKEND_URL, ACTIVE_HOST_KEY = load_remote_hosts()
OLLAMA_URL = os.getenv("OLLAMA_URL", ACTIVE_BACKEND_URL)
DEFAULT_MODEL = os.getenv("AOS_MODEL", "qwen2.5-coder-1.5b-instruct")

# ─── Arena Defaults ───────────────────────────────────────────────────────────
TOTAL_TOKENS_PER_ROUND = int(os.getenv("AOS_TOKENS_PER_ROUND", "2048"))
INITIAL_AGENT_BALANCE = float(os.getenv("AOS_INITIAL_BALANCE", "100.0"))

# ─── API Auth ─────────────────────────────────────────────────────────────────
AOS_API_KEY = os.getenv("AOS_API_KEY", None)  # None = auth disabled (dev mode)

# ─── RAG Pipeline ─────────────────────────────────────────────────────────────
INGRESS_DIR = DATA_DIR / "ingress"
INGRESS_DIR.mkdir(exist_ok=True)

PGVECTOR_HOST = os.getenv("PGVECTOR_HOST", "localhost")
PGVECTOR_PORT = int(os.getenv("PGVECTOR_PORT", "5432"))
PGVECTOR_DB = os.getenv("PGVECTOR_DB", "aos_rag")
PGVECTOR_USER = os.getenv("PGVECTOR_USER", "aos")
PGVECTOR_PASSWORD = os.getenv("PGVECTOR_PASSWORD", "aos_local_dev")
PGVECTOR_CONN_STRING = f"postgresql://{PGVECTOR_USER}:{PGVECTOR_PASSWORD}@{PGVECTOR_HOST}:{PGVECTOR_PORT}/{PGVECTOR_DB}"

RAG_EMBED_MODEL = os.getenv("RAG_EMBED_MODEL", "nomic-embed-text")
RAG_LLM_MODEL = os.getenv("RAG_LLM_MODEL", "llama3")
