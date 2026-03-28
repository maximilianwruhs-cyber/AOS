#!/usr/bin/env python3
"""
AOS Benchmark — Runner
Orchestrates benchmark runs: sends tasks to models, measures energy, scores output.
Uses async httpx for non-blocking inference I/O.
"""
import sys
import time
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime


import aos.config as config
import httpx
from aos.telemetry.task_suite import get_suite, list_suites
from aos.telemetry.evaluator import score_task
from aos.telemetry.energy_meter import EnergyMeter
from aos.telemetry.awattar import get_price_or_default


async def infer(client: httpx.AsyncClient, model: str, prompt: str,
                ollama_url: str, temperature: float = 0.3) -> tuple[str, int, float]:
    """Run inference asynchronously, returns (output, tokens_used, elapsed_seconds)."""
    start = time.time()
    try:
        resp = await client.post(
            f"{ollama_url}/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": 256
            },
            timeout=120.0,
        )
        data = resp.json()
        elapsed = time.time() - start

        choices = data.get("choices", [])
        output = choices[0].get("message", {}).get("content", "") if choices else ""
        usage = data.get("usage", {})
        tokens = usage.get("total_tokens", len(output.split()))

        return output, tokens, elapsed
    except Exception as e:
        return f"ERROR: {e}", 0, time.time() - start


async def run_benchmark(model: str, suite: str = "full", ollama_url: str = None,
                        temperature: float = 0.3, verbose: bool = True) -> dict:
    """Run a full benchmark suite against a model."""
    ollama_url = ollama_url or config.OLLAMA_URL
    tasks = get_suite(suite)
    timestamp = datetime.now().isoformat()
    meter = EnergyMeter()
    price_c_kwh = get_price_or_default()

    if verbose:
        print(f"\n{'='*60}")
        print(f"  AOS BENCHMARK — {model}")
        print(f"  Suite: {suite} ({len(tasks)} tasks) | {timestamp}")
        print(f"  Energy: {'RAPL (real watts)' if meter.rapl_available else 'estimate (no RAPL)'}")
        print(f"  Electricity: {price_c_kwh:.1f} ¢/kWh")
        print(f"{'='*60}\n")

    results = []
    total_tokens = 0
    total_time = 0.0
    total_score = 0.0
    total_joules = 0.0

    async with httpx.AsyncClient() as client:
        for i, task in enumerate(tasks):
            meter.start()
            output, tokens, elapsed = await infer(client, model, task["prompt"], ollama_url, temperature)
            energy = meter.stop()
            score = await score_task(task, output, judge_url=ollama_url, judge_model=model)

            total_tokens += tokens
            total_time += elapsed
            total_score += score
            total_joules += energy["joules"]

            result = {
                "task_id": task["id"],
                "type": task["type"],
                "score": score,
                "tokens": tokens,
                "elapsed_s": round(elapsed, 3),
                "joules": energy["joules"],
                "watts_avg": energy["watts_avg"],
                "output_preview": output[:100].replace("\n", " "),
            }
            results.append(result)

            if verbose:
                icon = "✅" if score >= 0.8 else "⚠️" if score > 0 else "❌"
                print(f"  {icon} [{task['type']:10}] {task['id']:12} score={score:.2f} "
                      f"tokens={tokens:4} {energy['joules']:6.2f}J {energy['watts_avg']:5.1f}W")

    n = len(tasks)
    avg_score = total_score / n if n > 0 else 0
    tokens_per_task = total_tokens / n if n > 0 else 0

    joules_per_token = total_joules / max(1, total_tokens)
    # z = quality / (joules × price_factor) — Intelligence per Watt per Euro
    price_factor = max(0.01, price_c_kwh / 25.0)  # normalize around 25 ¢/kWh
    z_score = avg_score / max(0.001, total_joules * price_factor) if avg_score > 0 else 0
    obl_cost = EnergyMeter.joules_to_obl(total_joules)
    eur_cost = EnergyMeter.joules_to_cost_eur(total_joules, price_c_kwh)

    summary = {
        "model": model,
        "suite": suite,
        "timestamp": timestamp,
        "temperature": temperature,
        "total_tasks": n,
        "avg_quality": round(avg_score, 4),
        "total_tokens": total_tokens,
        "avg_tokens_per_task": round(tokens_per_task, 1),
        "total_time_s": round(total_time, 2),
        "tokens_per_second": round(total_tokens / max(0.01, total_time), 1),
        "total_joules": round(total_joules, 4),
        "joules_per_token": round(joules_per_token, 6),
        "z_score": round(z_score, 6),
        "obl_cost": round(obl_cost, 6),
        "eur_cost": round(eur_cost, 8),
        "electricity_c_kwh": round(price_c_kwh, 2),
        "energy_source": meter.rapl_available and "rapl" or "estimate",
        "scores_by_type": {},
        "results": results,
    }

    # Per-type breakdown
    for task_type in ["math", "code", "factual", "reasoning"]:
        type_results = [r for r in results if r["type"] == task_type]
        if type_results:
            type_avg = sum(r["score"] for r in type_results) / len(type_results)
            summary["scores_by_type"][task_type] = {
                "avg_score": round(type_avg, 4),
                "count": len(type_results),
                "total_tokens": sum(r["tokens"] for r in type_results),
            }

    if verbose:
        print(f"\n{'─'*60}")
        print(f"  RESULTS: {model}")
        print(f"{'─'*60}")
        print(f"  Quality:    {avg_score:.2%}")
        print(f"  Energy:     {total_joules:.2f} J ({joules_per_token:.4f} J/tok)")
        print(f"  z-score:    {z_score:.6f} (quality / joule×price — higher is better)")
        print(f"  $OBL cost:  {obl_cost:.6f} OBL")
        print(f"  EUR cost:   €{eur_cost:.8f} @ {price_c_kwh:.1f} ¢/kWh")
        print(f"  Tokens:     {total_tokens} total ({tokens_per_task:.0f}/task)")
        print(f"  Speed:      {summary['tokens_per_second']:.1f} tok/s")
        print(f"  Time:       {total_time:.1f}s")
        print()
        for t, s in summary["scores_by_type"].items():
            print(f"    {t:12} {s['avg_score']:.2%} ({s['count']} tasks)")
        print(f"{'='*60}\n")

    return summary


