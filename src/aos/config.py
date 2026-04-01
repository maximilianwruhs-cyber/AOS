"""
AOS — Configuration (BACKWARD COMPATIBILITY SHIM)
Real implementation: aos.core.settings + aos.core.paths

This file re-exports ALL legacy symbols so existing code like:
    from aos.config import DATA_DIR
    import aos.config as config
continues to work during migration. Will be DELETED in Phase 4.
"""
import json
from pathlib import Path

# ─── Re-export paths ─────────────────────────────────────────────────────────
from aos.core.paths import (  # noqa: F401
    PROJECT_ROOT,
    AGENTS_DIR,
    DATA_DIR,
    TOOLS_DIR,
    DOCS_DIR,
    CONFIG_DIR,
    REMOTE_HOSTS_FILE,
)

# ─── Re-export settings as module-level constants ────────────────────────────
from aos.core.settings import get_settings as _get_settings

_s = _get_settings()

ACTIVE_BACKEND_URL = _s.active_backend_url
FALLBACK_BACKEND_URL = _s.fallback_backend_url
ACTIVE_HOST_KEY = _s.active_host_key
OLLAMA_URL = _s.ollama_url
DEFAULT_MODEL = _s.default_model
TOTAL_TOKENS_PER_ROUND = _s.total_tokens_per_round
INITIAL_AGENT_BALANCE = _s.initial_agent_balance
AOS_API_KEY = _s.aos_api_key

PGVECTOR_HOST = _s.pgvector_host
PGVECTOR_PORT = _s.pgvector_port
PGVECTOR_DB = _s.pgvector_db
PGVECTOR_USER = _s.pgvector_user
PGVECTOR_PASSWORD = _s.pgvector_password
PGVECTOR_CONN_STRING = _s.pgvector_conn_string
RAG_EMBED_MODEL = _s.rag_embed_model
RAG_LLM_MODEL = _s.rag_llm_model

INGRESS_DIR = _s.ingress_dir

# ─── Re-export host management functions ──────────────────────────────────────
# These are stateful operations that mutate remote_hosts.json
# Will be moved to features/hosts/service.py in Phase 2


def load_remote_hosts():
    """Load remote hosts config. Returns (active_url, fallback_url, active_key)."""
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
