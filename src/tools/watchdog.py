#!/usr/bin/env python3
"""GZMO Watchdog - LOCAL ONLY EDITION. Slim and efficient."""
import subprocess
import os
import glob
from datetime import datetime

# CONFIG
WORKSPACE = "/home/nikian/.openclaw/workspace"
TOKEN_WARNING_THRESHOLD = 50    # 50k tokens
TOKEN_CRITICAL_THRESHOLD = 150  # 150k tokens

def check_token_usage() -> int:
    """Token Efficiency Audit."""
    print("Watchdog: Checking Token Efficiency...")
    used_k = 0
    try:
        output = subprocess.check_output(["/usr/bin/openclaw", "status"]).decode()
        for line in output.splitlines():
            if "agent:main:main" in line:
                parts = line.split("│")
                if len(parts) >= 6:
                    tokens = parts[5].strip()
                    if "k/" in tokens:
                        used_str = tokens.split("k/")[0]
                        if used_str.isdigit():
                            used_k = int(used_str)
                            if used_k > TOKEN_WARNING_THRESHOLD:
                                print(f"Watchdog WARNING: High token usage ({used_k}k).")
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
    print(f"  GZMO LOCAL WATCHDOG — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    check_token_usage()
    check_integrity()

    print(f"\n{'='*60}")
    print(f"  GOD MODE WATCHDOG COMPLETE")
    print(f"{'='*60}\n")
