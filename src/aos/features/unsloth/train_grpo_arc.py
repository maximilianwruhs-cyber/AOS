#!/usr/bin/env python3
"""
GRPO (Group Relative Policy Optimization) Training for ARC Reasoning

Uses Unsloth's native GRPOTrainer to teach the model to solve ARC grid
transformation puzzles via reinforcement learning with verifiable rewards.

Pipeline: SFT (pretraining) → GRPO (reward optimization)
The SFT step (train_qwen_7b.py) teaches format. This script teaches reasoning.

Reward function: exact grid match = 1.0, partial cell match = proportional.
Hardware target: GTX 1070 (8GB VRAM) — num_generations=4 to fit in memory.
"""

import json
import os
import re
import sys

# Ensure unsloth is importable
try:
    from unsloth import FastLanguageModel
    from trl import GRPOConfig, GRPOTrainer
    from datasets import Dataset
except ImportError as e:
    print(f"ERROR: Missing dependency: {e}")
    print("Install: pip install unsloth trl datasets")
    sys.exit(1)

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
MAX_SEQ_LENGTH = 1024
DTYPE = None
LOAD_IN_4BIT = True
NUM_GENERATIONS = 4  # Group size — memory-limited on 8GB

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AOS_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))
ARC_JSONL = os.path.join(AOS_ROOT, "data", "training", "arc_reasoning_target.jsonl")
OUTPUT_DIR = os.path.join(AOS_ROOT, "data", "models")
SFT_MODEL_DIR = os.path.join(OUTPUT_DIR, "custom_gemma4_e4b")


# ──────────────────────────────────────────────
# Grid Utilities
# ──────────────────────────────────────────────
def compact_to_grid(text: str) -> list[list[int]]:
    """Deserialize compact grid format (pipe-delimited digits)."""
    try:
        return [[int(c) for c in row] for row in text.strip().split("|")]
    except (ValueError, AttributeError):
        return []


def extract_grid_from_completion(completion: str) -> list[list[int]]:
    """Extract the predicted grid from a model completion.

    Handles formats:
    - Raw compact: "012|301|..."
    - After </think> tag: "<think>...</think>\n012|301|..."
    """
    # Strip Gemma 4 thinking tags
    text = completion
    channel_end = text.rfind("<channel|>")
    if channel_end >= 0:
        text = text[channel_end + len("<channel|>"):].strip()

    # Fallback: strip legacy <think> tags
    think_end = text.rfind("</think>")
    if think_end >= 0:
        text = text[think_end + len("</think>"):].strip()

    # Find the first line that looks like a compact grid (digits and pipes)
    for line in text.split("\n"):
        line = line.strip()
        if line and all(c in "0123456789|" for c in line) and "|" in line:
            return compact_to_grid(line)

    # Fallback: try the entire remaining text
    clean = text.strip()
    if clean and all(c in "0123456789|\n" for c in clean):
        return compact_to_grid(clean.replace("\n", "|"))

    return []


def extract_expected_grid(prompt: str) -> list[list[int]]:
    """Extract the expected test output from the original training sample.

    The prompt contains the expected output embedded after 'Test Output:' or
    as the last compact grid in the assistant turn.
    """
    # Look for the pattern after "What is the Test Output?"
    # The expected output is stored separately in the training data
    return []  # This is filled by the reward wrapper


# ──────────────────────────────────────────────
# Reward Function
# ──────────────────────────────────────────────
def grid_match_reward(predicted: list[list[int]], expected: list[list[int]]) -> float:
    """Calculate reward based on grid cell matching.

    Returns:
        1.0 for exact match
        Proportional score for partial match
        0.0 for dimension mismatch or empty grids
    """
    if not predicted or not expected:
        return 0.0

    if len(predicted) != len(expected):
        return 0.0

    total_cells = 0
    matching_cells = 0

    for pred_row, exp_row in zip(predicted, expected):
        if len(pred_row) != len(exp_row):
            return 0.0  # Column mismatch
        for p, e in zip(pred_row, exp_row):
            total_cells += 1
            if p == e:
                matching_cells += 1

    return matching_cells / total_cells if total_cells > 0 else 0.0


