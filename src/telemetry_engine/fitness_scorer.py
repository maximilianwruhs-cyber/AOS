"""
AOS — Evolutionary Fitness Scorer
Minimal, production-ready scoring engine for mutation approval.
Based on the "Final Idea" specification.

z = (Quality × Efficiency) × (1 − Variance)
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple
import statistics


# =========================
# Exceptions
# =========================

class InvalidMeasurementError(Exception):
    pass


# =========================
# Data Models
# =========================

@dataclass
class TrialResult:
    passed: bool
    execution_time_ms: float
    output_similarity: float  # 0 → 1


@dataclass
class ScoringConfig:
    baseline_time_ms: float
    baseline_energy_joules: float

    min_trials_for_variance: int = 2
    variance_fallback: float = 0.3

    # Decision thresholds
    min_quality: float = 0.75
    min_efficiency: float = 1.01
    min_z_score: float = 0.7


@dataclass
class FitnessResult:
    z_score: float
    approved: bool
    reason: Optional[str]

    quality: float
    efficiency: float
    variance_penalty: float


# =========================
# Core Computation
# =========================

def compute_quality(trials: List[TrialResult], config: ScoringConfig) -> float:
    if not trials:
        return 0.0

    pass_rate = sum(t.passed for t in trials) / len(trials)
    successful = [t for t in trials if t.passed]

    if not successful:
        return 0.0

    avg_time = statistics.mean(t.execution_time_ms for t in successful)
    avg_similarity = statistics.mean(t.output_similarity for t in successful)

    # Normalize execution time against baseline
    time_score = min(1.0, config.baseline_time_ms / max(0.001, avg_time))  # FIX #44: avoid div/0

    # Weighted blend (simple & effective)
    Q = (
        0.5 * pass_rate +
        0.3 * time_score +
        0.2 * avg_similarity
    )

    return round(Q, 4)


def compute_efficiency(
    energy_joules: float,
    config: ScoringConfig
) -> float:
    if energy_joules == 0:
        raise InvalidMeasurementError("Energy measurement is zero (invalid).")

    if energy_joules < 0:
        raise InvalidMeasurementError("Energy measurement is negative (corrupt).")

    return round(config.baseline_energy_joules / energy_joules, 4)


def compute_variance_penalty(
    trials: List[TrialResult],
    config: ScoringConfig
) -> float:
    successful = [t.output_similarity for t in trials if t.passed]

    if len(successful) < config.min_trials_for_variance:
        return config.variance_fallback

    mean = statistics.mean(successful)
    stdev = statistics.stdev(successful)

    if mean == 0:
        return 1.0

    cv = stdev / mean
    return round(min(cv, 1.0), 4)


def compute_z_score(Q: float, E: float, V: float) -> float:
    return round((Q * E) * (1 - V), 4)


# =========================
# Decision Logic
# =========================

def approve(
    z: float,
    Q: float,
    E: float,
    config: ScoringConfig
) -> Tuple[bool, Optional[str]]:

    if Q < config.min_quality:
        return False, f"low_quality:{Q:.3f}"

    if E < config.min_efficiency:
        return False, f"no_efficiency_gain:{E:.3f}"

    if z < config.min_z_score:
        return False, f"low_score:{z:.3f}"

    return True, None


# =========================
# Main Entry Point
# =========================

def evaluate_mutation(
    trials: List[TrialResult],
    energy_joules: float,
    config: ScoringConfig
) -> FitnessResult:

    # --- Quality ---
    Q = compute_quality(trials, config)

    # --- Efficiency ---
    try:
        E = compute_efficiency(energy_joules, config)
    except InvalidMeasurementError:
        return FitnessResult(
            z_score=0.0,
            approved=False,
            reason="invalid_energy_measurement",
            quality=Q,
            efficiency=0.0,
            variance_penalty=1.0
        )

    # --- Variance ---
    V = compute_variance_penalty(trials, config)

    # --- Z Score ---
    Z = compute_z_score(Q, E, V)

    # --- Decision ---
    approved, reason = approve(Z, Q, E, config)

    return FitnessResult(
        z_score=Z,
        approved=approved,
        reason=reason,
        quality=Q,
        efficiency=E,
        variance_penalty=V
    )
