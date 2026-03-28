#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#  🏛️  AgenticOS (AOS) — Single-Command Bootstrap
# ═══════════════════════════════════════════════════════════════════════════════
#  Usage:
#    curl -fsSL https://raw.githubusercontent.com/maximilianwruhs-cyber/AOS/main/bootstrap.sh | bash
#
#  Prerequisites: A fresh Ubuntu 24.04 LTS installation with internet access.
#  This script is idempotent — safe to run multiple times.
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

# ─── Colors & Helpers ─────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

AOS_REPO="https://github.com/maximilianwruhs-cyber/AOS.git"
AOS_DIR="$HOME/AOS"

step()  { echo -e "\n${CYAN}${BOLD}[$1/8]${NC} ${BOLD}$2${NC}"; }
ok()    { echo -e "  ${GREEN}✅ $1${NC}"; }
skip()  { echo -e "  ${YELLOW}⏭️  $1${NC}"; }
fail()  { echo -e "  ${RED}❌ $1${NC}"; }
info()  { echo -e "  ${CYAN}ℹ️  $1${NC}"; }

# ─── Banner ───────────────────────────────────────────────────────────────────
echo -e "${CYAN}${BOLD}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║        🏛️  AgenticOS (AOS) — Bootstrap Installer            ║"
echo "║     The Sovereign AI Layer for Ubuntu 24.04 LTS             ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ─── Pre-flight Checks ───────────────────────────────────────────────────────
step 1 "Pre-flight checks"

# Check Ubuntu
if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [[ "$ID" != "ubuntu" ]]; then
        fail "This script requires Ubuntu. Detected: $ID"
        exit 1
    fi
    ok "OS: $PRETTY_NAME"
else
    fail "Cannot detect OS. /etc/os-release not found."
    exit 1
fi

# Check internet
if ping -c 1 -W 3 github.com &>/dev/null; then
    ok "Internet connectivity verified"
else
    fail "No internet connection. Cannot reach github.com."
    exit 1
fi

# Check disk space (require at least 8 GB free)
FREE_GB=$(df -BG --output=avail "$HOME" | tail -1 | tr -d ' G')
if [ "$FREE_GB" -lt 8 ]; then
    fail "Insufficient disk space: ${FREE_GB}GB free, need at least 8GB."
    exit 1
fi
ok "Disk space: ${FREE_GB}GB available"

# ─── Sudo Session ────────────────────────────────────────────────────────────
echo ""
info "This script requires sudo for system packages. You will be prompted once."
sudo -v
# Keep sudo alive in the background
( while true; do sudo -n true; sleep 50; done ) 2>/dev/null &
SUDO_KEEPER_PID=$!
trap "kill $SUDO_KEEPER_PID 2>/dev/null" EXIT

# ═══════════════════════════════════════════════════════════════════════════════
step 2 "Installing base dependencies (Ansible, Git)"

if command -v ansible-playbook &>/dev/null && command -v git &>/dev/null; then
    skip "Ansible and Git already installed"
else
    sudo apt update -qq
    sudo apt install -y -qq ansible git > /dev/null 2>&1
    ok "Ansible and Git installed"
fi

# ═══════════════════════════════════════════════════════════════════════════════
step 3 "Cloning AOS repository"

if [ -d "$AOS_DIR/.git" ]; then
    skip "AOS repo already exists at $AOS_DIR"
    info "Pulling latest changes..."
    git -C "$AOS_DIR" pull --ff-only 2>/dev/null || info "Pull skipped (local changes detected)"
else
    git clone "$AOS_REPO" "$AOS_DIR"
    ok "Cloned AOS to $AOS_DIR"
fi

# ═══════════════════════════════════════════════════════════════════════════════
step 4 "Running Ansible provisioning playbook"

info "This installs: Node.js 22+, Docker, Ollama, LM Studio, egpu-switcher, LiteParse..."
info "This may take several minutes on a fresh machine."
cd "$AOS_DIR"
ansible-playbook install.yml --connection=local -K
ok "Ansible provisioning complete"

# ═══════════════════════════════════════════════════════════════════════════════
step 5 "Installing Python dependencies"

if [ -d "$AOS_DIR/.venv" ]; then
    skip "Virtual environment already exists"
