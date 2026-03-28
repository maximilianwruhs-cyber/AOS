#!/usr/bin/env python3
"""
AOS VRAM Manager
Unloads current models and assigns target models to the active LLM backend.
"""
import requests
import sys
from pathlib import Path

from config import ACTIVE_BACKEND_URL


def swap_model(target_model_name: str, backend_url: str = None,
               gpu_offload: str = "max", ctx_len: int = 8192) -> bool:
    """Swap the active model on the LLM backend.
    
    Args:
        backend_url: Override the default backend URL. Fixes the frozen-import bug
                     where the URL wouldn't update after host-switching.
    """
    url = backend_url or ACTIVE_BACKEND_URL  # FIX Bug #1: accept runtime URL override
    print(f"🔄 [VRAM-MANAGER] Requesting swap to: {target_model_name} on {url}")
    try:
        current = requests.get(f"{url}/models", timeout=5).json()
        
        if "data" in current:
            for model in current["data"]:
                m_id = model.get("id")
                print(f"   🧹 Unloading: {m_id}")
                requests.post(f"{url}/internal/unload", json={"model": m_id}, timeout=30)
                
        print(f"   🚀 Loading: {target_model_name} (GPU: {gpu_offload}, CTX: {ctx_len})")
        payload = {
            "model": target_model_name,
            "gpu_offload": gpu_offload,
            "context_length": ctx_len
        }
        res = requests.post(f"{url}/internal/load", json=payload, timeout=120)
        res.raise_for_status()
        print("   ✅ VRAM Swap Complete.")
        return True
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Error: LM Studio Server unreachable at {url}")
        return False
    except Exception as e:
        print(f"   ❌ Error manipulating VRAM: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 vram_manager.py <model_name>")
        sys.exit(1)
    swap_model(sys.argv[1])
