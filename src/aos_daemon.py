#!/usr/bin/env python3
"""
AgenticOS (AOS) - Reactive Sovereign Gateway v4.2.0
Routes OpenAI-compatible API requests dynamically based on payload complexity.
Shadow Evaluator: Sampled HEAVY-Judge with EMA convergence.
"""
import time
import sys
import asyncio
import json
import random
import re
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks, Depends, HTTPException, Header
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
import uvicorn

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from tools.vram_manager import swap_model
from config import DEFAULT_MODEL, ACTIVE_BACKEND_URL, FALLBACK_BACKEND_URL, ACTIVE_HOST_KEY, AOS_API_KEY
from config import switch_active_host, list_hosts, load_remote_hosts
from telemetry_engine.market_broker import select_best_model, log_inference
from telemetry_engine.evaluator import score_generic_quality, GENERIC_QUALITY_RUBRIC
from telemetry_engine.energy_meter import EnergyMeter

logger = logging.getLogger("agenticos.gateway")
logging.basicConfig(level=logging.INFO, format="[AOS-GATEWAY] %(message)s")

# ─── Constants & State ────────────────────────────────────────────────────────
TINY_MODEL = "qwen2.5-0.5b-instruct"
HEAVY_MODEL = "qwen/qwen3.5-35b-a3b"
LM_STUDIO_URL = ACTIVE_BACKEND_URL

CURRENT_MODEL = None
IDLE_COOLDOWN_SECONDS = 300  # 5 minutes
_cooldown_handle: asyncio.Task | None = None  # debounce handle
_swap_lock = asyncio.Lock()  # FIX #39: serialize concurrent VRAM swaps

# ─── Shadow Evaluator Config ─────────────────────────────────────────────────
JUDGE_MODEL = HEAVY_MODEL
EVAL_SAMPLE_RATE = 0.15        # Only 15% of requests get LLM-as-Judge
MAX_CONCURRENT_EVALS = 1       # Backpressure: protect VRAM from eval queue floods
_eval_semaphore = asyncio.Semaphore(MAX_CONCURRENT_EVALS)

def log(msg):
    logger.info(msg)

async def verify_token(authorization: str = Header(None)):
    """Bearer Token auth. Skipped if AOS_API_KEY is not set (dev mode)."""
    if not AOS_API_KEY:
        return
    if not authorization or authorization != f"Bearer {AOS_API_KEY}":
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

# ─── Helper Functions ─────────────────────────────────────────────────────────
def assess_complexity(messages: list) -> str:
    """Triage the payload complexity."""
    full_text = " ".join([m.get("content", "") for m in messages if isinstance(m.get("content"), str)])
    heavy_keywords = ["write code", "analyze", "explain", "python", "javascript", "c++", "refactor", "debug", "architect"]
    if len(full_text) > 1000:
        return "heavy"
    for kw in heavy_keywords:
        if kw in full_text.lower():
            return "heavy"
    return "tiny"

async def _do_cooldown():
    """Internal: waits then reverts to tiny model."""
    global CURRENT_MODEL
    log(f"Cooldown initiated. Waiting {IDLE_COOLDOWN_SECONDS}s...")
    await asyncio.sleep(IDLE_COOLDOWN_SECONDS)
    log(f"Cooldown complete. System idle. Reverting to {TINY_MODEL}.")
    # FIX Bug #15: run sync swap_model in thread pool to not block event loop
    if await asyncio.to_thread(swap_model, TINY_MODEL, backend_url=LM_STUDIO_URL):
        CURRENT_MODEL = TINY_MODEL

# FIX Bug #3: schedule_cooldown is now async
async def schedule_cooldown():
    """Debounced cooldown: cancels previous timer before starting a new one."""
    global _cooldown_handle
    if _cooldown_handle and not _cooldown_handle.done():
        _cooldown_handle.cancel()
    _cooldown_handle = asyncio.create_task(_do_cooldown())