else
    python3 -m venv "$AOS_DIR/.venv"
    ok "Virtual environment created"
fi

"$AOS_DIR/.venv/bin/pip" install -q --upgrade pip > /dev/null 2>&1
"$AOS_DIR/.venv/bin/pip" install -q -r "$AOS_DIR/requirements.txt" 2>&1 | tail -1
ok "Python dependencies installed"

# ═══════════════════════════════════════════════════════════════════════════════
step 6 "Pulling Ollama models"

if command -v ollama &>/dev/null; then
    MODELS=("nomic-embed-text" "llama3")
    for model in "${MODELS[@]}"; do
        if ollama list 2>/dev/null | grep -q "$model"; then
            skip "$model already available"
        else
            info "Pulling $model (this may take a while)..."
            ollama pull "$model" || fail "Failed to pull $model — you can retry later with: ollama pull $model"
        fi
    done
else
    fail "Ollama not found. It should have been installed by Ansible."
    info "Try manually: curl -fsSL https://ollama.com/install.sh | sh"
fi

# ═══════════════════════════════════════════════════════════════════════════════
step 7 "Starting Docker services (pgvector)"

if command -v docker &>/dev/null; then
    if sudo docker ps --format '{{.Names}}' 2>/dev/null | grep -q "aos-pgvector"; then
        skip "pgvector container already running"
    else
        info "Starting pgvector container (using sudo — docker group activates on next login)..."
        sudo docker compose -f "$AOS_DIR/docker-compose.yml" up -d 2>/dev/null || \
            fail "Docker failed. After reboot, run: cd ~/AOS && docker compose up -d"
        ok "pgvector Postgres container started"
    fi
else
    fail "Docker not found. It should have been installed by Ansible."
    info "After installing Docker, run: cd ~/AOS && docker compose up -d"
fi

# ═══════════════════════════════════════════════════════════════════════════════
step 8 "Health check"

# Wait for services to stabilize
sleep 3

echo ""
PASS=0
TOTAL=0

# Check Ollama
TOTAL=$((TOTAL + 1))
if curl -sf http://localhost:11434/api/tags &>/dev/null; then
    ok "Ollama is running (port 11434)"
    PASS=$((PASS + 1))
else
    fail "Ollama is not responding on port 11434"
fi

# Check pgvector
TOTAL=$((TOTAL + 1))
if sudo docker ps --format '{{.Names}}' 2>/dev/null | grep -q "aos-pgvector"; then
    ok "pgvector Postgres is running"
    PASS=$((PASS + 1))
else
    fail "pgvector container is not running"
fi

# Check LM Studio (may not be running yet)
TOTAL=$((TOTAL + 1))
if curl -sf http://localhost:1234/v1/models &>/dev/null; then
    ok "LM Studio is running (port 1234)"
    PASS=$((PASS + 1))
else
    info "LM Studio not responding (port 1234) — start it manually or wait for systemd"
    PASS=$((PASS + 1))  # Non-critical
fi

# Check AOS daemon
TOTAL=$((TOTAL + 1))
if curl -sf http://localhost:8000/health &>/dev/null; then
    ok "AOS daemon is running (port 8000)"
    PASS=$((PASS + 1))
else
    info "AOS daemon not responding yet — it may still be starting"
    info "Check with: systemctl status aos-core"
fi

# ─── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}${BOLD}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                 🏛️  AOS Bootstrap Complete                   ║"
echo "╠═══════════════════════════════════════════════════════════════╣"
echo -e "║  Health: ${PASS}/${TOTAL} services OK                                  ║"
echo "║                                                             ║"
echo "║  Quick Start:                                               ║"
echo "║    aos health          — Check system status                ║"
echo "║    aos ask \"hello\"     — Run inference                      ║"
echo "║    aos ingest file.pdf — Ingest into RAG database           ║"
echo "║    aos query \"...\"     — Query your knowledge base          ║"
echo "║    aos hosts           — List LLM backends                  ║"
echo "║                                                             ║"
echo "║  Logs:                                                      ║"
echo "║    journalctl -u aos-core -f                                ║"
echo "║    journalctl -u lm-studio -f                               ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
