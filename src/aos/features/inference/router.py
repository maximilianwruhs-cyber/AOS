"""
AOS Features — Inference Router
FastAPI routes for /v1/chat/completions, /v1/models, /v1/switch-model, /health
"""
import asyncio
import json
import logging
import sqlite3

from fastapi import APIRouter, Request, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, StreamingResponse
import httpx

from aos.core.auth import verify_token
from aos.gateway.triage import assess_complexity
from aos.tools.vram_manager import swap_model
import aos.config as config
from aos.config import switch_active_host, list_hosts, load_remote_hosts
from aos.telemetry.market_broker import select_best_model
from aos.telemetry.energy_meter import EnergyMeter

from aos.features.inference.service import (
    TINY_MODEL, HEAVY_MODEL, EVAL_SAMPLE_RATE,
    CURRENT_MODEL, LM_STUDIO_URL,
    set_backend_url as _set_backend_url,
    shadow_evaluation, schedule_cooldown,
    write_stigmergy_note, log,
    _swap_lock,
)
import aos.features.inference.service as svc

logger = logging.getLogger("agenticos.inference.router")

router = APIRouter()


def set_backend_url(url: str):
    """Proxy to service-level backend URL setter."""
    _set_backend_url(url)


# ─── Health ───────────────────────────────────────────────────────────────────
@router.get("/health")
async def health_check():
    """Health check endpoint for monitoring — includes live model metrics."""
    backend_ok = False
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{svc.LM_STUDIO_URL}/models", timeout=3.0)
            backend_ok = resp.status_code == 200
    except Exception:
        pass

    from aos.config import ACTIVE_HOST_KEY
    from aos.telemetry.market_broker import DB_PATH, init_db
    from aos.telemetry.awattar import get_price_or_default

    energy_avg = None
    z_score = None
    quality = None
    if svc.CURRENT_MODEL:
        try:
            init_db()
            with sqlite3.connect(str(DB_PATH), timeout=2) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT avg_joules, z_score, avg_quality FROM model_metrics WHERE model_name = ?",
                    (svc.CURRENT_MODEL,)
                ).fetchone()
                if row:
                    energy_avg = row["avg_joules"]
                    z_score = row["z_score"]
                    quality = row["avg_quality"]
        except Exception:
            pass

    price_ct_kwh = get_price_or_default()
    meter = EnergyMeter()

    return JSONResponse(content={
        "status": "healthy",
        "current_model": svc.CURRENT_MODEL,
        "active_host": ACTIVE_HOST_KEY,
        "backend_url": svc.LM_STUDIO_URL,
        "backend_reachable": backend_ok,
        "shadow_eval_sample_rate": EVAL_SAMPLE_RATE,
        "energy_avg": energy_avg,
        "energy_source": "rapl" if meter.rapl_available else "estimate",
        "z_score": z_score,
        "quality": quality,
        "price_ct_kwh": price_ct_kwh,
    })


