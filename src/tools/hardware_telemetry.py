#!/usr/bin/env python3
"""
AOS Hardware Telemetry Engine
Natively triggers the intelligence-per-watt evaluators physically embedded in AOS.
"""
import sys
from pathlib import Path

# Add src to path so we can import telemetry_engine natively
sys.path.insert(0, str(Path(__file__).parent.parent))
from telemetry_engine.runner import run_benchmark

def run_telemetry(model_name: str, suite: str = "math"):
    print(f"⚡ [TELEMETRY] Analyzing hardware efficiency for {model_name}...")
    
    try:
        run_benchmark(
            model=model_name,
            suite=suite,
            temperature=0.3,
            verbose=True
        )
        print("   ✅ Telemetry captured successfully.")
        return True
    except Exception as e:
        print(f"   ❌ Error executing native telemetry: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 hardware_telemetry.py <model_name> [suite]")
        sys.exit(1)
    s = sys.argv[2] if len(sys.argv) > 2 else "math"
    run_telemetry(sys.argv[1], s)
