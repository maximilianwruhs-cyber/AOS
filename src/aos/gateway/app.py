#!/usr/bin/env python3
"""
AgenticOS (AOS) - Reactive Sovereign Gateway v4.3.0
Slim application entrypoint — routes, auth, and triage live in submodules.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
import httpx
import uvicorn

from aos.config import ACTIVE_BACKEND_URL, ACTIVE_HOST_KEY
from aos.gateway.auth import verify_token
from aos.gateway import routes

logger = logging.getLogger("agenticos.gateway")
logging.basicConfig(level=logging.INFO, format="[AOS-GATEWAY] %(message)s")


@asynccontextmanager
async def lifespan(app):
    """Startup and shutdown logic for the AOS Gateway."""
    LM_STUDIO_URL = ACTIVE_BACKEND_URL
    routes.set_backend_url(LM_STUDIO_URL)

    print(f"\n{'='*60}")
    print(f"  🏛️ AGENTICOS (AOS) — SOVEREIGN GATEWAY v4.3.0")
    print(f"  Listening on Port 8000 | Backend: {LM_STUDIO_URL}")
    print(f"  Active Host: {ACTIVE_HOST_KEY}")
    print(f"  Shadow Evaluator: {routes.EVAL_SAMPLE_RATE*100:.0f}% LLM-Judge")
    print(f"{'='*60}\n")

    # Detect currently loaded model instead of force-swapping
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{LM_STUDIO_URL}/models", timeout=5.0)
            data = resp.json()
            models = data.get("data", [])
            if models:
                routes.CURRENT_MODEL = models[0].get("id", "unknown")
                logger.info(f"Detected active model: {routes.CURRENT_MODEL}")
            else:
                logger.info("No model loaded in LM Studio.")
    except Exception as e:
        logger.warning(f"Could not detect active model: {e}")

    yield
    logger.info("Shutting down AOS Gateway.")


app = FastAPI(title="AOS Reactive Gateway", version="4.3.0", lifespan=lifespan)

# ─── Register Routes ─────────────────────────────────────────────────────────
app.get("/health")(routes.health_check)
app.get("/v1/hosts")(routes.get_hosts)
app.post("/v1/hosts/switch")(routes.switch_host)
app.get("/v1/models")(routes.get_models)
app.post("/v1/chat/completions")(routes.chat_completions)
app.post("/v1/benchmark/run")(routes.benchmark_run)
app.get("/v1/leaderboard")(routes.leaderboard)


if __name__ == "__main__":
    uvicorn.run("aos.gateway.app:app", host="0.0.0.0", port=8000, reload=False)
