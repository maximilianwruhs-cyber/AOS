#!/usr/bin/env python3
"""
AOS Hardware Telemetry Engine
Natively triggers the intelligence-per-watt evaluators physically embedded in AOS.
"""
import sys
from pathlib import Path
import asyncio  # FIX #18: run_benchmark is async

# Add src to path so we can import telemetry_engine natively
from aos.telemetry.runner import run_benchmark

def run_telemetry(model_name: str, suite: str = "math"):
    print(f"⚡ [TELEMETRY] Analyzing hardware efficiency for {model_name}...")
    
    try:
        asyncio.run(run_benchmark(  # FIX #18: run_benchmark is async
            model=model_name,
            suite=suite,
            temperature=0.3,
            verbose=True
        ))
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
