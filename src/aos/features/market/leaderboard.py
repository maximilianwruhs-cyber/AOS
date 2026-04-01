"""
AOS — Persistent Mutation Leaderboard
Tracks top-performing mutations across evolutionary runs.
"""
import json
import sys
from pathlib import Path
from datetime import datetime

import aos.config as config


class MutationLeaderboard:
    """JSON-backed leaderboard for top mutations over time."""

    def __init__(self, path: Path = None):
        self.path = path or config.DATA_DIR / "mutation_leaderboard.json"
        self.entries = self._load()

    def _load(self) -> list:
        if self.path.exists():
            try:
                with open(self.path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.entries, f, indent=2, ensure_ascii=False)

    def record(self, agent_id: str, genome_summary: str, fitness_result,
               generation: int = 0, model: str = ""):
        """Record a mutation result on the leaderboard."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent_id,
            "model": model,
            "generation": generation,
            "z_score": fitness_result.z_score,
            "quality": fitness_result.quality,
            "efficiency": fitness_result.efficiency,
            "variance_penalty": fitness_result.variance_penalty,
            "approved": fitness_result.approved,
            "reason": fitness_result.reason,
            "genome_summary": genome_summary[:200],
        }
        self.entries.append(entry)
        self._save()
        return entry

    def top(self, n: int = 10) -> list:
        """Return top N mutations by z-score."""
        return sorted(self.entries, key=lambda x: x.get("z_score", 0), reverse=True)[:n]

    def print_leaderboard(self, n: int = 10):
        """Print a formatted leaderboard."""
        top = self.top(n)
        if not top:
            print("  No mutations recorded yet.")
            return

        print(f"\n{'='*70}")
        print(f"  AOS MUTATION LEADERBOARD — Top {n}")
        print(f"{'='*70}")
        print(f"  {'#':<3} {'Agent':<15} {'z-score':>8} {'Q':>6} {'E':>6} {'V':>6} {'OK':>4} {'Gen':>4}")
        print(f"  {'─'*3} {'─'*15} {'─'*8} {'─'*6} {'─'*6} {'─'*6} {'─'*4} {'─'*4}")

        for i, e in enumerate(top, 1):
            ok = "✅" if e.get("approved") else "❌"
            print(f"  {i:<3} {e['agent_id']:<15} {e['z_score']:>8.4f} "
                  f"{e['quality']:>6.3f} {e['efficiency']:>6.3f} "
                  f"{e['variance_penalty']:>6.3f} {ok:>4} {e.get('generation', 0):>4}")
        print(f"{'='*70}\n")
