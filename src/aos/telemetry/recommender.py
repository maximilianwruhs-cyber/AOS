"""
AOS — Recommender
Analyzes benchmark results to recommend the best model per task type
and project costs at different scales using LIVE electricity pricing.
"""
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

import aos.config as config
from aos.telemetry.awattar import get_current_price_c_kwh, get_price_or_default


# Cloud API reference costs (USD per 1M tokens, approximate 2026 pricing)
CLOUD_COSTS = {
    "gpt-4o":       {"input": 2.50, "output": 10.00},
    "gpt-4o-mini":  {"input": 0.15, "output": 0.60},
    "claude-3.5":   {"input": 3.00, "output": 15.00},
    "gemini-1.5":   {"input": 1.25, "output": 5.00},
}


def load_results(path: Path = None) -> list:
    """Load benchmark results."""
    path = path or config.DATA_DIR / "benchmark_results.json"
    if not path.exists():
        return []
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def project_costs(joules_per_run: float, tokens_per_run: int,
                  queries_per_day: int, electricity_c_kwh: float) -> dict:
    """Project costs at different scales."""
    joules_per_day = joules_per_run * queries_per_day
    kwh_per_day = joules_per_day / 3_600_000
    eur_per_day = kwh_per_day * electricity_c_kwh / 100

    return {
        "queries_per_day": queries_per_day,
        "joules_per_day": round(joules_per_day, 2),
        "kwh_per_day": round(kwh_per_day, 6),
        "eur_per_day": round(eur_per_day, 6),
        "eur_per_month": round(eur_per_day * 30, 4),
        "eur_per_year": round(eur_per_day * 365, 2),
        "obl_per_day": round(joules_per_day / 3600, 4),
    }


def cloud_equivalent(tokens_per_run: int, queries_per_day: int) -> dict:
    """Estimate what the same workload would cost on cloud APIs."""
    total_tokens_per_day = tokens_per_run * queries_per_day
    comparisons = {}
    for provider, costs in CLOUD_COSTS.items():
        # Assume ~50% input, 50% output tokens
        avg_cost_per_token = (costs["input"] + costs["output"]) / 2 / 1_000_000
        daily_cost_usd = total_tokens_per_day * avg_cost_per_token
        comparisons[provider] = {
            "usd_per_day": round(daily_cost_usd, 4),
            "usd_per_month": round(daily_cost_usd * 30, 2),
            "usd_per_year": round(daily_cost_usd * 365, 2),
        }
    return comparisons


def recommend(results: list = None) -> Optional[dict]:
    """
    Analyze benchmark results and produce recommendations.
    Uses LIVE electricity pricing from aWATTar for cost projections.
    """
    results = results if results is not None else load_results()
    if not results:
        return None

    # Fetch live electricity price
    live_price = get_current_price_c_kwh()
    price_c_kwh = live_price if live_price is not None else 25.0
    price_is_live = live_price is not None

    # Find best model per task type by z-score
    best_by_type = {}
    best_overall = None
    best_overall_z = 0

    for run in results:
        model = run.get("model", "unknown")
        z = run.get("z_score", 0)
        quality = run.get("avg_quality", 0)
        joules = run.get("total_joules", 0)
        tokens = run.get("total_tokens", 0)
        tasks = run.get("total_tasks", 1)

        if z > best_overall_z:
            best_overall_z = z
            best_overall = {
                "model": model,
                "z_score": z,
                "quality": quality,
                "total_joules": joules,
                "total_tokens": tokens,
                "total_tasks": tasks,
            }

        for task_type, stats in run.get("scores_by_type", {}).items():
            type_z = stats.get("avg_score", 0) / max(0.001, joules)
            if task_type not in best_by_type or type_z > best_by_type[task_type].get("z", 0):
                best_by_type[task_type] = {
                    "model": model,
                    "z": type_z,
                    "quality": stats["avg_score"],
                    "tokens": stats.get("total_tokens", 0),
                }

    if not best_overall:
        return None

    # Cost projections using LIVE electricity price
    joules_per_query = best_overall["total_joules"] / max(1, best_overall["total_tasks"])
    tokens_per_query = best_overall["total_tokens"] // max(1, best_overall["total_tasks"])

    scales = {
        "personal": project_costs(joules_per_query, tokens_per_query, 50, price_c_kwh),
        "team": project_costs(joules_per_query, tokens_per_query, 500, price_c_kwh),
        "enterprise": project_costs(joules_per_query, tokens_per_query, 10000, price_c_kwh),
    }

    cloud = cloud_equivalent(tokens_per_query, 500)

    return {
        "best_overall": best_overall,
        "best_by_type": best_by_type,
        "cost_projections": scales,
        "cloud_comparison": cloud,
        "electricity_c_kwh": price_c_kwh,
        "price_is_live": price_is_live,
        "timestamp": datetime.now().isoformat(),
    }


