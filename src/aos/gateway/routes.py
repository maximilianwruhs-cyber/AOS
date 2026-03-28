"""
AOS Gateway — API Route Definitions
All FastAPI route handlers extracted from the monolithic daemon.
"""
import asyncio
import random
import logging

from fastapi import Request, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, StreamingResponse
import httpx

from aos.gateway.auth import verify_token
from aos.gateway.triage import assess_complexity
from aos.tools.vram_manager import swap_model
from aos.config import switch_active_host, list_hosts, load_remote_hosts
from aos.telemetry.market_broker import select_best_model, log_inference
from aos.telemetry.evaluator import score_generic_quality, GENERIC_QUALITY_RUBRIC
from aos.telemetry.energy_meter import EnergyMeter

logger = logging.getLogger("agenticos.gateway")

# ─── Constants & State ────────────────────────────────────────────────────────
TINY_MODEL = "qwen2.5-0.5b-instruct"
HEAVY_MODEL = "qwen/qwen3.5-35b-a3b"

CURRENT_MODEL = None
IDLE_COOLDOWN_SECONDS = 300  # 5 minutes
_cooldown_handle: asyncio.Task | None = None
_swap_lock = asyncio.Lock()

# ─── Shadow Evaluator Config ─────────────────────────────────────────────────
JUDGE_MODEL = HEAVY_MODEL
EVAL_SAMPLE_RATE = 0.15
MAX_CONCURRENT_EVALS = 1
_eval_semaphore = asyncio.Semaphore(MAX_CONCURRENT_EVALS)

# Will be set by app.py at lifespan
LM_STUDIO_URL = None


def set_backend_url(url: str):
    """Called by app.py to set the active backend URL."""
    global LM_STUDIO_URL
    LM_STUDIO_URL = url


def log(msg):
    logger.info(msg)


async def _do_cooldown():
    """Internal: waits then reverts to tiny model."""
    global CURRENT_MODEL
    log(f"Cooldown initiated. Waiting {IDLE_COOLDOWN_SECONDS}s...")
    await asyncio.sleep(IDLE_COOLDOWN_SECONDS)
    log(f"Cooldown complete. System idle. Reverting to {TINY_MODEL}.")
    if await asyncio.to_thread(swap_model, TINY_MODEL, backend_url=LM_STUDIO_URL):
        CURRENT_MODEL = TINY_MODEL


async def schedule_cooldown():
    """Debounced cooldown: cancels previous timer before starting a new one."""
    global _cooldown_handle
    if _cooldown_handle and not _cooldown_handle.done():
        _cooldown_handle.cancel()
    _cooldown_handle = asyncio.create_task(_do_cooldown())


# ─── Shadow Evaluator ────────────────────────────────────────────────────────
async def shadow_evaluation(prompt: str, response_text: str, target_model: str,
                            complexity: str, energy_joules: float):
    """
    Background task: grades the response quality asynchronously.
    Strategy: Sampled HEAVY-Judge with zero-compute fallbacks.
    """
    try:
        eval_score = None

        if not response_text.strip():
            log(f"[EVAL] {target_model}: Empty response → score 0.1")
            eval_score = 0.1
        elif len(response_text.strip()) < 10 and len(prompt) > 50:
            log(f"[EVAL] {target_model}: Suspiciously short response → score 0.1")
            eval_score = 0.1

        if eval_score is None and random.random() <= EVAL_SAMPLE_RATE:
            if _eval_semaphore.locked():
                log("[EVAL] Queue full — skipping Judge to prioritize user requests.")
            else:
                async with _eval_semaphore:
                    log(f"[EVAL] Running LLM-Judge for {target_model} ({energy_joules:.1f}J)...")
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

        log_inference(target_model, energy_joules, eval_score)

        if eval_score is not None:
            log(f"[EVAL] Logged: {target_model} | Score: {eval_score:.2f} | Energy: {energy_joules:.1f}J")
        else:
            log(f"[EVAL] Energy-only update: {target_model} | {energy_joules:.1f}J")

    except Exception as e:
        log(f"[EVAL] Shadow evaluation failed: {e}")


# ─── Route Handlers ──────────────────────────────────────────────────────────

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
        "active_host": None,  # set dynamically
        "backend_url": LM_STUDIO_URL,
        "backend_reachable": backend_ok,
        "shadow_eval_sample_rate": EVAL_SAMPLE_RATE,
    })


async def get_hosts():
    """List all available LLM backends and the active one."""
    hosts, active = list_hosts()
    return JSONResponse(content={"hosts": hosts, "active_host": active})


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


async def get_models():
    """Proxy the models endpoint from the active LLM backend."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{LM_STUDIO_URL}/models", timeout=5.0)
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Backend offline: {e}"})


async def chat_completions(request: Request, background_tasks: BackgroundTasks, _=Depends(verify_token)):
    global CURRENT_MODEL
    payload = await request.json()
    messages = payload.get("messages", [])

    # 1. Triage
    complexity = assess_complexity(messages)
    try:
        target_model = await asyncio.to_thread(select_best_model, complexity, TINY_MODEL, HEAVY_MODEL)
    except Exception as e:
        log(f"Market Broker failed: {e}. Defaulting to static escalation.")
        target_model = HEAVY_MODEL if complexity == "heavy" else TINY_MODEL

    log(f"Incoming Request | Complexity: {complexity.upper()} | Target: {target_model}")

    # 2. VRAM Swap if needed
    async with _swap_lock:
        if CURRENT_MODEL != target_model:
            log(f"Swapping VRAM [{CURRENT_MODEL} -> {target_model}]...")
            if await asyncio.to_thread(swap_model, target_model, backend_url=LM_STUDIO_URL):
                CURRENT_MODEL = target_model
            else:
                log("Swap failed. Proceeding with current model.")

    payload["model"] = CURRENT_MODEL or target_model

    # 3. Start energy measurement BEFORE inference
    meter = EnergyMeter()
    meter.start()

    prompt_text = " ".join(m.get("content", "") for m in messages if isinstance(m.get("content"), str))

    # 4. Forward to backend
    if payload.get("stream", False):
        async def forward_stream():
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream("POST", f"{LM_STUDIO_URL}/chat/completions", json=payload) as response:
                    async for chunk in response.aiter_bytes():
                        yield chunk

        meter.stop()
        await schedule_cooldown()
        background_tasks.add_task(
            shadow_evaluation, prompt_text, "[streaming]",
            target_model, complexity, 0.0
        )
        return StreamingResponse(forward_stream(), media_type="text/event-stream")
    else:
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                resp = await client.post(f"{LM_STUDIO_URL}/chat/completions", json=payload)
                energy = meter.stop()

                resp_data = resp.json()
                response_text = ""
                choices = resp_data.get("choices", [])
                if choices:
                    response_text = choices[0].get("message", {}).get("content", "")

                await schedule_cooldown()
                background_tasks.add_task(
                    shadow_evaluation, prompt_text, response_text,
                    target_model, complexity, energy["joules"]
                )
                return JSONResponse(status_code=resp.status_code, content=resp_data)
            except Exception as e:
                meter.stop()
                return JSONResponse(status_code=500, content={"error": f"Backend failed: {e}"})
