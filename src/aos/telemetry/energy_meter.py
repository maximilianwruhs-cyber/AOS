"""
AOS — Energy Meter
Measures real energy consumption per inference via Intel RAPL or psutil fallback.
"""
import os
import time
from pathlib import Path


class EnergyMeter:
    """Measures real energy consumption using Intel RAPL counters."""

    RAPL_PATHS = [
        Path("/sys/class/powercap/intel-rapl:0/energy_uj"),      # Package 0 (whole CPU)
        Path("/sys/class/powercap/intel-rapl:1/energy_uj"),      # Package 1 (if multi-socket)
    ]

    def __init__(self):
        self.rapl_available = False
        self.active_paths = []
        self._start_uj = {}
        self._start_time = 0.0

        for p in self.RAPL_PATHS:
            if p.exists() and os.access(p, os.R_OK):
                self.active_paths.append(p)
                self.rapl_available = True

    def _read_uj(self) -> dict[str, int]:
        """Read current energy in microjoules from all RAPL counters."""
        readings = {}
        for p in self.active_paths:
            try:
                readings[str(p)] = int(p.read_text().strip())
            except (IOError, ValueError):
                readings[str(p)] = 0
        return readings

    def start(self):
        """Mark the start of an energy measurement."""
        self._start_uj = self._read_uj()
        self._start_time = time.monotonic()

    def stop(self) -> dict:
        """
        Stop measurement and return energy stats.

        Returns:
            dict with keys:
                joules: float — total energy consumed in joules
                watts_avg: float — average power draw in watts
                elapsed_s: float — wall clock seconds
                source: str — "rapl" or "estimate"
        """
        elapsed = time.monotonic() - self._start_time
        end_uj = self._read_uj()

        if self.rapl_available and self._start_uj:
            total_uj = 0
            for path_str, end_val in end_uj.items():
                start_val = self._start_uj.get(path_str, 0)
                # Handle counter overflow (RAPL counters are 32-bit on some systems)
                if end_val >= start_val:
                    total_uj += end_val - start_val
                else:
                    total_uj += (2**32 - start_val) + end_val

            joules = total_uj / 1_000_000
            watts = joules / max(0.001, elapsed)
            return {
                "joules": round(joules, 4),
                "watts_avg": round(watts, 2),
                "elapsed_s": round(elapsed, 3),
                "source": "rapl",
            }
        else:
            # Fallback: estimate from CPU TDP × load
            try:
                import psutil
                load = psutil.cpu_percent(interval=0) / 100.0
            except ImportError:
                load = 0.5
            est_tdp = 15.0  # Conservative estimate for mobile CPU
            watts = est_tdp * max(0.1, load)
            joules = watts * elapsed
            return {
                "joules": round(joules, 4),
                "watts_avg": round(watts, 2),
                "elapsed_s": round(elapsed, 3),
                "source": "estimate",
            }

    @staticmethod
    def joules_to_obl(joules: float) -> float:
        """Convert joules to $OBL (1 OBL = 1 Wh = 3600 J)."""
        return round(joules / 3600, 6)

    @staticmethod
    def joules_to_cost_eur(joules: float, price_c_kwh: float) -> float:
        """Convert joules to EUR cost given electricity price in ¢/kWh."""
        kwh = joules / 3_600_000
        return round(kwh * price_c_kwh / 100, 8)