# ──────────────────────────────────────────────
# Dataset Loading
# ──────────────────────────────────────────────
def load_arc_grpo_dataset() -> Dataset:
    """Load ARC prediction tasks formatted for GRPO.

    Each sample needs:
    - prompt: the task description (examples + test input)
    - expected_output: the compact grid string (for reward computation)
    """
    if not os.path.exists(ARC_JSONL):
        print(f"ERROR: {ARC_JSONL} not found. Run preprocess_arc.py first.")
        sys.exit(1)

    prompts = []
    expected_outputs = []

    with open(ARC_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            sample = json.loads(line)
            if sample.get("format") != "prediction":
                continue

            text = sample["text"]

            # Extract the prompt (everything up to the model turn)
            assistant_marker = "<start_of_turn>model\n"
            idx = text.find(assistant_marker)
            if idx < 0:
                # Fallback to ChatML format
                assistant_marker = "<|im_start|>assistant\n"
                idx = text.find(assistant_marker)
                if idx < 0:
                    continue

            prompt = text[:idx + len(assistant_marker)].rstrip()

            # Extract expected output (the compact grid in the assistant response)
            assistant_content = text[idx + len(assistant_marker):]
            assistant_content = assistant_content.replace("<end_of_turn>", "").replace("<|im_end|>", "").strip()

            # Remove Gemma 4 thinking channel
            channel_end = assistant_content.rfind("<channel|>")
            if channel_end >= 0:
                grid_text = assistant_content[channel_end + len("<channel|>"):].strip()
            else:
                # Fallback: legacy <think> tags
                think_end = assistant_content.rfind("</think>")
                if think_end >= 0:
                    grid_text = assistant_content[think_end + len("</think>"):].strip()
                else:
                    grid_text = assistant_content.strip()

            if grid_text and "|" in grid_text:
                prompts.append(prompt)
                expected_outputs.append(grid_text)

    print(f"Loaded {len(prompts)} ARC prediction tasks for GRPO")
    return Dataset.from_dict({
        "prompt": prompts,
        "expected_output": expected_outputs,
    })


# ──────────────────────────────────────────────
# GRPO Reward Wrapper
# ──────────────────────────────────────────────
def make_reward_fn(expected_outputs: list[str]):
    """Create a reward function that captures the expected outputs."""
    expected_map = {}
    for i, output in enumerate(expected_outputs):
        expected_map[i] = compact_to_grid(output)

    def reward_fn(completions: list[str], prompts: list[str] = None, **kwargs) -> list[float]:
        """Compute rewards for a batch of completions."""
        rewards = []
        for completion in completions:
            pred_grid = extract_grid_from_completion(completion)

            best_reward = 0.0
            for exp_grid in expected_map.values():
                r = grid_match_reward(pred_grid, exp_grid)
                if r > best_reward:
                    best_reward = r

            # Bonus for valid grid format
            format_bonus = 0.1 if pred_grid else 0.0

            # Bonus for using Gemma 4 thinking channel (or legacy <think>)
            think_bonus = 0.05 if ("<|channel>thought" in completion or "<think>" in completion) else 0.0

            rewards.append(min(1.0, best_reward + format_bonus + think_bonus))

        return rewards

    return reward_fn


# ──────────────────────────────────────────────
# Main Training Loop
# ──────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  ARC-AGI GRPO Training — Intelligence per Watt")
    print("  Hardware: GTX 1070 (8GB VRAM)")
    print("  Group size: 4 | Max sequence: 1024")
    print("=" * 60)

    # Load SFT-pretrained model (or base model if SFT hasn't run)
    model_path = SFT_MODEL_DIR if os.path.exists(SFT_MODEL_DIR) else "unsloth/gemma-4-E4B-it-bnb-4bit"
    print(f"\nLoading model from: {model_path}")

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_path,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=DTYPE,
        load_in_4bit=LOAD_IN_4BIT,
    )

    model = FastLanguageModel.get_peft_model(
        model, r=8,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_alpha=8, lora_dropout=0, bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    # Load dataset
    dataset = load_arc_grpo_dataset()
    reward_fn = make_reward_fn(dataset["expected_output"])

    # GRPO Training config — tuned for 8GB VRAM
    training_args = GRPOConfig(
        output_dir=os.path.join(OUTPUT_DIR, "checkpoints_grpo"),
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        num_generations=NUM_GENERATIONS,
        max_prompt_length=768,
        max_completion_length=256,
        num_train_epochs=1,
        learning_rate=5e-5,
        fp16=True,
        bf16=False,
        logging_steps=1,
        optim="adamw_8bit",
        seed=3407,
        report_to="none",
    )

    trainer = GRPOTrainer(
        model=model,
        tokenizer=tokenizer,
        args=training_args,
        train_dataset=dataset,
        reward_funcs=reward_fn,
    )

    print("\nStarting GRPO training...")
    trainer.train()

    # Export
    output_path = os.path.join(OUTPUT_DIR, "custom_gemma4_e4b_grpo")
    print(f"Exporting GRPO-trained model to {output_path}...")
    model.save_pretrained_gguf(output_path, tokenizer, quantization_method="q4_k_m")
    print("GRPO training complete.")


if __name__ == "__main__":
    main()
