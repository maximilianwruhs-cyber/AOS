# 🏛️ AgenticOS (AOS)

**The Plug-and-Play, Agentic-First Operating System for the Cloud-Edge Era.**

AgenticOS (AOS) is not a traditional operating system. It is a sovereign artificial intelligence layer built for Ubuntu that treats large language models as its engine. It natively hot-swaps AI models in and out of GPU VRAM based on real-time task complexity and Intel RAPL energy telemetry (Intelligence per Watt).

## Core Architecture
- **LM Studio**: The Engine Room (loads and unloads quantized models).
- **Obolus**: The Diagnostics Tool (benchmarks models on the precise hardware it wakes up on).
- **GZMO (Chief of Staff)**: The sovereign brain that evaluates logs, runs Obolus, and delegates to the cloud only when the absolute intelligence ceiling of local hardware is breached.

## Installation

On a fresh **Ubuntu 24.04 LTS** machine, run:

```bash
curl -fsSL https://raw.githubusercontent.com/maximilianwruhs-cyber/AOS/main/bootstrap.sh | bash
```

This single command will install all dependencies, clone the repo, provision AI engines (Ollama, LM Studio), start the RAG database, pull models, and verify everything is healthy.

<details>
<summary>Manual Installation (fallback)</summary>

```bash
sudo apt update && sudo apt install -y ansible git
git clone https://github.com/maximilianwruhs-cyber/AOS.git
cd AOS
ansible-playbook install.yml -K
```

</details>

## Components
- `bootstrap.sh`: One-command setup for fresh Ubuntu machines.
- `install.yml`: The Ansible deployment orchestrator.
- `src/aos_daemon.py`: The Chief of Staff lifecycle script.
- `src/rag_engine.py`: Local RAG pipeline (LiteParse + Ollama + pgvector).
- `src/tools/`: Integration bindings for LM Studio APIs and Hardware Telemetry.
