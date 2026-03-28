#!/usr/bin/env python3
"""
Obolus Agentic Orchestrator
Continuously feeds all 17 specialized agent profiles into the Obolus Evolutionary Arena.
"""
import os
import subprocess
from pathlib import Path
import sys

OBOLUS_DIR = Path("/home/maximilian-wruhs/Dokumente/Obolus/Obolus")
AGENTS_DIR = OBOLUS_DIR / "agents"

def main():
    print(f"\n{'='*60}")
    print(f"  ⚡ OBULUS AGENTIC ORCHESTRATOR")
    print(f"{'='*60}\n")
    
    if not AGENTS_DIR.exists():
        print("❌ Error: agents/ directory not found.")
        sys.exit(1)
        
    # Discover all agent profiles
    agent_files = [f.name for f in AGENTS_DIR.glob("*.md")]
    if not agent_files:
        print("❌ Error: No agent profiles found in agents/.")
        sys.exit(1)
        
    print(f"📦 Discovered {len(agent_files)} master agent identities:")
    for a in agent_files:
        print(f"   - {a}")
        
    # Construct the evolutionary arena command
    cmd = [
        ".venv/bin/python3", "obulus.py", "evolve",
        "--suite", "full",
        "--epochs", "50",
        "--agents"
    ] + agent_files
    
    print(f"\n🚀 Launching Evolutionary Arena (The Forge)...")
    print(f"   Command: {' '.join(cmd)}\n")
    
    try:
        subprocess.run(cmd, cwd=OBOLUS_DIR)
    except KeyboardInterrupt:
        print("\n🛑 Orchestrator interrupted by user.")
    except Exception as e:
        print(f"\n❌ Orchestrator failed: {e}")

if __name__ == "__main__":
    main()
