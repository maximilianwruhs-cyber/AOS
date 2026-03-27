---
name: aos
description: AgenticOS — Sovereign LLM Gateway with energy-aware model routing
version: 4.1.0
---

# AOS Skill

AgenticOS (AOS) is a reactive LLM gateway that routes inference requests between
local and remote LLM backends (LM Studio, Ollama) with energy-aware model selection.

## Prerequisites

- AOS daemon running on `localhost:8000` (systemd: `aos-core.service`)
- At least one LLM backend (LM Studio on port 1234 or Ollama on port 11434)

## Commands

### Check System Health
```bash
aos health
```
Returns daemon status, active model, backend reachability.

### List Available Backends
```bash
aos hosts
```
Shows all configured LLM backends (local, remote, Ollama, LM Studio).

### Switch Active Backend
```bash
aos switch <host-key>
```
Switches the active LLM backend at runtime.
Available keys: `local`, `aos-keller`, `ollama-local`, `ollama-keller`

### List Loaded Models
```bash
aos models
```
Proxies the models endpoint from the active backend.

### Run Inference
```bash
aos ask "Your prompt here"
```
Sends a prompt through the AOS gateway with automatic complexity triage and model selection.

### Run Benchmark
```bash
aos bench --model <model-name> [--suite full|math|code]
```
Runs the full benchmark suite, measuring energy, quality, and z-score.

### Show Leaderboard
```bash
aos leaderboard
```
Compares all previous benchmark results, ranked by intelligence-per-watt.

### eGPU Switcher (optional, Thunderbolt machines only)
```bash
sudo egpu-switcher setup       # Interactive GPU selection
sudo egpu-switcher enable      # Enable auto-switch on boot
sudo egpu-switcher disable     # Disable auto-switch
egpu-switcher status           # Show current GPU config
```
Manages external GPU switching for machines with Thunderbolt eGPU enclosures. Installed automatically when a Thunderbolt controller is detected.

## API Endpoints

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/health` | GET | No | Health check |
| `/v1/hosts` | GET | No | List backends |
| `/v1/hosts/switch` | POST | Yes | Switch backend |
| `/v1/models` | GET | No | List models |
| `/v1/chat/completions` | POST | Yes | Run inference |
| `/v1/rag/ingest` | POST | Yes | Ingest a document into the RAG database |
| `/v1/rag/query` | POST | Yes | Query the RAG database with natural language |

### Ingest a Document (RAG)
```bash
aos ingest <file-path>
```
Parses a local PDF/document via LiteParse, embeds it with Ollama, and stores it in the local pgvector database.

### Query the Knowledge Base (RAG)
```bash
aos query "Your question here"
```
Searches the local pgvector database and generates an answer using the local LLM.

## Authentication

Set `AOS_API_KEY` in the environment to enable Bearer Token authentication.
Pass the token as: `Authorization: Bearer <your-key>`
