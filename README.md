# 🏛️ AgenticOS (AOS)

**The Plug-and-Play, Agentic-First Operating System for the Cloud-Edge Era.**

AgenticOS (AOS) is not a traditional operating system. It is a sovereign artificial intelligence layer built for Ubuntu that treats large language models as its engine. It natively hot-swaps AI models in and out of GPU VRAM based on real-time task complexity and Intel RAPL energy telemetry (Intelligence per Watt).

## Core Architecture
- **LM Studio**: The Engine Room (loads and unloads quantized models).
- **Obolus**: The Diagnostics Tool (benchmarks models on the precise hardware it wakes up on).
- **GZMO (Chief of Staff)**: The sovereign brain that evaluates logs, runs Obolus, and delegates to the cloud only when the absolute intelligence ceiling of local hardware is breached.

## Installation
If you are starting with a completely empty Ubuntu 24.04 LTS machine, you only need to run:

```bash
sudo apt update && sudo apt install -y ansible git
git clone https://github.com/maximilianwruhs-cyber/AOS.git
cd AOS
ansible-playbook install.yml -K
```

Ansible will provision all dependencies, unlock hardware sensors, download LM Studio and Ollama, setup Python virtual environments, and permanently enroll the `aos-core` daemon into `systemd`.

## Components
- `install.yml`: The Ansible deployment orchestrator.
- `src/aos_daemon.py`: The Chief of Staff lifecycle script.
- `src/tools/`: Integration bindings for LM Studio APIs and Hardware Telemetry execution.
