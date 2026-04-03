#!/usr/bin/env python3
"""
ARC-AGI → ChatML Training Data Preprocessor (v2 — Research-Grade)

Converts ARC-AGI grid reasoning puzzles into structured ChatML training samples
for Unsloth fine-tuning. Based on ARC Prize winning methodology (2024-2026):

Formats:
  1. Prediction — multi-turn: show examples, predict held-out test output (TARGET)
  2. Grid Analysis — short pattern description (DRAFTER)
  3. CoT Reasoning — step-by-step with <think> tags (TARGET)

Augmentation:
  - Full D8 dihedral symmetry group (8 geometric transforms)
  - Random color permutations (shuffle non-zero palette)

Output:
  - arc_reasoning_target.jsonl  — prediction + CoT for 7B target model
  - arc_reasoning_drafter.jsonl — grid analysis (capped) for 0.5B drafter
  - arc_reasoning_all.jsonl     — everything combined (backward compat)

Usage:
  python preprocess_arc.py                        # Generate all formats
  python preprocess_arc.py --augment              # Full D8 + color permutations
  python preprocess_arc.py --stats                # Show dataset statistics
  python preprocess_arc.py --max-tasks 50         # Limit for testing
  python preprocess_arc.py --drafter-cap 300      # Cap drafter samples
"""

import argparse
import json
import os
import random
import sys
from itertools import permutations
from pathlib import Path

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.resolve()
AOS_ROOT = SCRIPT_DIR.parent.parent.parent.parent
ARC_DIR = AOS_ROOT / "data" / "arc-agi" / "data"
REARC_DIR = AOS_ROOT / "data" / "re-arc"
OUTPUT_DIR = AOS_ROOT / "data" / "training"

OUTPUT_TARGET = OUTPUT_DIR / "arc_reasoning_target.jsonl"
OUTPUT_DRAFTER = OUTPUT_DIR / "arc_reasoning_drafter.jsonl"
OUTPUT_ALL = OUTPUT_DIR / "arc_reasoning.jsonl"  # backward compat


# ──────────────────────────────────────────────
# Compact Grid Serialization
# ──────────────────────────────────────────────
def grid_to_compact(grid: list[list[int]]) -> str:
    """Serialize a grid as pipe-delimited digit rows. ~70% fewer tokens than JSON."""
    return "|".join("".join(str(c) for c in row) for row in grid)


def compact_to_grid(text: str) -> list[list[int]]:
    """Deserialize compact grid format back to nested list."""
    return [[int(c) for c in row] for row in text.split("|")]


def grid_dimensions(grid: list[list[int]]) -> tuple[int, int]:
    """Return (rows, cols) of a grid."""
    return len(grid), len(grid[0]) if grid else 0


def count_colors(grid: list[list[int]]) -> dict[int, int]:
    """Count occurrences of each color in a grid."""
    counts = {}
    for row in grid:
        for cell in row:
            counts[cell] = counts.get(cell, 0) + 1
    return counts


# ──────────────────────────────────────────────
# D8 Dihedral Symmetry Group (8 transforms)
# ──────────────────────────────────────────────
def rotate_90(grid):
    """Rotate 90° clockwise."""
    rows, cols = len(grid), len(grid[0])
    return [[grid[rows - 1 - j][i] for j in range(rows)] for i in range(cols)]


def rotate_180(grid):
    """Rotate 180°."""
    return [row[::-1] for row in grid[::-1]]


def rotate_270(grid):
    """Rotate 270° clockwise (= 90° counter-clockwise)."""
    rows, cols = len(grid), len(grid[0])
    return [[grid[j][cols - 1 - i] for j in range(rows)] for i in range(cols)]


def flip_h(grid):
    """Flip horizontally (left-right)."""
    return [row[::-1] for row in grid]


def flip_v(grid):
    """Flip vertically (top-bottom)."""
    return grid[::-1]


def transpose(grid):
    """Transpose (flip along main diagonal)."""
    return [list(row) for row in zip(*grid)]


def anti_transpose(grid):
    """Flip along anti-diagonal."""
    return rotate_90(flip_h(grid))


D8_TRANSFORMS = [
    ("identity", lambda g: [row[:] for row in g]),
    ("rot90", rotate_90),
    ("rot180", rotate_180),
    ("rot270", rotate_270),
    ("flip_h", flip_h),
    ("flip_v", flip_v),
    ("transpose", transpose),
    ("anti_transpose", anti_transpose),
]


