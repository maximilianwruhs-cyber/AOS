import sqlite3
import os
from pathlib import Path
from telemetry_engine.awattar import get_current_price_c_kwh

DB_PATH = Path(__file__).parent.parent.parent / "data" / "aos_metrics.db"

def init_db():
    os.makedirs(DB_PATH.parent, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS model_metrics (
                model_name TEXT PRIMARY KEY,
                z_score REAL DEFAULT 0.5,
                avg_wattage REAL DEFAULT 150.0,
                runs INTEGER DEFAULT 0
            )
        """)
        # Insert defaults if empty
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM model_metrics")
        if cursor.fetchone()[0] == 0:
            from config import DEFAULT_MODEL
            conn.execute("INSERT INTO model_metrics (model_name, z_score, avg_wattage) VALUES (?, 0.4, 60.0)", (DEFAULT_MODEL,))
            conn.execute("INSERT INTO model_metrics (model_name, z_score, avg_wattage) VALUES (?, 0.9, 250.0)", ("deepseek-coder-33b-instruct",))

def log_inference(model: str, energy_joules: float, eval_score: float):
    """Shadow Evaluation Logger. Records energy and score, recalculating Z."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT z_score, avg_wattage, runs FROM model_metrics WHERE model_name = ?", (model,))
        row = cursor.fetchone()
        if not row:
            conn.execute("INSERT INTO model_metrics (model_name, z_score, avg_wattage, runs) VALUES (?, ?, ?, 1)", (model, eval_score, energy_joules))
        else:
            old_z, old_w, runs = row
            # moving average
            new_z = ((old_z * runs) + eval_score) / (runs + 1)
            new_w = ((old_w * runs) + energy_joules) / (runs + 1) # simple mapping
            conn.execute("UPDATE model_metrics SET z_score=?, avg_wattage=?, runs=? WHERE model_name=?", (new_z, new_w, runs + 1, model))

def select_best_model(complexity: str, tiny_model: str, heavy_model: str) -> str:
    """The Auction Block. Models bid their z_score against live electricity price."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Get live price (cents per kWh)
        price = get_current_price_c_kwh() or 10.0
        price_multiplier = max(1.0, price / 10.0) # Above 10 cents = amplifies grid penalty
        
        cursor.execute("SELECT model_name, z_score, avg_wattage FROM model_metrics WHERE model_name IN (?, ?)", (tiny_model, heavy_model))
        models = cursor.fetchall()
        
        # If DB miss, fallback
        if not models:
            return heavy_model if complexity == "heavy" else tiny_model
            
        best_model = tiny_model
        best_bid = -9999.0
        
        for name, z_score, wattage in models:
            # 1 $OBL = 1 Joule equivalent for this math
            obl_cost = (wattage) * price_multiplier
            
            utility = z_score * 1000  # Scale utility up to compete with raw joules
            if complexity == "heavy" and name == heavy_model:
                utility *= 2.0  # Heavy gets utility multiplier on complex tasks
            elif complexity == "tiny" and name == heavy_model:
                utility *= 0.2  # Heavy penalized for easy tasks
                
            bid = utility - obl_cost
            
            if bid > best_bid:
                best_bid = bid
                best_model = name
                
        return best_model
