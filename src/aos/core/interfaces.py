"""
AOS Core — Interface Protocols
Defines contracts for cross-feature dependency injection.
Features depend on these protocols, not on concrete implementations.
This eliminates circular imports and enables testability.
"""
from typing import Protocol, Optional, runtime_checkable


@runtime_checkable
class PricingProvider(Protocol):
    """Contract for energy pricing data sources (e.g., aWATTar API)."""

    def get_current_price_c_kwh(self) -> Optional[float]:
        """Return current electricity price in ct/kWh, or None if unavailable."""
        ...

    def get_price_or_default(self, default: float = 10.0) -> float:
        """Return current price, falling back to default if API is unavailable."""
        ...


@runtime_checkable
class EnergyReader(Protocol):
    """Contract for energy measurement backends (e.g., Intel RAPL)."""

    def start(self) -> None:
        """Begin energy measurement."""
        ...

    def stop(self) -> dict:
        """Stop measurement and return {"joules": float, "watts_avg": float}."""
        ...

    @property
    def rapl_available(self) -> bool:
        """Whether real hardware energy counters are available."""
        ...


@runtime_checkable
class ModelScorer(Protocol):
    """Contract for LLM output quality scoring."""

    async def score(self, output: str, judge_url: str, judge_model: str) -> float:
        """Score model output quality on a 0.0-1.0 scale."""
        ...