# ──────────────────────────────────────────────
# Color Permutation
# ──────────────────────────────────────────────
def permute_colors(grid: list[list[int]], perm: dict[int, int]) -> list[list[int]]:
    """Apply a color permutation map to a grid. Background (0) stays 0."""
    return [[perm.get(c, c) for c in row] for row in grid]


def random_color_perm(rng: random.Random) -> dict[int, int]:
    """Generate a random permutation of non-zero colors (1-9)."""
    colors = list(range(1, 10))
    shuffled = colors[:]
    rng.shuffle(shuffled)
    return {orig: new for orig, new in zip(colors, shuffled)}


# ──────────────────────────────────────────────
# Chat Template Formatting (ChatML + Gemma 4)
# ──────────────────────────────────────────────
CHAT_FORMAT = "chatml"  # Global, set by --format flag


def make_chatml(system: str, user: str, assistant: str) -> str:
    """Format a training sample in ChatML (Qwen/Llama)."""
    return (
        f"<|im_start|>system\n{system}<|im_end|>\n"
        f"<|im_start|>user\n{user}<|im_end|>\n"
        f"<|im_start|>assistant\n{assistant}<|im_end|>"
    )


def make_gemma4(system: str, user: str, assistant: str) -> str:
    """Format a training sample in Gemma 4 native template."""
    return (
        f"<start_of_turn>system\n{system}<end_of_turn>\n"
        f"<start_of_turn>user\n{user}<end_of_turn>\n"
        f"<start_of_turn>model\n{assistant}<end_of_turn>"
    )


def make_chat(system: str, user: str, assistant: str) -> str:
    """Format using the globally selected chat template."""
    if CHAT_FORMAT == "gemma4":
        return make_gemma4(system, user, assistant)
    return make_chatml(system, user, assistant)


def wrap_thinking(reasoning: str) -> str:
    """Wrap reasoning in format-appropriate thinking tags."""
    if CHAT_FORMAT == "gemma4":
        return f"<|channel>thought\n{reasoning}\n<channel|>\n"
    return f"<think>\n{reasoning}\n</think>\n"


# ──────────────────────────────────────────────
# Format 1: Multi-Turn Prediction (TARGET MODEL)
# ──────────────────────────────────────────────
def generate_prediction(task_id: str, pairs: list[dict], test_pair: dict) -> str:
    """
    Generate a prediction sample: show N examples, model must predict held-out output.
    Uses <think> tags for chain-of-thought emergence.
    """
    if CHAT_FORMAT == "gemma4":
        system = (
            "<|think|>You solve grid transformation puzzles. Study the examples, "
            "infer the transformation rule, then predict the output for the test input. "
            "Think step-by-step before giving your answer."
        )
    else:
        system = (
            "You solve grid transformation puzzles. Study the examples, "
            "infer the transformation rule, then predict the output for the test input. "
            "Think step-by-step inside <think> tags before giving your answer."
        )

    # Build example display
    examples = []
    for i, pair in enumerate(pairs):
        inp = grid_to_compact(pair["input"])
        out = grid_to_compact(pair["output"])
        examples.append(f"Example {i+1} Input: {inp}\nExample {i+1} Output: {out}")

    test_inp = grid_to_compact(test_pair["input"])
    test_out = grid_to_compact(test_pair["output"])

    user = (
        f"Task {task_id}\n\n"
        + "\n\n".join(examples)
        + f"\n\nTest Input: {test_inp}\n\nWhat is the Test Output?"
    )

    # Build CoT reasoning trace
    in_dims = grid_dimensions(test_pair["input"])
    out_dims = grid_dimensions(test_pair["output"])
    in_colors = sorted(set(c for row in test_pair["input"] for c in row) - {0})
    out_colors = sorted(set(c for row in test_pair["output"] for c in row) - {0})

    size_note = (
        "Grid size stays the same."
        if in_dims == out_dims
        else f"Grid changes from {in_dims[0]}x{in_dims[1]} to {out_dims[0]}x{out_dims[1]}."
    )

    reasoning = (
        f"Looking at the examples:\n"
        f"- {size_note}\n"
        f"- Input uses colors: {in_colors}\n"
        f"- Output uses colors: {out_colors}\n"
        f"- I need to identify the transformation pattern from the examples "
        f"and apply it to the test input."
    )

    assistant = wrap_thinking(reasoning) + test_out
    return make_chat(system, user, assistant)


