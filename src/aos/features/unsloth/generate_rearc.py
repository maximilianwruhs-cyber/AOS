#!/usr/bin/env python3
"""
Re-ARC Synthetic Task Generator

Generates synthetic ARC-AGI tasks using the Re-ARC DSL generators and verifiers.
Outputs tasks in the same JSON format as original ARC-AGI data for direct
consumption by preprocess_arc.py.

Usage:
  python generate_rearc.py                      # Generate 25 examples per task
  python generate_rearc.py --n-examples 50      # More examples per task
  python generate_rearc.py --max-tasks 10       # Limit tasks for testing
  python generate_rearc.py --seed 123           # Reproducible generation
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from random import seed as set_seed

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.resolve()
AOS_ROOT = SCRIPT_DIR.parent.parent.parent.parent
REARC_DIR = AOS_ROOT / "data" / "re-arc"
OUTPUT_DIR = AOS_ROOT / "data" / "arc-agi" / "data" / "synthetic"

# Add Re-ARC to path
sys.path.insert(0, str(REARC_DIR))


def generate_synthetic_tasks(
    n_examples: int = 25,
    max_tasks: int = 0,
    seed: int = 42,
    diff_lb: float = 0.0,
    diff_ub: float = 1.0,
) -> dict:
    """Generate synthetic tasks using Re-ARC generators.

    Returns dict with counts and any errors.
    """
    # Import Re-ARC modules (must be done after path setup)
    try:
        import dsl
        import generators as gen_module
        import verifiers as ver_module
        from utils import strip_prefix, is_grid
    except ImportError as e:
        print(f"ERROR: Failed to import Re-ARC modules: {e}")
        print(f"Ensure Re-ARC is cloned at: {REARC_DIR}")
        sys.exit(1)

    # Get all generators and verifiers
    prefix_gen = "generate_"
    prefix_ver = "verify_"
    generators = {
        strip_prefix(n, prefix_gen): getattr(gen_module, n)
        for n in dir(gen_module) if n.startswith(prefix_gen)
    }
    verifiers = {
        strip_prefix(n, prefix_ver): getattr(ver_module, n)
        for n in dir(ver_module) if n.startswith(prefix_ver)
    }

    keys = sorted(generators.keys())
    if max_tasks > 0:
        keys = keys[:max_tasks]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    set_seed(seed)

    total_tasks = len(keys)
    total_examples = 0
    errors = 0

    print(f"Generating synthetic tasks: {total_tasks} tasks × {n_examples} examples")
    print(f"Difficulty range: [{diff_lb:.1f}, {diff_ub:.1f}]")
    print(f"Output: {OUTPUT_DIR}")
    print()

    for i, key in enumerate(keys):
        generator = generators[key]
        verifier = verifiers.get(key)

        examples = []
        attempts = 0
        max_attempts = n_examples * 20  # Avoid infinite loops

        start = time.time()

        while len(examples) < n_examples and attempts < max_attempts:
            attempts += 1
            try:
                example = generator(diff_lb, diff_ub)
                assert is_grid(example["input"])
                assert is_grid(example["output"])
                assert example["input"] != example["output"]

                # Verify if verifier exists
                if verifier:
                    assert verifier(example["input"]) == example["output"]

                # Convert frozensets to lists for JSON serialization
                inp = _convert_grid(example["input"])
                out = _convert_grid(example["output"])
                examples.append({"input": inp, "output": out})

            except Exception:
                continue

        elapsed = time.time() - start

        if not examples:
            errors += 1
            print(f"  ❌ {key}: 0 examples ({attempts} attempts, {elapsed:.1f}s)")
            continue

        # Split into train/test (first N-1 as train, last as test)
        if len(examples) >= 4:
            n_train = min(5, len(examples) - 1)
            task_data = {
                "train": examples[:n_train],
                "test": examples[n_train : n_train + 1],
            }
        else:
            task_data = {
                "train": examples[:-1] if len(examples) > 1 else examples,
                "test": examples[-1:] if len(examples) > 1 else [],
            }

        # Save as JSON
        task_path = OUTPUT_DIR / f"rearc_{key}.json"
        with open(task_path, "w") as f:
            json.dump(task_data, f, ensure_ascii=False)

        total_examples += len(examples)

        if (i + 1) % 50 == 0 or i + 1 == total_tasks:
            print(
                f"  [{i+1}/{total_tasks}] {key}: {len(examples)} examples "
                f"({attempts} attempts, {elapsed:.1f}s)"
            )

    print(f"\nDone: {total_tasks - errors} tasks, {total_examples} total examples, {errors} errors")
    print(f"Saved to: {OUTPUT_DIR}")

    return {
        "tasks": total_tasks - errors,
        "examples": total_examples,
        "errors": errors,
    }


def _convert_grid(grid) -> list[list[int]]:
    """Convert Re-ARC grid (possibly tuple of tuples) to list of lists."""
    if isinstance(grid, (tuple, frozenset)):
        return [list(row) for row in grid]
    return [list(row) for row in grid]


def main():
    parser = argparse.ArgumentParser(description="Re-ARC Synthetic Task Generator")
    parser.add_argument("--n-examples", type=int, default=25, help="Examples per task")
    parser.add_argument("--max-tasks", type=int, default=0, help="Limit tasks (0=all)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--diff-lb", type=float, default=0.0, help="Difficulty lower bound")
    parser.add_argument("--diff-ub", type=float, default=1.0, help="Difficulty upper bound")
    args = parser.parse_args()

    result = generate_synthetic_tasks(
        n_examples=args.n_examples,
        max_tasks=args.max_tasks,
        seed=args.seed,
        diff_lb=args.diff_lb,
        diff_ub=args.diff_ub,
    )

    # Print reprocessing hint
    print(f"\nTo include synthetic data in training, re-run the preprocessor:")
    print(f"  python -m aos.features.unsloth.preprocess_arc --augment")


if __name__ == "__main__":
    main()
