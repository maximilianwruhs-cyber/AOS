"""
AOS Gateway — Routes (BACKWARD COMPATIBILITY SHIM)
Real implementation moved to aos.features.inference.

This module re-exports everything so existing tests and imports
continue to work during the DDD migration. Will be DELETED in Phase 4.
"""
import asyncio
import os
import random
import logging

from fastapi import Request, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, StreamingResponse
import httpx

# Re-export from new feature modules
from aos.features.inference.service import (  # noqa: F401
    TINY_MODEL,
    HEAVY_MODEL,
    JUDGE_MODEL,
    EVAL_SAMPLE_RATE,
    MAX_CONCURRENT_EVALS,
    IDLE_COOLDOWN_SECONDS,
    CURRENT_MODEL,
    LM_STUDIO_URL,
    set_backend_url,
    shadow_evaluation,
    schedule_cooldown,
    write_stigmergy_note,
    _cooldown_handle,
    _swap_lock,
    _eval_semaphore,
    _do_cooldown,
    log,
)

# Re-export from feature router
from aos.features.inference.router import (  # noqa: F401
    health_check,
    get_hosts,
    switch_host,
    get_models,
    switch_model,
    chat_completions,
    benchmark_run,
    benchmark_results,
    leaderboard,
)

# Re-export from dependencies used by tests
from aos.gateway.auth import verify_token  # noqa: F401
from aos.gateway.triage import assess_complexity  # noqa: F401
from aos.tools.vram_manager import swap_model  # noqa: F401
from aos.config import switch_active_host, list_hosts, load_remote_hosts  # noqa: F401
import aos.config as config  # noqa: F401
from aos.telemetry.market_broker import select_best_model, log_inference  # noqa: F401
from aos.telemetry.evaluator import score_generic_quality, GENERIC_QUALITY_RUBRIC  # noqa: F401
from aos.telemetry.energy_meter import EnergyMeter  # noqa: F401

# Mutable state references — tests mutate these directly
import aos.features.inference.service as _svc

logger = logging.getLogger("agenticos.gateway")


def __getattr__(name):
    """Dynamic attribute access for mutable state that tests read/write."""
    if name == "CURRENT_MODEL":
        return _svc.CURRENT_MODEL
    if name == "LM_STUDIO_URL":
        return _svc.LM_STUDIO_URL
    if name == "_cooldown_handle":
        return _svc._cooldown_handle
    raise AttributeError(f"module 'aos.gateway.routes' has no attribute {name!r}")


def __setattr__(name, value):
    """Allow tests to set mutable state on the legacy routes module."""
    if name == "CURRENT_MODEL":
        _svc.CURRENT_MODEL = value
        return
    if name == "LM_STUDIO_URL":
        _svc.LM_STUDIO_URL = value
        return
    if name == "_cooldown_handle":
        _svc._cooldown_handle = value
        return
    # Fallback: set on this module's actual namespace
    globals()[name] = value
