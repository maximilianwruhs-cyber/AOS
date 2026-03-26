#!/usr/bin/env python3
"""
AgenticOS (AOS) - Sovereign Daemon
The core operating loop for managing local LLM compute and hardware telemetry.
"""
import time
import sys
from tools.vram_manager import swap_model
from tools.hardware_telemetry import run_telemetry

def log(msg):
    print(f"[AOS-DAEMON] {msg}")

def main():
    print(f"\n{'='*60}")
    print(f"  🏛️ AGENTICOS (AOS) — SOVEREIGN NODE")
    print(f"  Powered by Dynamic VRAM Routing & Intelligence-per-Watt")
    print(f"{'='*60}\n")
    
    # Define models available in LM Studio's models directory
    TINY_MODEL = "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
    HEAVY_MODEL = "deepseek-coder-33b-instruct.Q5_K_M.gguf"
    
    log("Status: Boot Sequence Initiated.")
    
    # 1. Start with the Tiny Model to save power
    log(f"Routing to Lightweight Compute Node...")
    
    # Wait for LM Studio Engine to mount 
    import requests
    log("Waiting for LM Studio Engine API (Port 1234) to bind...")
    for _ in range(30):
        try:
            requests.get("http://127.0.0.1:1234/v1/models", timeout=2)
            log("LM Studio Engine successfully bound.")
            break
        except:
            time.sleep(2)
            
    if not swap_model(TINY_MODEL):
        log("LM Studio unavailable or swap failed. Ensure the server is mounted.")
        sys.exit(1)
        
    log("Lightweight model deployed for background tasks (heartbeat monitoring).")
    time.sleep(2)
    
    # 2. Simulate User escalation
    log("\n[!] ESCALATION: Complex workload detected.")
    log(f"Decision: {TINY_MODEL} insufficient. Swapping to Heavy Compute Node.")
    
    # 3. Swap physically to the big model
    time.sleep(1)
    if swap_model(HEAVY_MODEL):
        log(f"Heavy Compute Node ({HEAVY_MODEL}) online.")
        time.sleep(2)
    else:
        log(f"Failed to load Heavy Compute Node.")
        
    # 4. Benchmarking the new model
    log("\n[!] TELEMETRY: Validating compute node via hardware telemetry.")
    run_telemetry(HEAVY_MODEL, suite="math")
    
    # 5. Cool down
    log("\n[!] SYSTEM IDLE: Cooling down Compute Node. Returning to Lightweight Model...")
    swap_model(TINY_MODEL)
    
    print(f"\n{'='*60}")
    print(f"  ✅ AOS Workflow Complete. Returning to standby.")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
