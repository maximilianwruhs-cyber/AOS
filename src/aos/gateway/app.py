#!/usr/bin/env python3
"""
AgenticOS (AOS) - Reactive Sovereign Gateway v4.2.0
Slim application entrypoint — routes, auth, and triage live in submodules.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
import uvicorn

from aos.config import ACTIVE_BACKEND_URL, ACTIVE_HOST_KEY
from aos.gateway.auth import verify_token
from aos.gateway import routes
from aos.tools.vram_manager import swap_model

logger = logging.getLogger("agenticos.gateway")
logging.basicConfig(level=logging.INFO, format="[AOS-GATEWAY] %(message)s")


@asynccontextmanager
async def lifespan(app):
    """Startup and shutdown logic for the AOS Gateway."""
    LM_STUDIO_URL = ACTIVE_BACKEND_URL
    routes.set_backend_url(LM_STUDIO_URL)

    print(f"\n{'='*60}")
    print(f"  🏛️ AGENTICOS (AOS) — SOVEREIGN GATEWAY v4.2.0")
    print(f"  Listening on Port 8000 | Backend: {LM_STUDIO_URL}")
    print(f"  Active Host: {ACTIVE_HOST_KEY}")
    print(f"  Shadow Evaluator: {routes.EVAL_SAMPLE_RATE*100:.0f}% LLM-Judge")
    print(f"{'='*60}\n")

    logger.info(f"Pre-loading idle model: {routes.TINY_MODEL}")
    if await asyncio.to_thread(swap_model, routes.TINY_MODEL, backend_url=LM_STUDIO_URL):
        routes.CURRENT_MODEL = routes.TINY_MODEL
    else:
        logger.info("WARNING: Failed to preload TINY_MODEL. LM Studio might be down.")
    yield
    logger.info("Shutting down AOS Gateway.")


app = FastAPI(title="AOS Reactive Gateway", version="4.2.0", lifespan=lifespan)

# ─── Register Routes ─────────────────────────────────────────────────────────
app.get("/health")(routes.health_check)
app.get("/v1/hosts")(routes.get_hosts)
app.post("/v1/hosts/switch")(routes.switch_host)
app.get("/v1/models")(routes.get_models)
app.post("/v1/chat/completions")(routes.chat_completions)


if __name__ == "__main__":
    uvicorn.run("aos.gateway.app:app", host="0.0.0.0", port=8000, reload=False)
