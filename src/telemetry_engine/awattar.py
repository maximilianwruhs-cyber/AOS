"""
AOS — AWattar Electricity Price Bridge
Fetches current spot price from AWattar AT API.
Used to weight z-score by real energy cost.
"""
import requests
from datetime import datetime, timezone


AWATTAR_URL = "https://api.awattar.at/v1/marketdata"


def get_current_price_c_kwh() -> float | None:
    """
    Fetch current electricity spot price in ¢/kWh from AWattar AT.
    Returns None if API is unreachable.
    """
    try:
        resp = requests.get(AWATTAR_URL, timeout=5)
        data = resp.json()
        now_ms = datetime.now(timezone.utc).timestamp() * 1000

        for entry in data.get("data", []):
            if entry["start_timestamp"] <= now_ms <= entry["end_timestamp"]:
                # API returns €/MWh → convert to ¢/kWh
                return entry["marketprice"] / 10.0

        # No matching period — return the latest entry
        entries = data.get("data", [])
        if entries:
            return entries[-1]["marketprice"] / 10.0

    except Exception:
        pass
    return None


def get_price_or_default(default_c_kwh: float = 25.0) -> float:
    """Get price with fallback to a default Austrian average."""
    price = get_current_price_c_kwh()
    return price if price is not None else default_c_kwh
