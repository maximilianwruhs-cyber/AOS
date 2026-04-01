# ═══════════════════════════════════════════════════════════════════════
#  🏛️ AOS Gateway — Production Container
#  Multi-stage build for minimal attack surface
# ═══════════════════════════════════════════════════════════════════════
FROM python:3.12-slim AS base

LABEL maintainer="AOS Sovereign Factory"
LABEL description="AgenticOS Gateway — Energy-Aware LLM Router"

# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# ─── System deps (RAPL needs linux-tools, psutil needs gcc) ──────────
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ─── Python deps ─────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─── Application source ─────────────────────────────────────────────
COPY src/ ./src/
COPY config/ ./config/
COPY pyproject.toml .

# Install the package in editable mode
RUN pip install --no-cache-dir -e .

# ─── Volumes ──────────────────────────────────────────────────────────
# Obsidian Vault for stigmergic memory
VOLUME ["/vault"]
# Benchmark data persistence
VOLUME ["/data"]

# ─── Healthcheck ──────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ─── Runtime ──────────────────────────────────────────────────────────
EXPOSE 8000

ENV PYTHONPATH=/app/src
ENV AOS_VAULT_PATH=/vault/Evaluations
ENV AOS_DATA_DIR=/data

CMD ["python3", "-m", "aos.gateway.app"]