def print_recommendation(rec: dict = None):
    """Pretty-print the recommendation with live energy pricing."""
    rec = rec or recommend()
    if not rec:
        print("\n  No benchmark results found. Run `aos bench --model <model> --suite full` first.\n")
        return

    best = rec["best_overall"]
    by_type = rec["best_by_type"]
    costs = rec["cost_projections"]
    cloud = rec["cloud_comparison"]
    price = rec["electricity_c_kwh"]
    is_live = rec["price_is_live"]
    timestamp = rec.get("timestamp", "")

    price_label = f"LIVE {price:.1f} ¢/kWh" if is_live else f"est. {price:.1f} ¢/kWh"
    price_icon = "⚡" if is_live else "📊"

    print()
    print(f"  ╔{'═'*62}╗")
    print(f"  ║  AOS RECOMMENDATION — Your Hardware Profile{' '*17}║")
    print(f"  ╠{'═'*62}╣")
    print(f"  ║{' '*62}║")
    print(f"  ║  {price_icon} Electricity: {price_label:<20}  {timestamp[:19]:<20} ║")
    print(f"  ║{' '*62}║")

    # Price context
    if is_live:
        if price < 0:
            print(f"  ║  🎉 NEGATIVE PRICE — Grid is paying YOU to use power!{' '*7}║")
        elif price < 5:
            print(f"  ║  🟢 Very cheap — great time for heavy inference{' '*12}║")
        elif price < 15:
            print(f"  ║  🟡 Normal pricing — standard operations{' '*19}║")
        elif price < 25:
            print(f"  ║  🟠 Above average — consider smaller models{' '*16}║")
        else:
            print(f"  ║  🔴 Expensive — minimize inference or defer tasks{' '*11}║")
        print(f"  ║{' '*62}║")

    print(f"  ║  🏆 Best Overall: {best['model']:<30} z={best['z_score']:.4f}  ║")
    print(f"  ║     Quality: {best['quality']:.1%}  |  Energy: {best['total_joules']:.1f}J total{' '*16}║")
    print(f"  ║{' '*62}║")

    if by_type:
        print(f"  ║  📊 Best per Task Type:{' '*38}║")
        for task_type, info in sorted(by_type.items()):
            model_short = info['model'][:25]
            print(f"  ║     {task_type:<12} → {model_short:<25} Q={info['quality']:.0%}     ║")
        print(f"  ║{' '*62}║")

    print(f"  ╠{'═'*62}╣")
    print(f"  ║  💰 Local Cost Projections @ {price_label:<20}{' '*11}║")
    print(f"  ║{' '*62}║")
    for scale_name, scale in costs.items():
        label = f"{scale_name} ({scale['queries_per_day']} q/day)"
        eur_mo = scale['eur_per_month']
        eur_yr = scale['eur_per_year']
        print(f"  ║  {label:<30} €{eur_mo:>8.4f}/mo  €{eur_yr:>8.2f}/yr  ║")
    print(f"  ║{' '*62}║")

    print(f"  ╠{'═'*62}╣")
    print(f"  ║  ☁️  Cloud API Comparison (500 queries/day){' '*17}║")
    print(f"  ║{' '*62}║")
    local_monthly = costs["team"]["eur_per_month"]
    for provider, cost in cloud.items():
        pct = (1 - local_monthly / max(0.01, cost["usd_per_month"])) * 100
        print(f"  ║  {provider:<15} ${cost['usd_per_month']:>8.2f}/mo   "
              f"(local saves {pct:>5.0f}%){' '*7}║")
    print(f"  ║{' '*62}║")
    print(f"  ║  💡 Local Ollama: €{local_monthly:.4f}/mo @ {price_label:<22}{' '*3}║")
    print(f"  ║{' '*62}║")
    print(f"  ╚{'═'*62}╝")
    print()