# ──────────────────────────────────────────────
# Format 2: Grid Analysis (DRAFTER MODEL)
# ──────────────────────────────────────────────
def generate_grid_analysis(task_id: str, pairs: list[dict]) -> str:
    """Generate a short grid analysis training sample."""
    system = "You analyze grid transformation patterns concisely."

    inp = grid_to_compact(pairs[0]["input"])
    out = grid_to_compact(pairs[0]["output"])
    in_dims = grid_dimensions(pairs[0]["input"])
    out_dims = grid_dimensions(pairs[0]["output"])

    user = f"Task {task_id}\nInput ({in_dims[0]}x{in_dims[1]}): {inp}\nOutput ({out_dims[0]}x{out_dims[1]}): {out}\nDescribe the transformation."

    # Build concise analysis
    in_colors = count_colors(pairs[0]["input"])
    out_colors = count_colors(pairs[0]["output"])
    non_zero_in = {k: v for k, v in in_colors.items() if k != 0}
    non_zero_out = {k: v for k, v in out_colors.items() if k != 0}

    size_change = "same size" if in_dims == out_dims else f"{in_dims[0]}x{in_dims[1]}→{out_dims[0]}x{out_dims[1]}"
    nz_in = sum(non_zero_in.values())
    nz_out = sum(non_zero_out.values())
    pattern = "expansion" if nz_out > nz_in else "reduction" if nz_out < nz_in else "rearrangement"

    assistant = (
        f"Grid {size_change}. "
        f"Input: {nz_in} non-zero cells ({sorted(non_zero_in.keys())}). "
        f"Output: {nz_out} non-zero cells ({sorted(non_zero_out.keys())}). "
        f"Pattern: {pattern}."
    )
    return make_chat(system, user, assistant)


# ──────────────────────────────────────────────
# Format 3: CoT Reasoning (TARGET MODEL)
# ──────────────────────────────────────────────
def generate_cot_reasoning(task_id: str, pairs: list[dict]) -> str:
    """Generate a chain-of-thought reasoning sample with <think> tags."""
    if CHAT_FORMAT == "gemma4":
        system = (
            "<|think|>You reason step-by-step about grid transformations."
        )
    else:
        system = (
            "You reason step-by-step about grid transformations. "
            "Use <think> tags for your reasoning process."
        )

    inp = grid_to_compact(pairs[0]["input"])
    out = grid_to_compact(pairs[0]["output"])

    user = f"Input: {inp}\nOutput: {out}\nWhat transformation was applied?"

    in_dims = grid_dimensions(pairs[0]["input"])
    out_dims = grid_dimensions(pairs[0]["output"])
    in_colors = count_colors(pairs[0]["input"])
    out_colors = count_colors(pairs[0]["output"])
    nz_in = sum(v for k, v in in_colors.items() if k != 0)
    nz_out = sum(v for k, v in out_colors.items() if k != 0)

    steps = [
        f"Step 1: Input is {in_dims[0]}x{in_dims[1]}, output is {out_dims[0]}x{out_dims[1]}.",
        f"Step 2: Input has {nz_in} non-zero cells, output has {nz_out}.",
        f"Step 3: Input colors: {sorted(set(in_colors.keys()) - {{0}})}. Output colors: {sorted(set(out_colors.keys()) - {{0}})}.",
    ]

    if in_dims == out_dims:
        steps.append("Step 4: Dimensions unchanged — transformation modifies cell values in-place.")
    else:
        steps.append(f"Step 4: Grid resized from {in_dims[0]}x{in_dims[1]} to {out_dims[0]}x{out_dims[1]}.")

    if len(pairs) > 1:
        p2_in = grid_dimensions(pairs[1]["input"])
        p2_out = grid_dimensions(pairs[1]["output"])
        steps.append(
            f"Step 5: Verifying with example 2: {p2_in[0]}x{p2_in[1]}→{p2_out[0]}x{p2_out[1]} — consistent."
        )

    assistant = wrap_thinking("\n".join(steps))
    return make_chat(system, user, assistant)


