#!/usr/bin/env python3
"""
AgenticOS (AOS) - Reactive Sovereign Gateway
Routes OpenAI-compatible API requests dynamically based on payload complexity.
"""
import time
import sys
import asyncio
import json
from pathlib import Path
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
import uvicorn

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from tools.vram_manager import swap_model
from config import DEFAULT_MODEL, ACTIVE_BACKEND_URL, FALLBACK_BACKEND_URL, ACTIVE_HOST_KEY
from config import switch_active_host, list_hosts, load_remote_hosts
from telemetry_engine.market_broker import select_best_model, log_inference

app = FastAPI(title="AOS Reactive Gateway", version="4.0.0")

TINY_MODEL = "qwen2.5-0.5b-instruct"
HEAVY_MODEL = "qwen/qwen3.5-35b-a3b"
LM_STUDIO_URL = ACTIVE_BACKEND_URL

# State tracking
CURRENT_MODEL = None
IDLE_COOLDOWN_SECONDS = 300  # 5 minutes

def log(msg):
    print(f"[AOS-GATEWAY] {msg}")

def assess_complexity(messages: list) -> str:
    """Triage the payload complexity."""
    full_text = " ".join([m.get("content", "") for m in messages if isinstance(m.get("content"), str)])
    
    # Heuristics for heavy model
    heavy_keywords = ["write code", "analyze", "explain", "python", "javascript", "c++", "refactor", "debug", "architect"]
    
    if len(full_text) > 1000:
        return "heavy"
        
    for kw in heavy_keywords:
        if kw in full_text.lower():
            return "heavy"
            
    return "tiny"

async def cooldown_task():
    """Swaps back to tiny model after IDLE_COOLDOWN_SECONDS of inactivity."""
    global CURRENT_MODEL
    log(f"Cooldown initiated. Waiting {IDLE_COOLDOWN_SECONDS}s...")
    await asyncio.sleep(IDLE_COOLDOWN_SECONDS)
    log(f"Cooldown complete. System idle. Reverting to {TINY_MODEL}.")
    if swap_model(TINY_MODEL):
        CURRENT_MODEL = TINY_MODEL

async def shadow_evaluation(model: str, complexity: str):
    """Background task to grade the response and track bounds asynchronously."""
    import random
    # In a full production deployment, this invokes an LLM-as-judge loop 
    # to read the last N prompts. For convergence simulation:
    log("Running Shadow Evaluator...")
    simulated_joules = 50.0 if model == TINY_MODEL else 250.0
    quality = random.uniform(0.8, 1.0)
    
    # Tiny model flounders on heavy code tasks, degrading its z-score over time
    if model == TINY_MODEL and complexity == "heavy":
        quality = random.uniform(0.2, 0.5)
        
    log_inference(model, simulated_joules, quality)
    log(f"Shadow Evaluator Logged: {model} | Acc: {quality:.2f} | J: {simulated_joules}")

@app.on_event("startup")
async def startup_event():
    global CURRENT_MODEL
    print(f"\n{'='*60}")
    print(f"  🏛️ AGENTICOS (AOS) — SOVEREIGN GATEWAY")
    print(f"  Listening on Port 8000 | Backend: {LM_STUDIO_URL}")
    print(f"  Active Host: {ACTIVE_HOST_KEY}")
    print(f"{'='*60}\n")
    log(f"Pre-loading idle model: {TINY_MODEL}")
    if swap_model(TINY_MODEL):
        CURRENT_MODEL = TINY_MODEL
    else:
        log("WARNING: Failed to preload TINY_MODEL. LM Studio might be down.")

@app.get("/v1/hosts")
async def get_hosts():
    """List all available LLM backends and the active one."""
    hosts, active = list_hosts()
    return JSONResponse(content={"hosts": hosts, "active_host": active})

@app.post("/v1/hosts/switch")
async def switch_host(request: Request):
    """Switch the active LLM backend. Body: {"host": "aos-keller"}"""
    global LM_STUDIO_URL
    payload = await request.json()
    host_key = payload.get("host")
    if switch_active_host(host_key):
        new_url, _, _ = load_remote_hosts()
        LM_STUDIO_URL = new_url
        log(f"🔄 Switched backend to: {host_key} ({LM_STUDIO_URL})")
        return JSONResponse(content={"status": "switched", "active_host": host_key, "url": LM_STUDIO_URL})
    return JSONResponse(status_code=400, content={"error": f"Unknown host: {host_key}"})

@app.get("/v1/models")
async def get_models():
    """Proxy the models endpoint from the active LLM backend."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{LM_STUDIO_URL}/models", timeout=5.0)
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Backend offline: {e}"})

@app.post("/v1/chat/completions")
async def chat_completions(request: Request, background_tasks: BackgroundTasks):
    global CURRENT_MODEL
    payload = await request.json()
    messages = payload.get("messages", [])
    
    # 1. Triage
    complexity = assess_complexity(messages)
    try:
        target_model = select_best_model(complexity, TINY_MODEL, HEAVY_MODEL)
    except Exception as e:
        log(f"Market Broker failed: {e}. Defaulting to static escalation.")
        target_model = HEAVY_MODEL if complexity == "heavy" else TINY_MODEL
    
    log(f"Incoming Request | Complexity: {complexity.upper()} | Target: {target_model}")
    
    # 2. VRAM Swap if needed
    if CURRENT_MODEL != target_model:
        log(f"Swapping VRAM [{CURRENT_MODEL} -> {target_model}]...")
        if swap_model(target_model):
            CURRENT_MODEL = target_model
        else:
            log("Swap failed. Proceeding with current model.")
            
    # Modify payload model to match the hardware backend's expected name if strict
    payload["model"] = CURRENT_MODEL
    
    # 3. Forward to backend
    async def forward_stream():
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream("POST", f"{LM_STUDIO_URL}/chat/completions", json=payload) as response:
                async for chunk in response.aiter_bytes():
                    yield chunk

    # Handle streaming vs non-streaming
    if payload.get("stream", False):
        background_tasks.add_task(cooldown_task)
        background_tasks.add_task(shadow_evaluation, target_model, complexity)
        return StreamingResponse(forward_stream(), media_type="text/event-stream")
    else:
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                resp = await client.post(f"{LM_STUDIO_URL}/chat/completions", json=payload)
                background_tasks.add_task(cooldown_task)
                background_tasks.add_task(shadow_evaluation, target_model, complexity)
                return JSONResponse(status_code=resp.status_code, content=resp.json())
            except Exception as e:
                return JSONResponse(status_code=500, content={"error": f"Backend failed: {e}"})

if __name__ == "__main__":
    uvicorn.run("aos_daemon:app", host="0.0.0.0", port=8000, reload=False)