# ─── Shadow Evaluator (Real Logic) ───────────────────────────────────────────
async def shadow_evaluation(prompt: str, response_text: str, target_model: str,
                            complexity: str, energy_joules: float):
    """
    Background task: grades the response quality asynchronously.
    
    Strategy: Sampled HEAVY-Judge with zero-compute fallbacks.
    - 100% of requests: update RAPL energy in market_broker
    - 15% of requests: run LLM-as-Judge for quality score
    - Zero-compute heuristics catch obvious failures before wasting GPU
    """
    try:
        eval_score = None

        # 1. Zero-compute heuristics (catch garbage before wasting GPU)
        if not response_text.strip():
            log(f"[EVAL] {target_model}: Empty response → score 0.1")
            eval_score = 0.1
        elif len(response_text.strip()) < 10 and len(prompt) > 50:
            log(f"[EVAL] {target_model}: Suspiciously short response → score 0.1")
            eval_score = 0.1

        # 2. LLM-as-Judge with fractional sampling
        if eval_score is None and random.random() <= EVAL_SAMPLE_RATE:
            # Load shedding: skip if semaphore is already locked (user requests go first)
            if _eval_semaphore.locked():
                log("[EVAL] Queue full — skipping Judge to prioritize user requests.")
            else:
                async with _eval_semaphore:
                    log(f"[EVAL] Running LLM-Judge for {target_model} ({energy_joules:.1f}J)...")

                    # Blind evaluation: no model name in the judge prompt
                    judge_input = (
                        f"Evaluate the AI response to the User Prompt.\n\n"
                        f"USER PROMPT:\n{prompt[:500]}\n\n"
                        f"AI RESPONSE:\n{response_text[:800]}"
                    )

                    try:
                        raw_score = await score_generic_quality(
                            output=judge_input,
                            judge_url=LM_STUDIO_URL,
                            judge_model=JUDGE_MODEL
                        )
                        eval_score = max(0.0, min(1.0, float(raw_score)))
                        log(f"[EVAL] {target_model} scored {eval_score:.2f}")
                    except Exception as e:
                        log(f"[EVAL] Judge failed: {e}. Skipping quality update.")

        # 3. Update market broker (energy ALWAYS, quality only when scored)
        log_inference(target_model, energy_joules, eval_score)

        if eval_score is not None:
            log(f"[EVAL] Logged: {target_model} | Score: {eval_score:.2f} | Energy: {energy_joules:.1f}J")
        else:
            log(f"[EVAL] Energy-only update: {target_model} | {energy_joules:.1f}J")

    except Exception as e:
        log(f"[EVAL] Shadow evaluation failed: {e}")


# ─── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app):
    """Startup and shutdown logic for the AOS Gateway."""
    global CURRENT_MODEL
    print(f"\n{'='*60}")
    print(f"  🏛️ AGENTICOS (AOS) — SOVEREIGN GATEWAY v4.2.0")
    print(f"  Listening on Port 8000 | Backend: {LM_STUDIO_URL}")
    print(f"  Active Host: {ACTIVE_HOST_KEY}")
    print(f"  Shadow Evaluator: {EVAL_SAMPLE_RATE*100:.0f}% LLM-Judge | EMA α={0.15}")
    print(f"{'='*60}\n")
    log(f"Pre-loading idle model: {TINY_MODEL}")
    # FIX Bug #15: run sync swap_model in thread pool
    if await asyncio.to_thread(swap_model, TINY_MODEL, backend_url=LM_STUDIO_URL):
        CURRENT_MODEL = TINY_MODEL
    else:
        log("WARNING: Failed to preload TINY_MODEL. LM Studio might be down.")
    yield
    log("Shutting down AOS Gateway.")

app = FastAPI(title="AOS Reactive Gateway", version="4.2.0", lifespan=lifespan)

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    backend_ok = False
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{LM_STUDIO_URL}/models", timeout=3.0)
            backend_ok = resp.status_code == 200
    except Exception:
        pass
    return JSONResponse(content={
        "status": "healthy",
        "current_model": CURRENT_MODEL,
        "active_host": ACTIVE_HOST_KEY,
        "backend_url": LM_STUDIO_URL,
        "backend_reachable": backend_ok,
        "shadow_eval_sample_rate": EVAL_SAMPLE_RATE,
    })

