"""
AOS Core — Typed Settings (Pydantic BaseSettings)
Replaces the config.py god-object with a validated, injectable settings class.
All values can be overridden via environment variables or .env file.
"""
import json
import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict

from aos.core.paths import PROJECT_ROOT, DATA_DIR, CONFIG_DIR, REMOTE_HOSTS_FILE


class Settings(BaseSettings):
    """Immutable, validated configuration for the AOS stack."""

    # ─── Backend API ──────────────────────────────────────────────────────
    active_backend_url: str = Field(default="http://localhost:1234/v1")
    fallback_backend_url: str = Field(default="http://localhost:11434/v1")
    active_host_key: str = Field(default="local")
    ollama_url: str = Field(default="")
    default_model: str = Field(default="qwen2.5-coder-1.5b-instruct", alias="AOS_MODEL")

    # ─── Arena Defaults ───────────────────────────────────────────────────
    total_tokens_per_round: int = Field(default=2048, alias="AOS_TOKENS_PER_ROUND")
    initial_agent_balance: float = Field(default=100.0, alias="AOS_INITIAL_BALANCE")

    # ─── API Auth ─────────────────────────────────────────────────────────
    aos_api_key: Optional[str] = Field(default=None, alias="AOS_API_KEY")

    # ─── RAG Pipeline ─────────────────────────────────────────────────────
    pgvector_host: str = Field(default="localhost", alias="PGVECTOR_HOST")
    pgvector_port: int = Field(default=5432, alias="PGVECTOR_PORT")
    pgvector_db: str = Field(default="aos_rag", alias="PGVECTOR_DB")
    pgvector_user: str = Field(default="aos", alias="PGVECTOR_USER")
    pgvector_password: str = Field(default="aos_local_dev", alias="PGVECTOR_PASSWORD")
    rag_embed_model: str = Field(default="nomic-embed-text", alias="RAG_EMBED_MODEL")
    rag_llm_model: str = Field(default="llama3", alias="RAG_LLM_MODEL")

    # ─── Vault (Stigmergy) ────────────────────────────────────────────────
    vault_path: str = Field(
        default="",
        alias="AOS_VAULT_PATH",
    )

    @property
    def pgvector_conn_string(self) -> str:
        """Construct PostgreSQL connection string from components."""
        return (
            f"postgresql://{self.pgvector_user}:{self.pgvector_password}"
            f"@{self.pgvector_host}:{self.pgvector_port}/{self.pgvector_db}"
        )

    @property
    def ingress_dir(self) -> Path:
        """Directory for RAG document ingestion."""
        d = DATA_DIR / "ingress"
        d.mkdir(exist_ok=True)
        return d

    model_config = ConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )


def _resolve_hosts(settings: Settings) -> Settings:
    """Load active/fallback URLs from remote_hosts.json if it exists."""
    if REMOTE_HOSTS_FILE.exists():
        try:
            with open(REMOTE_HOSTS_FILE) as f:
                config = json.load(f)
            hosts = config.get("hosts", {})
            active_key = config.get("active_host", "local")
            fallback_key = config.get("fallback_host", "ollama-local")
            active_url = hosts.get(active_key, {}).get("url", settings.active_backend_url)
            fallback_url = hosts.get(fallback_key, {}).get("url", settings.fallback_backend_url)
            # Use object.__setattr__ since Pydantic models may be frozen
            object.__setattr__(settings, "active_backend_url", active_url)
            object.__setattr__(settings, "fallback_backend_url", fallback_url)
            object.__setattr__(settings, "active_host_key", active_key)
        except (json.JSONDecodeError, IOError):
            pass

    if not settings.ollama_url:
        object.__setattr__(settings, "ollama_url", settings.active_backend_url)

    return settings


# ─── Singleton ────────────────────────────────────────────────────────────────
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Return the singleton Settings instance, creating it on first call."""
    global _settings
    if _settings is None:
        _settings = _resolve_hosts(Settings())
    return _settings