# ─── Models ───────────────────────────────────────────────────────────────────
@router.get("/v1/models")
async def get_models():
    """Proxy the models endpoint from the active LLM backend."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{svc.LM_STUDIO_URL}/models", timeout=5.0)
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Backend offline: {e}"})


# ─── Hosts ────────────────────────────────────────────────────────────────────
@router.get("/v1/hosts")
async def get_hosts():
    """List all available LLM backends and the active one."""
    hosts, active = list_hosts()
    return JSONResponse(content={"hosts": hosts, "active_host": active})


@router.post("/v1/hosts/switch")
async def switch_host(request: Request, _=Depends(verify_token)):
    """Switch the active LLM backend. Body: {"host": "aos-keller"}"""
    payload = await request.json()
    host_key = payload.get("host")
    if switch_active_host(host_key):
        new_url, _, _ = load_remote_hosts()
        svc.LM_STUDIO_URL = new_url
        log(f"🔄 Switched backend to: {host_key} ({svc.LM_STUDIO_URL})")
        return JSONResponse(content={"status": "switched", "active_host": host_key, "url": svc.LM_STUDIO_URL})
    return JSONResponse(status_code=400, content={"error": f"Unknown host: {host_key}"})


# ─── Switch Model ─────────────────────────────────────────────────────────────
@router.post("/v1/switch-model")
async def switch_model(request: Request):
    """Switch the active LLM model. Body: {"model_id": "qwen/qwen3.5-9b"}"""
    payload = await request.json()
    model_id = payload.get("model_id")

    if not model_id:
        return JSONResponse(status_code=400, content={"error": "Missing 'model_id' in request body."})

    previous_model = svc.CURRENT_MODEL
    log(f"🔄 Model switch requested: {previous_model} → {model_id}")

    async with svc._swap_lock:
        try:
            success = await asyncio.to_thread(swap_model, model_id, backend_url=svc.LM_STUDIO_URL)
            if success:
                svc.CURRENT_MODEL = model_id
                log(f"✅ Model switched to: {model_id}")
                return JSONResponse(content={
                    "status": "switched",
                    "model": model_id,
                    "previous_model": previous_model
                })
            else:
                log(f"❌ Model switch failed for: {model_id}")
                return JSONResponse(status_code=500, content={
                    "error": f"VRAM swap failed for model: {model_id}"
                })
        except Exception as e:
            log(f"❌ Model switch error: {e}")
            return JSONResponse(status_code=500, content={"error": f"Switch failed: {e}"})


# ─── Chat Completions ────────────────────────────────────────────────────────
@router.post("/v1/chat/completions")
async def chat_completions(request: Request, background_tasks: BackgroundTasks, _=Depends(verify_token)):
    payload = await request.json()
    messages = payload.get("messages", [])

    complexity = assess_complexity(messages)
    try:
        target_model = await asyncio.to_thread(select_best_model, complexity, TINY_MODEL, HEAVY_MODEL)
    except Exception as e:
        log(f"Market Broker failed: {e}. Defaulting to static escalation.")
        target_model = HEAVY_MODEL if complexity == "heavy" else TINY_MODEL

    log(f"Incoming Request | Complexity: {complexity.upper()} | Target: {target_model}")

    async with svc._swap_lock:
        if svc.CURRENT_MODEL != target_model:
            log(f"Swapping VRAM [{svc.CURRENT_MODEL} -> {target_model}]...")
            if await asyncio.to_thread(swap_model, target_model, backend_url=svc.LM_STUDIO_URL):
                svc.CURRENT_MODEL = target_model
            else:
                log("Swap failed. Proceeding with current model.")

    payload["model"] = svc.CURRENT_MODEL or target_model

    meter = EnergyMeter()
    meter.start()

    prompt_text = " ".join(m.get("content", "") for m in messages if isinstance(m.get("content"), str))

    if payload.get("stream", False):
        async def forward_stream():
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream("POST", f"{svc.LM_STUDIO_URL}/chat/completions", json=payload) as response:
                    async for chunk in response.aiter_bytes():
                        yield chunk
            energy = meter.stop()
            await schedule_cooldown()
            await shadow_evaluation(
                prompt_text, "[streaming]",
                target_model, complexity, energy["joules"]
            )

        return StreamingResponse(forward_stream(), media_type="text/event-stream")
    else:
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                resp = await client.post(f"{svc.LM_STUDIO_URL}/chat/completions", json=payload)
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


# ─── Benchmark Endpoint ──────────────────────────────────────────────────────
@router.post("/v1/benchmark/run")
async def benchmark_run(request: Request):
    """Run an Obolus benchmark suite against a model via the gateway."""
    from aos.telemetry.runner import run_benchmark, save_results
    from aos.telemetry.task_suite import list_suites

    payload = await request.json()
    suite = payload.get("suite", "full")
    model = payload.get("model", svc.CURRENT_MODEL)

    if not model:
        return JSONResponse(status_code=400, content={
            "error": "No model specified and none currently loaded."
        })

    available_suites = list_suites()
    if suite not in available_suites:
        return JSONResponse(status_code=400, content={
            "error": f"Unknown suite: {suite}. Available: {list(available_suites.keys())}"
        })

    try:
        log(f"Benchmark started: model={model}, suite={suite}")
        summary = await run_benchmark(
            model=model,
            suite=suite,
            ollama_url=svc.LM_STUDIO_URL,
            verbose=True
        )
        save_results(summary)
        log(f"Benchmark complete: z={summary['z_score']:.4f}, quality={summary['avg_quality']:.2%}")

        await asyncio.to_thread(
            write_stigmergy_note,
            "benchmark_runner",
            f"Suite_{suite}",
            f"# Benchmark Complete\n**Model**: {summary['model']}\n**Suite**: {summary['suite']}\n\n**Quality**: {summary['avg_quality']:.2%}\n**Z-Score**: {summary['z_score']:.4f}\n**Cost**: {summary['obl_cost']} OBL"
        )

        return JSONResponse(content={
            "status": "completed",
            "model": summary["model"],
            "suite": summary["suite"],
            "score": summary["avg_quality"],
            "z_score": summary["z_score"],
            "total_joules": summary["total_joules"],
            "obl_cost": summary["obl_cost"],
            "tokens_per_second": summary["tokens_per_second"],
            "scores_by_type": summary["scores_by_type"],
        })
    except Exception as e:
        log(f"Benchmark failed: {e}")
        return JSONResponse(status_code=500, content={"error": f"Benchmark failed: {e}"})


# ─── Benchmark Results ────────────────────────────────────────────────────────
@router.get("/v1/benchmark/results")
async def benchmark_results():
    """Return raw benchmark history from benchmark_results.json."""
    import json as _json
    results_path = config.DATA_DIR / "benchmark_results.json"

    if not results_path.exists():
        return JSONResponse(content={"data": [], "total": 0})

    try:
        with open(results_path) as f:
            raw = _json.load(f)

        data = []
        for run in raw:
            entry = {k: v for k, v in run.items() if k != "results"}
            entry["task_count"] = len(run.get("results", []))
            data.append(entry)

        return JSONResponse(content={"data": data, "total": len(data)})
    except Exception as e:
        log(f"Benchmark results read failed: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# ─── Leaderboard ──────────────────────────────────────────────────────────────
@router.get("/v1/leaderboard")
async def leaderboard():
    """Return ranked model metrics aggregated from benchmark results."""
    import json as _json
    results_path = config.DATA_DIR / "benchmark_results.json"

    if not results_path.exists():
        log("[LEADERBOARD] No benchmark_results.json found.")
        return JSONResponse(content={"data": []})

    try:
        with open(results_path) as f:
            raw = _json.load(f)
        log(f"[LEADERBOARD] Loaded {len(raw)} benchmark runs from file.")

        models: dict = {}
        for run in raw:
            model = run["model"]
            if model not in models:
                models[model] = {
                    "runs": [],
                    "suites": {},
                    "total_tokens": 0,
                    "total_joules": 0.0,
                    "total_time": 0.0,
                }
            m = models[model]
            m["runs"].append(run)
            m["total_tokens"] += run.get("total_tokens", 0)
            m["total_joules"] += run.get("total_joules", 0)
            m["total_time"] += run.get("total_time_s", 0)

            suite = run.get("suite", "unknown")
            if suite not in m["suites"]:
                m["suites"][suite] = {"scores": [], "z_scores": [], "tokens_per_sec": []}
            m["suites"][suite]["scores"].append(run.get("avg_quality", 0))
            m["suites"][suite]["z_scores"].append(run.get("z_score", 0))
            tps = run.get("tokens_per_second", 0)
            if tps > 0:
                m["suites"][suite]["tokens_per_sec"].append(tps)

        data = []
        for model_id, m in models.items():
            runs = m["runs"]
            n = len(runs)

            all_quality = [r.get("avg_quality", 0) for r in runs]
            all_z = [r.get("z_score", 0) for r in runs]
            valid_quality = [q for q in all_quality if q > 0]
            avg_quality = sum(valid_quality) / len(valid_quality) if valid_quality else 0
            best_z = max(all_z) if all_z else 0
            avg_joules = m["total_joules"] / n if n > 0 else 0
            avg_tps = m["total_tokens"] / max(0.01, m["total_time"])

            suite_breakdown = {}
            for suite_name, s in m["suites"].items():
                valid_s = [sc for sc in s["scores"] if sc > 0]
                suite_breakdown[suite_name] = {
                    "avg_quality": round(sum(valid_s) / len(valid_s), 4) if valid_s else 0,
                    "best_z": round(max(s["z_scores"]), 6) if s["z_scores"] else 0,
                    "runs": len(s["scores"]),
                    "avg_tps": round(sum(s["tokens_per_sec"]) / len(s["tokens_per_sec"]), 1) if s["tokens_per_sec"] else 0,
                }

            if best_z > 0.8:
                eff_class = "A+"
            elif best_z > 0.5:
                eff_class = "A"
            elif best_z > 0.2:
                eff_class = "B"
            elif best_z > 0.05:
                eff_class = "C"
            else:
                eff_class = "D"

            data.append({
                "model_id": model_id,
                "z_score": round(best_z, 6),
                "quality_score": round(avg_quality, 4),
                "joules_per_request": round(avg_joules, 2),
                "tokens_per_second": round(avg_tps, 1),
                "total_runs": n,
                "suites_tested": list(m["suites"].keys()),
                "suite_breakdown": suite_breakdown,
                "efficiency_class": eff_class,
            })

        data.sort(key=lambda x: x["z_score"], reverse=True)

        return JSONResponse(content={"data": data})
    except Exception as e:
        log(f"Leaderboard aggregation failed: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
