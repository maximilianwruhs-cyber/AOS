#!/usr/bin/env python3
"""
AgenticOS (AOS) - Reactive Sovereign Gateway v4.3.0
Slim application entrypoint — routes live in feature slices.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
import httpx
import uvicorn

from aos.config import ACTIVE_BACKEND_URL, ACTIVE_HOST_KEY
from aos.features.inference.router import router as inference_router
from aos.features.inference.service import set_backend_url
import aos.features.inference.service as svc

# Backward compat: keep routes importable for tests
from aos.gateway import routes

logger = logging.getLogger("agenticos.gateway")
logging.basicConfig(level=logging.INFO, format="[AOS-GATEWAY] %(message)s")


@asynccontextmanager
async def lifespan(app):
    """Startup and shutdown logic for the AOS Gateway."""
    LM_STUDIO_URL = ACTIVE_BACKEND_URL
    set_backend_url(LM_STUDIO_URL)
    # Also set on legacy routes for backward compat during migration
    routes.set_backend_url(LM_STUDIO_URL)

    print(f"\n{'='*60}")
    print(f"  🏛️ AGENTICOS (AOS) — SOVEREIGN GATEWAY v4.3.0")
    print(f"  Listening on Port 8000 | Backend: {LM_STUDIO_URL}")
    print(f"  Active Host: {ACTIVE_HOST_KEY}")
    print(f"  Shadow Evaluator: {svc.EVAL_SAMPLE_RATE*100:.0f}% LLM-Judge")
    print(f"{'='*60}\n")

    # Detect currently loaded model
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{LM_STUDIO_URL}/models", timeout=5.0)
            data = resp.json()
            models = data.get("data", [])
            if models:
                svc.CURRENT_MODEL = models[0].get("id", "unknown")
                routes.CURRENT_MODEL = svc.CURRENT_MODEL  # sync legacy
                logger.info(f"Detected active model: {svc.CURRENT_MODEL}")
            else:
                logger.info("No model loaded in LM Studio.")
    except Exception as e:
        logger.warning(f"Could not detect active model: {e}")

    # Ensure DB schema is migrated
    from aos.telemetry.market_broker import init_db
    init_db()
    logger.info("Database schema verified.")

    yield
    logger.info("Shutting down AOS Gateway.")


app = FastAPI(title="AOS Reactive Gateway", version="4.3.0", lifespan=lifespan)

# ─── Register Feature Routers ────────────────────────────────────────────────
app.include_router(inference_router)


if __name__ == "__main__":
    uvicorn.run("aos.gateway.app:app", host="0.0.0.0", port=8000, reload=False)
