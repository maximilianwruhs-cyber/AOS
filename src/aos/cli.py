#!/usr/bin/env python3
"""
AOS CLI — Thin wrapper for the AOS Gateway API.
Used by CLI-Anything and OpenClaw for agent-native interaction.
"""
import sys
import json
import os
from pathlib import Path
import httpx

AOS_URL = os.getenv("AOS_URL", "http://localhost:8000")
AOS_API_KEY = os.getenv("AOS_API_KEY", "")

def _headers():
    h = {"Content-Type": "application/json"}
    if AOS_API_KEY:
        h["Authorization"] = f"Bearer {AOS_API_KEY}"
    return h

def health():
    resp = httpx.get(f"{AOS_URL}/health", timeout=5.0)
    data = resp.json()
    print(f"Status:           {data['status']}")
    print(f"Current Model:    {data.get('current_model', 'none')}")
    print(f"Active Host:      {data.get('active_host', '?')}")
    print(f"Backend URL:      {data.get('backend_url', '?')}")
    print(f"Backend Reachable: {'✅' if data.get('backend_reachable') else '❌'}")

def hosts():
    resp = httpx.get(f"{AOS_URL}/v1/hosts", timeout=5.0)
    data = resp.json()
    active = data.get("active_host", "")
    for key, info in data.get("hosts", {}).items():
        marker = " ◀ ACTIVE" if key == active else ""
        print(f"  {key:20} {info['url']:40} {info.get('description', '')}{marker}")

def switch(host_key: str):
    resp = httpx.post(f"{AOS_URL}/v1/hosts/switch",
                      json={"host": host_key}, headers=_headers(), timeout=5.0)
    data = resp.json()
    if resp.status_code == 200:
        print(f"✅ Switched to: {host_key} ({data.get('url', '')})")
    else:
        print(f"❌ Error: {data.get('error', 'unknown')}")

def models():
    resp = httpx.get(f"{AOS_URL}/v1/models", timeout=5.0)
    data = resp.json()
    if "data" in data:
        for m in data["data"]:
            print(f"  {m.get('id', '?')}")
    else:
        print(json.dumps(data, indent=2))

def ask(prompt: str):
    resp = httpx.post(f"{AOS_URL}/v1/chat/completions",
                      json={"model": "auto", "messages": [{"role": "user", "content": prompt}]},
                      headers=_headers(), timeout=300.0)
    data = resp.json()
    if "choices" in data:
        print(data["choices"][0].get("message", {}).get("content", ""))
    else:
        print(json.dumps(data, indent=2))

def main():
    if len(sys.argv) < 2:
        print("Usage: aos <command> [args]")
        print("Commands: health, hosts, switch <key>, models, ask <prompt>,")
        print("          ingest <file>, query <question>, bench, leaderboard")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "health":
        health()
    elif cmd == "hosts":
        hosts()
    elif cmd == "switch":
        if len(sys.argv) < 3:
            print("Usage: aos switch <host-key>")
            sys.exit(1)
        switch(sys.argv[2])
    elif cmd == "models":
        models()
    elif cmd == "ask":
        if len(sys.argv) < 3:
            print("Usage: aos ask \"your prompt\"")
            sys.exit(1)
        ask(" ".join(sys.argv[2:]))
    elif cmd == "bench":
        import subprocess
        # Resolve package directory → project root → src/aos/telemetry/runner.py
        pkg_dir = Path(__file__).resolve().parent
        runner = str(pkg_dir / "telemetry" / "runner.py")
        subprocess.run([sys.executable, runner] + sys.argv[1:])
    elif cmd == "leaderboard":
        import subprocess
        pkg_dir = Path(__file__).resolve().parent
        runner = str(pkg_dir / "telemetry" / "runner.py")
        subprocess.run([sys.executable, runner, "compare"])
    elif cmd == "ingest":
        if len(sys.argv) < 3:
            print("Usage: aos ingest <file-path>")
            sys.exit(1)
        import subprocess
        pkg_dir = Path(__file__).resolve().parent
        rag = str(pkg_dir / "rag_engine.py")
        subprocess.run([sys.executable, rag, "ingest", sys.argv[2]])
    elif cmd == "query":
        if len(sys.argv) < 3:
            print('Usage: aos query "your question"')
            sys.exit(1)
        import subprocess
        pkg_dir = Path(__file__).resolve().parent
        rag = str(pkg_dir / "rag_engine.py")
        subprocess.run([sys.executable, rag, "query", " ".join(sys.argv[2:])])
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()