# ──────────────────────────────────────────────
# Task Processing
# ──────────────────────────────────────────────
def process_task(
    filepath: Path,
    augment: bool = False,
    color_perms: int = 3,
    rng: random.Random = None,
) -> dict:
    """
    Process a single ARC task file into role-specific training samples.
    Returns dict with 'target' and 'drafter' sample lists.
    """
    if rng is None:
        rng = random.Random(42)

    task_id = filepath.stem
    with open(filepath, "r") as f:
        task = json.load(f)

    train_pairs = task.get("train", [])
    test_pairs = task.get("test", [])
    if not train_pairs:
        return {"target": [], "drafter": []}

    target_samples = []
    drafter_samples = []

    def _generate_all(tid, pairs, test_p):
        """Generate all formats for a given set of pairs."""
        t_samples = []
        d_samples = []

        # Format 1: Prediction (target only) — needs at least 2 train pairs or a test pair
        if test_p:
            try:
                text = generate_prediction(tid, pairs, test_p)
                t_samples.append({"text": text, "task_id": tid, "format": "prediction", "role": "target"})
            except Exception:
                pass
        elif len(pairs) > 1:
            # Hold out last train pair as pseudo-test
            try:
                text = generate_prediction(tid, pairs[:-1], pairs[-1])
                t_samples.append({"text": text, "task_id": tid, "format": "prediction", "role": "target"})
            except Exception:
                pass

        # Format 2: Grid Analysis (drafter)
        try:
            text = generate_grid_analysis(tid, pairs)
            d_samples.append({"text": text, "task_id": tid, "format": "grid_analysis", "role": "drafter"})
        except Exception:
            pass

        # Format 3: CoT Reasoning (target)
        try:
            text = generate_cot_reasoning(tid, pairs)
            t_samples.append({"text": text, "task_id": tid, "format": "cot_reasoning", "role": "target"})
        except Exception:
            pass

        return t_samples, d_samples

    # Base task (identity transform)
    test_p = test_pairs[0] if test_pairs else None
    t, d = _generate_all(task_id, train_pairs, test_p)
    target_samples.extend(t)
    drafter_samples.extend(d)

    # Augmented variants
    if augment:
        for transform_name, transform_fn in D8_TRANSFORMS:
            if transform_name == "identity":
                continue  # Already processed above

            # Apply geometric transform
            aug_train = [{"input": transform_fn(p["input"]), "output": transform_fn(p["output"])} for p in train_pairs]
            aug_test = {"input": transform_fn(test_p["input"]), "output": transform_fn(test_p["output"])} if test_p else None
            aug_id = f"{task_id}_{transform_name}"

            t, d = _generate_all(aug_id, aug_train, aug_test)
            target_samples.extend(t)
            drafter_samples.extend(d)

        # Color permutations (applied on top of identity only to limit explosion)
        for cp_idx in range(color_perms):
            perm = random_color_perm(rng)
            perm_train = [{"input": permute_colors(p["input"], perm), "output": permute_colors(p["output"], perm)} for p in train_pairs]
            perm_test = {"input": permute_colors(test_p["input"], perm), "output": permute_colors(test_p["output"], perm)} if test_p else None
            perm_id = f"{task_id}_cperm{cp_idx}"

            t, d = _generate_all(perm_id, perm_train, perm_test)
            target_samples.extend(t)
            drafter_samples.extend(d)

    return {"target": target_samples, "drafter": drafter_samples}