def save_results(summary: dict):
    """Append results to data/benchmark_results.json."""
    path = config.DATA_DIR / "benchmark_results.json"
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    existing = []
    if path.exists():
        try:
            with open(path) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing = []

    existing.append(summary)
    with open(path, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
    print(f"  Results saved → {path}")


def compare_models(results_path: str = None):
    """Compare benchmark results across models."""
    path = Path(results_path) if results_path else config.DATA_DIR / "benchmark_results.json"
    if not path.exists():
        print("No benchmark results found. Run `obulus bench` first.")
        return

    with open(path) as f:
        results = json.load(f)

    print(f"\n{'='*80}")
    print(f"  AOS LEADERBOARD — Intelligence per Watt")
    print(f"{'='*80}")
    print(f"  {'Model':<22} {'Quality':>8} {'Energy':>8} {'z (Q/J)':>9} {'J/tok':>7} {'Suite':<6} {'When'}")
    print(f"  {'─'*22} {'─'*8} {'─'*8} {'─'*9} {'─'*7} {'─'*6} {'─'*19}")

    for r in sorted(results, key=lambda x: x.get("z_score", 0), reverse=True):
        ts = r["timestamp"][:19]
        joules = r.get("total_joules", 0)
        z = r.get("z_score", 0)
        jpt = r.get("joules_per_token", 0)
        print(f"  {r['model']:<22} {r['avg_quality']:>7.2%} {joules:>7.1f}J {z:>9.4f} "
              f"{jpt:>6.4f} {r['suite']:<6} {ts}")
    print(f"{'='*80}\n")


def main():
    parser = argparse.ArgumentParser(description="AOS Benchmark Runner")
    sub = parser.add_subparsers(dest="command")

    bench = sub.add_parser("bench", help="Run benchmark")
    bench.add_argument("--model", required=True, help="Ollama model name")
    bench.add_argument("--suite", default="full", choices=list(list_suites().keys()),
                       help="Task suite (default: full)")
    bench.add_argument("--ollama-url", default=None, help="Ollama URL")
    bench.add_argument("--temperature", type=float, default=0.3)
    bench.add_argument("--quiet", action="store_true")

    sub.add_parser("compare", help="Compare benchmark results")
    sub.add_parser("suites", help="List available suites")

    args = parser.parse_args()

    if args.command == "bench":
        summary = asyncio.run(run_benchmark(
            model=args.model,
            suite=args.suite,
            ollama_url=args.ollama_url,
            temperature=args.temperature,
            verbose=not args.quiet,
        ))
        save_results(summary)

    elif args.command == "compare":
        compare_models()

    elif args.command == "suites":
        print("\nAvailable suites:")
        for name, count in list_suites().items():
            print(f"  {name}: {count} tasks")
        print()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
