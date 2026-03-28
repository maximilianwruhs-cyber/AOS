"""
AOS — AWattar Electricity Price Bridge
Fetches current spot price from AWattar AT API.
Used to weight z-score by real energy cost.
"""
import time
import requests
from datetime import datetime, timezone


AWATTAR_URL = "https://api.awattar.at/v1/marketdata"

# FIX Bug #14: Cache price for 15 min to avoid blocking event-loop on every request
_price_cache = {"value": None, "timestamp": 0.0}
CACHE_TTL = 900  # 15 minutes


def get_current_price_c_kwh() -> float | None:
    """
    Fetch current electricity spot price in ¢/kWh from AWattar AT.
    Returns cached value if fresh enough. Returns None only on first-ever failure.
    """
    now = time.monotonic()

    # Return cached value if still fresh
    if _price_cache["value"] is not None and (now - _price_cache["timestamp"]) < CACHE_TTL:
        return _price_cache["value"]

    try:
        resp = requests.get(AWATTAR_URL, timeout=3)  # FIX: 3s statt 5s
        data = resp.json()
        now_ms = datetime.now(timezone.utc).timestamp() * 1000

        price = None
        for entry in data.get("data", []):
            if entry["start_timestamp"] <= now_ms <= entry["end_timestamp"]:
                price = entry["marketprice"] / 10.0
                break

        if price is None:
            entries = data.get("data", [])
            if entries:
                price = entries[-1]["marketprice"] / 10.0

        if price is not None:
            _price_cache["value"] = price
            _price_cache["timestamp"] = now

        return price

    except Exception:
        pass
    return _price_cache["value"]  # FIX: stale cache better than None


def get_price_or_default(default_c_kwh: float = 25.0) -> float:
    """Get price with fallback to a default Austrian average."""
    price = get_current_price_c_kwh()
    return price if price is not None else default_c_kwh
