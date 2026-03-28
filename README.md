# 🏛️ AgenticOS (AOS)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform: Ubuntu](https://img.shields.io/badge/platform-Ubuntu%2024.04-E95420?logo=ubuntu&logoColor=white)](https://ubuntu.com/)
[![Part of: AgenticOS](https://img.shields.io/badge/ecosystem-AgenticOS-blue)](https://github.com/maximilianwruhs-cyber)

**The Plug-and-Play, Agentic-First Operating System for the Cloud-Edge Era.**

AgenticOS (AOS) is not a traditional operating system. It is a sovereign artificial intelligence layer built for Ubuntu that treats large language models as its engine. It natively hot-swaps AI models in and out of GPU VRAM based on real-time task complexity and Intel RAPL energy telemetry (Intelligence per Watt).

## Core Architecture
- **LM Studio**: The Engine Room (loads and unloads quantized models).
- **VS Codium + Continue.dev**: The primary customer-facing editor with local AI coding.
- **Antigravity (VS Code)**: Setup & development editor with Google Cloud integration.
- **Obolus**: The Diagnostics Tool (benchmarks models on the precise hardware it wakes up on).
- **GZMO (Chief of Staff)**: The sovereign brain that evaluates logs, runs Obolus, and delegates to the cloud only when the absolute intelligence ceiling of local hardware is breached.

## Installation

On a fresh **Ubuntu 24.04 LTS** machine, run:

```bash
curl -fsSL https://raw.githubusercontent.com/maximilianwruhs-cyber/AOS/main/deploy/bootstrap.sh | bash
```

<details>
<summary>Manual Installation (fallback)</summary>

```bash
sudo apt update && sudo apt install -y ansible git
git clone https://github.com/maximilianwruhs-cyber/AOS.git
cd AOS
ansible-playbook deploy/ansible/install.yml -K
```

</details>

## Development Setup

```bash
git clone https://github.com/maximilianwruhs-cyber/AOS.git
cd AOS
python3 -m venv .venv && source .venv/bin/activate
pip install -e .            # Core gateway
pip install -e '.[rag]'     # + RAG pipeline
```

## Project Structure

```
AOS/
├── src/aos/                    # Python package
│   ├── gateway/                # FastAPI reactive inference router
│   │   ├── app.py              # Application entrypoint & lifespan
│   │   ├── auth.py             # Bearer token authentication
│   │   ├── routes.py           # API route handlers & shadow evaluator
│   │   └── triage.py           # Prompt complexity classification
│   ├── telemetry/              # Energy-aware benchmarking & evaluation
│   ├── tools/                  # Hardware telemetry, VRAM manager, watchdog
│   ├── simulation/             # Sandboxed code execution
│   ├── cli.py                  # CLI wrapper for the gateway API
│   ├── config.py               # Centralized configuration
│   └── rag_engine.py           # Local RAG pipeline (LiteParse + pgvector)
├── config/                     # Runtime configuration files
│   ├── remote_hosts.json       # LLM backend host definitions
│   ├── mcp_config.json         # MCP server configuration (both editors)
│   ├── continue_config.json    # Continue.dev → LM Studio config
│   └── lm_studio_mcp.py       # LM Studio MCP bridge script
├── core_identity/              # Agent persona definitions (Markdown)
├── deploy/                     # Deployment & provisioning
│   ├── ansible/                # Ansible playbooks
│   ├── iso/                    # Custom Ubuntu ISO builder
│   └── bootstrap.sh            # One-command setup script
├── data/                       # Runtime data (gitignored)
├── docs/                       # Documentation
├── tests/                      # Test suite (coming soon)
├── _archive/                   # Legacy/archived files
├── pyproject.toml              # Python package definition
├── docker-compose.yml          # pgvector database
└── requirements.txt            # Pinned dependencies
```

## Components
- `deploy/bootstrap.sh`: One-command setup for fresh Ubuntu machines.
- `deploy/ansible/install.yml`: The Ansible deployment orchestrator.
- `src/aos/gateway/app.py`: The Chief of Staff lifecycle script.
- `src/aos/rag_engine.py`: Local RAG pipeline (LiteParse + Ollama + pgvector).
- `src/aos/tools/`: Integration bindings for LM Studio APIs and Hardware Telemetry.

---

## AgenticOS Ecosystem

| Project | Description |
|---------|-------------|
| [**AOS Customer Edition**](https://github.com/maximilianwruhs-cyber/AOS-Customer-Edition) | Zero-touch deployment — one `curl` command installs everything |
| [**AOS Intelligence Dashboard**](https://github.com/maximilianwruhs-cyber/AOS-Intelligence-Dashboard) | VS Codium extension for real-time energy monitoring & LLM leaderboard |
| [**Obolus**](https://github.com/maximilianwruhs-cyber/Obolus) | Intelligence per Watt — benchmark which LLM is most efficient on your hardware |
| [**HSP**](https://github.com/maximilianwruhs-cyber/HSP) | Hardware Sonification Pipeline — turn machine telemetry into music |
| [**HSP VS Codium Extension**](https://github.com/maximilianwruhs-cyber/HSP-VS-Codium-Extension) | VS Codium sidebar for live HSP telemetry visualization |

## License

MIT — see [LICENSE](LICENSE).