# ──────────────────────────────────────────────
# Statistics
# ──────────────────────────────────────────────
def run_stats():
    """Print preprocessing statistics."""
    training_dir = ARC_DIR / "training"
    eval_dir = ARC_DIR / "evaluation"

    train_count = len(list(training_dir.glob("*.json"))) if training_dir.exists() else 0
    eval_count = len(list(eval_dir.glob("*.json"))) if eval_dir.exists() else 0

    print("═══════════════════════════════════════════")
    print("  ARC-AGI Preprocessing Statistics (v2)")
    print("═══════════════════════════════════════════")
    print(f"  Training tasks:     {train_count}")
    print(f"  Evaluation tasks:   {eval_count}")
    print(f"  Total tasks:        {train_count + eval_count}")
    print(f"  Re-ARC available:   {'yes' if REARC_DIR.exists() else 'no'}")
    print(f"  ─────────────────────────────────────────")
    print(f"  Formats: prediction (target), CoT (target), grid_analysis (drafter)")
    print(f"  With D8 augment:    8 geometric × 3 color perms = 11 variants/task")
    print(f"  Est. target samples: {(train_count + eval_count) * 11 * 2}")
    print(f"  Est. drafter samples: {(train_count + eval_count) * 11}")
    print(f"  ─────────────────────────────────────────")

    for path, label in [(OUTPUT_TARGET, "Target"), (OUTPUT_DRAFTER, "Drafter"), (OUTPUT_ALL, "Combined")]:
        if path.exists():
            with open(path, "r") as f:
                count = sum(1 for _ in f)
            size = path.stat().st_size / 1024 / 1024
            print(f"  {label} samples:    {count} ({size:.1f} MB)")
        else:
            print(f"  {label} samples:    0 (not yet processed)")

    print("═══════════════════════════════════════════")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="ARC-AGI Training Data Preprocessor (v2)")
    parser.add_argument("--augment", action="store_true", help="Full D8 + color permutation augmentation")
    parser.add_argument("--stats", action="store_true", help="Show dataset statistics")
    parser.add_argument("--max-tasks", type=int, default=0, help="Limit number of tasks (0=all)")
    parser.add_argument("--color-perms", type=int, default=3, help="Number of color permutations per task")
    parser.add_argument("--drafter-cap", type=int, default=300, help="Max drafter samples (0=no cap)")
    parser.add_argument("--format", choices=["chatml", "gemma4"], default="gemma4",
                        help="Chat template format: chatml (Qwen/Llama) or gemma4 (default)")
    args = parser.parse_args()

    # Set global chat format
    global CHAT_FORMAT
    CHAT_FORMAT = args.format
    print(f"  Chat format: {CHAT_FORMAT}")

    if args.stats:
        run_stats()
        return

    if not ARC_DIR.exists():
        print(f"ERROR: ARC dataset not found at {ARC_DIR}")
        print("Run: git clone https://github.com/fchollet/ARC-AGI.git data/arc-agi")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)

    # Collect all task files (original + synthetic)
    task_files = sorted(list((ARC_DIR / "training").glob("*.json")))
    task_files += sorted(list((ARC_DIR / "evaluation").glob("*.json")))

    # Include Re-ARC synthetic tasks if available
    synthetic_dir = ARC_DIR / "synthetic"
    if synthetic_dir.exists():
        synthetic_files = sorted(list(synthetic_dir.glob("*.json")))
        task_files += synthetic_files
        print(f"  Including {len(synthetic_files)} Re-ARC synthetic tasks")

    if args.max_tasks > 0:
        task_files = task_files[:args.max_tasks]

    print(f"Processing {len(task_files)} ARC tasks "
          f"(augment={'D8+color' if args.augment else 'no'}, "
          f"color_perms={args.color_perms})...")

    all_target = []
    all_drafter = []
    errors = 0

    for filepath in task_files:
        try:
            result = process_task(filepath, augment=args.augment, color_perms=args.color_perms, rng=rng)
            all_target.extend(result["target"])
            all_drafter.extend(result["drafter"])
        except Exception as e:
            errors += 1
            print(f"  ERROR: {filepath.name}: {e}")

    # Shuffle
    rng.shuffle(all_target)
    rng.shuffle(all_drafter)

    # Cap drafter samples
    if args.drafter_cap > 0 and len(all_drafter) > args.drafter_cap:
        all_drafter = all_drafter[:args.drafter_cap]

    # Write role-specific JSONL files
    for samples, path, label in [
        (all_target, OUTPUT_TARGET, "Target"),
        (all_drafter, OUTPUT_DRAFTER, "Drafter"),
    ]:
        with open(path, "w", encoding="utf-8") as f:
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
        size_mb = path.stat().st_size / 1024 / 1024
        print(f"  {label}: {len(samples)} samples ({size_mb:.1f} MB) → {path.name}")

    # Write combined (backward compat)
    all_combined = all_target + all_drafter
    rng.shuffle(all_combined)
    with open(OUTPUT_ALL, "w", encoding="utf-8") as f:
        for sample in all_combined:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    # Summary
    print(f"\nDone.")
    for label, samples in [("Target", all_target), ("Drafter", all_drafter)]:
        formats = {}
        for s in samples:
            fmt = s.get("format", "unknown")
            formats[fmt] = formats.get(fmt, 0) + 1
        print(f"  {label}: {', '.join(f'{k}={v}' for k, v in sorted(formats.items()))}")
    if errors:
        print(f"  Errors: {errors}")


if __name__ == "__main__":
    main()
