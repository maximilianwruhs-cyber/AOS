"""
AOS Market Broker — Energy-Aware Model Auction
Uses EMA (Exponential Moving Average) for convergent z-scores
and ε-greedy exploration to prevent model starvation.
"""
import sqlite3
import os
import random
import logging
from pathlib import Path

logger = logging.getLogger("agenticos.market_broker")

DB_PATH = Path(__file__).parent.parent.parent / "data" / "aos_metrics.db"

# ─── Convergence Parameters ─────────────────────────────────────────────────
ALPHA = 0.15            # EMA decay: 15% new data, 85% history (~13 eval memory)
EPSILON = 0.10          # Exploration rate: 10% random model choice
MIN_STABLE_EVALS = 5   # Warm-up: models with <5 evals get forced exploration
_db_initialized = False  # FIX #35: skip repeated schema checks

# ─── Lazy import to avoid circular dependency ───────────────────────────────
_awattar_price_fn = None
def _get_price():
    global _awattar_price_fn
    if _awattar_price_fn is None:
        try:
            from aos.telemetry.awattar import get_current_price_c_kwh
            _awattar_price_fn = get_current_price_c_kwh
        except ImportError:
            _awattar_price_fn = lambda: None
    return _awattar_price_fn() or 10.0


def init_db():
    global _db_initialized
    if _db_initialized:  # FIX #35: skip after first successful init
        return
    os.makedirs(DB_PATH.parent, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS model_metrics (
                model_name TEXT PRIMARY KEY,
                z_score REAL DEFAULT 0.5,
                avg_quality REAL DEFAULT 0.5,
                avg_joules REAL DEFAULT 150.0,
                eval_runs INTEGER DEFAULT 0,
                total_runs INTEGER DEFAULT 0
            )
        """)
        # Migrate old schema if needed (add missing columns)
        try:
            conn.execute("SELECT avg_quality FROM model_metrics LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE model_metrics ADD COLUMN avg_quality REAL DEFAULT 0.5")
            conn.execute("ALTER TABLE model_metrics ADD COLUMN avg_joules REAL DEFAULT 150.0")
            conn.execute("ALTER TABLE model_metrics ADD COLUMN eval_runs INTEGER DEFAULT 0")
            conn.execute("ALTER TABLE model_metrics ADD COLUMN total_runs INTEGER DEFAULT 0")
            # FIX #23: removed broken migration referencing non-existent columns (avg_wattage, runs)
            logger.info("Migrated model_metrics schema to EMA format (columns added with defaults).")
    _db_initialized = True


def log_inference(model: str, energy_joules: float, eval_score: float = None):
    """
    Shadow Evaluation Logger with EMA convergence.
    
    - energy_joules: ALWAYS updated (100% of requests have RAPL data)
    - eval_score: Only updated when the LLM Judge ran (15% sample rate).
                  None means "only update energy, keep quality score unchanged."
    """
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT avg_quality, avg_joules, eval_runs, total_runs FROM model_metrics WHERE model_name = ?", (model,))
        row = cursor.fetchone()

        if not row:
            # First time this model is seen
            q = eval_score if eval_score is not None else 0.5
            j = energy_joules if energy_joules > 0 else 150.0  # FIX #24: don't seed with 0J (streaming)
            conn.execute(
                "INSERT INTO model_metrics (model_name, avg_quality, avg_joules, eval_runs, total_runs, z_score) VALUES (?, ?, ?, ?, 1, ?)",
                (model, q, j, 1 if eval_score is not None else 0, q / max(0.01, j))
            )
        else:
            old_q, old_j, eval_runs, total_runs = row

            # EMA for energy (skip when 0 = streaming/unmeasurable) — FIX #20
            if energy_joules > 0:
                new_j = (ALPHA * energy_joules) + ((1 - ALPHA) * old_j)
            else:
                new_j = old_j  # Keep existing average

            # EMA for quality (only when judge ran)
            new_q = old_q
            new_eval_runs = eval_runs
            if eval_score is not None:
                new_q = (ALPHA * eval_score) + ((1 - ALPHA) * old_q)
                new_eval_runs = eval_runs + 1

            # z-score = quality / joules (intelligence per watt)
            new_z = new_q / max(0.01, new_j)

            conn.execute(
                "UPDATE model_metrics SET avg_quality=?, avg_joules=?, z_score=?, eval_runs=?, total_runs=? WHERE model_name=?",
                (new_q, new_j, new_z, new_eval_runs, total_runs + 1, model)
            )


def select_best_model(complexity: str, tiny_model: str, heavy_model: str) -> str:
    """
    The Auction Block with ε-greedy exploration.
    
    - Warm-Up: models with <MIN_STABLE_EVALS get forced exploration
    - Exploration (ε=10%): random model choice to keep z-scores calibrated
    - Exploitation (90%): highest bid wins (utility - energy cost)
    """
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT model_name, z_score, avg_joules, eval_runs FROM model_metrics WHERE model_name IN (?, ?)",
            (tiny_model, heavy_model)
        )
        models = cursor.fetchall()

        # If DB miss, fallback
        if not models:
            return heavy_model if complexity == "heavy" else tiny_model

        # ── Warm-Up: Force exploration for under-evaluated models ──
        # FIX Bug #11: pick model with fewest evals, break ties randomly
        under_eval = [(name, eval_runs) for name, _, _, eval_runs in models if eval_runs < MIN_STABLE_EVALS]
        if under_eval:
            min_evals = min(e for _, e in under_eval)
            candidates = [name for name, e in under_eval if e == min_evals]
            chosen = random.choice(candidates)
            logger.info(f"Warm-up exploration: {chosen} ({min_evals}/{MIN_STABLE_EVALS} evals)")
            return chosen

        # ── ε-Greedy: 10% random exploration ──
        if random.random() < EPSILON:
            chosen = random.choice([tiny_model, heavy_model])
            logger.info(f"ε-greedy exploration: randomly chose {chosen}")
            return chosen

        # ── Exploitation: bid auction ──
        price = _get_price()
        price_multiplier = max(1.0, price / 10.0)

        best_model = tiny_model
        best_bid = -9999.0

        for name, z_score, avg_joules, _ in models:
            obl_cost = avg_joules * price_multiplier

            utility = z_score * 1000
            if complexity == "heavy" and name == heavy_model:
                utility *= 2.0
            elif complexity == "tiny" and name == heavy_model:
                utility *= 0.2

            bid = utility - obl_cost

            if bid > best_bid:
                best_bid = bid
                best_model = name

        return best_model