@app.get("/v1/hosts")
async def get_hosts():
    """List all available LLM backends and the active one."""
    hosts, active = list_hosts()
    return JSONResponse(content={"hosts": hosts, "active_host": active})

@app.post("/v1/hosts/switch")
async def switch_host(request: Request, _=Depends(verify_token)):
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
async def chat_completions(request: Request, background_tasks: BackgroundTasks, _=Depends(verify_token)):
    global CURRENT_MODEL
    payload = await request.json()
    messages = payload.get("messages", [])
    
    # 1. Triage
    complexity = assess_complexity(messages)
    try:
        # FIX #34: don't block event loop with sync SQLite
        target_model = await asyncio.to_thread(select_best_model, complexity, TINY_MODEL, HEAVY_MODEL)
    except Exception as e:
        log(f"Market Broker failed: {e}. Defaulting to static escalation.")
        target_model = HEAVY_MODEL if complexity == "heavy" else TINY_MODEL
    
    log(f"Incoming Request | Complexity: {complexity.upper()} | Target: {target_model}")
    
    # 2. VRAM Swap if needed — FIX Bug #1: pass LM_STUDIO_URL
    async with _swap_lock:  # FIX #39: prevent concurrent VRAM swaps
        if CURRENT_MODEL != target_model:
            log(f"Swapping VRAM [{CURRENT_MODEL} -> {target_model}]...")
            if await asyncio.to_thread(swap_model, target_model, backend_url=LM_STUDIO_URL):  # FIX #15
                CURRENT_MODEL = target_model
            else:
                log("Swap failed. Proceeding with current model.")
            
    # Modify payload model to match the hardware backend
    payload["model"] = CURRENT_MODEL or target_model  # FIX #29: fallback if startup swap failed

    # 3. Start energy measurement BEFORE inference
    meter = EnergyMeter()
    meter.start()
    
    # Extract prompt for Shadow Evaluator
    prompt_text = " ".join(m.get("content", "") for m in messages if isinstance(m.get("content"), str))

    # 4. Forward to backend
    if payload.get("stream", False):
        async def forward_stream():
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream("POST", f"{LM_STUDIO_URL}/chat/completions", json=payload) as response:
                    async for chunk in response.aiter_bytes():
                        yield chunk

        # FIX Bug #20: Energy can't be measured for streaming (meter.stop() here
        # would measure 0J since inference hasn't started yet). Skip energy.
        meter.stop()  # cleanup only
        await schedule_cooldown()
        background_tasks.add_task(
            shadow_evaluation, prompt_text, "[streaming]",
            target_model, complexity, 0.0  # 0 = unmeasurable
        )
        return StreamingResponse(forward_stream(), media_type="text/event-stream")
    else:
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                resp = await client.post(f"{LM_STUDIO_URL}/chat/completions", json=payload)
                energy = meter.stop()  # Stop BEFORE shadow eval (don't count eval joules)
                
                # Extract response text for Shadow Evaluator
                resp_data = resp.json()
                response_text = ""
                choices = resp_data.get("choices", [])
                if choices:
                    response_text = choices[0].get("message", {}).get("content", "")

                await schedule_cooldown()  # FIX Bug #3: await
                background_tasks.add_task(
                    shadow_evaluation, prompt_text, response_text,
                    target_model, complexity, energy["joules"]
                )
                return JSONResponse(status_code=resp.status_code, content=resp_data)
            except Exception as e:
                meter.stop()  # Clean up meter
                return JSONResponse(status_code=500, content={"error": f"Backend failed: {e}"})

if __name__ == "__main__":
    uvicorn.run("aos_daemon:app", host="0.0.0.0", port=8000, reload=False)
