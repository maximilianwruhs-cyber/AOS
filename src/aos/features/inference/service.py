"""
AOS Features — Inference Service
Extracted business logic: shadow evaluation, model cooldown, state management.
"""
import asyncio
import os
import random
import logging

from aos.telemetry.market_broker import log_inference
from aos.telemetry.evaluator import score_generic_quality

logger = logging.getLogger("agenticos.inference")

# ─── Constants ────────────────────────────────────────────────────────────────
TINY_MODEL = "qwen2.5-0.5b-instruct"
HEAVY_MODEL = "qwen/qwen3.5-35b-a3b"
JUDGE_MODEL = HEAVY_MODEL
EVAL_SAMPLE_RATE = 0.15
MAX_CONCURRENT_EVALS = 1
IDLE_COOLDOWN_SECONDS = 300

# ─── Mutable State ────────────────────────────────────────────────────────────
CURRENT_MODEL = None
_cooldown_handle: asyncio.Task | None = None
_swap_lock = asyncio.Lock()
_eval_semaphore = asyncio.Semaphore(MAX_CONCURRENT_EVALS)

# Backend URL — set by app.py at lifespan
LM_STUDIO_URL = None


def set_backend_url(url: str):
    """Called by app.py to set the active backend URL."""
    global LM_STUDIO_URL
    LM_STUDIO_URL = url


def log(msg):
    """Shorthand logger."""
    logger.info(msg)


def write_stigmergy_note(agent_role: str, title: str, content: str):
    """Write an immutable Markdown note to the Obsidian Vault for stigmergic memory."""
    import datetime
    from pathlib import Path

    vault_dir = Path(
        os.environ.get(
            "AOS_VAULT_PATH",
            "/home/maximilian-wruhs/Dokumente/Playground/DevStack_v2/Obsidian_Vault/Evaluations"
        )
    )
    vault_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_title = "".join(c if c.isalnum() else "_" for c in title)
    filename = f"{timestamp}_{agent_role}_{safe_title}.md"
    file_path = vault_dir / filename

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"---\ntags: [{agent_role}, evaluation]\ndate: {timestamp}\n---\n\n{content}")
        log(f"[STIGMERGY] Wrote {filename} to vault")
    except Exception as e:
        log(f"[STIGMERGY] Failed to write note: {e}")


async def _do_cooldown():
    """Internal: waits then reverts to tiny model."""
    global CURRENT_MODEL
    from aos.tools.vram_manager import swap_model
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
            await asyncio.to_thread(
                write_stigmergy_note,
                "shadow_judge",
                f"Eval_{target_model}",
                f"# Shadow Evaluation\n**Model**: {target_model}\n**Score**: {eval_score:.2f}\n**Energy**: {energy_joules:.1f}J\n\n## Content Evaluated\n{response_text[:500]}"
            )
        else:
            log(f"[EVAL] Energy-only update: {target_model} | {energy_joules:.1f}J")

    except Exception as e:
        log(f"[EVAL] Shadow evaluation failed: {e}")
