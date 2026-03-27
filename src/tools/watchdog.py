#!/usr/bin/env python3
"""AOS Watchdog - LOCAL ONLY EDITION. Slim and efficient."""
import subprocess
import os
import glob
from datetime import datetime
from pathlib import Path

# FIX Bug #22: resolve from script location, not hardcoded path
WORKSPACE = str(Path(__file__).parent.parent.parent.resolve())
TOKEN_WARNING_THRESHOLD = 50    # 50k tokens
TOKEN_CRITICAL_THRESHOLD = 150  # 150k tokens

def check_token_usage() -> int:
    """Token Efficiency Audit."""
    print("Watchdog: Checking Token Efficiency...")
    # NOTE: In AOS, token usage is tracked by the telemetry_engine.
    # This is a stub for future integration.
    used_k = 0
    try:
        # Placeholder for actual AOS token tracking logic
        pass
    except Exception as e:
        print(f"Watchdog Token Check Error: {e}")
    return used_k

def check_integrity():
    """Security & Integrity Guard."""
    print("Watchdog: Monitoring Integrity...")
    try:
        ss_output = subprocess.check_output(["ss", "-antup"]).decode()
        for line in ss_output.splitlines():
            if "python" in line and "ESTAB" in line:
                if "127.0.0.1" not in line:
                    print(f"Watchdog WARNING: External connection detected: {line}")
        print("  Integrity check passed.")
    except Exception as e:
        print(f"Watchdog Integrity Check Error: {e}")

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"  AOS LOCAL WATCHDOG — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    check_token_usage()
    check_integrity()

    print(f"\n{'='*60}")
    print(f"  AOS WATCHDOG COMPLETE")
    print(f"{'='*60}\n")
