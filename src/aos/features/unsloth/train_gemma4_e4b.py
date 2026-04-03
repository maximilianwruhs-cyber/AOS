"""
Unsloth QLoRA Fine-Tuning: Qwen2.5-7B (Primary Target Model)
Hardware target: GTX 1070 (8GB VRAM) — BORDERLINE!
Maximum memory constraints: batch=1, seq=512, gradient checkpointing mandatory.
"""

from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import Dataset
import torch
import os
import glob
import json

# ──────────────────────────────────────────────
# EXTREME VRAM constraints for 7B on 8GB
# ──────────────────────────────────────────────
MAX_SEQ_LENGTH = 1024  # Bumped from 512 to fit larger ARC grids (30x30 compact)
DTYPE = None
LOAD_IN_4BIT = True

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AOS_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))
BRAIN_DIR = os.path.join(AOS_ROOT, "AOS_Brain", "02_Memory_Logs")
ARC_JSONL = os.path.join(AOS_ROOT, "data", "training", "arc_reasoning_target.jsonl")
OUTPUT_DIR = os.path.join(AOS_ROOT, "data", "models")
BRAIN_UPSAMPLE = 5  # Repeat brain samples to balance against ARC data


def load_brain_dataset() -> Dataset:
    """Ingest markdown from AOS_Brain vault + ARC reasoning JSONL."""
    texts = []

    # Source 1: Brain vault markdown (upsampled to balance ARC volume)
    brain_texts = []
    md_files = glob.glob(os.path.join(BRAIN_DIR, "*.md"))
    for fpath in md_files:
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                brain_texts.append(
                    f"<start_of_turn>system\nYou are NemoClaw, a sovereign AI coding assistant.<end_of_turn>\n"
                    f"<start_of_turn>user\nAnalyze this insight:<end_of_turn>\n"
                    f"<start_of_turn>model\n{content}<end_of_turn>"
                )
    # Upsample brain vault to prevent ARC data from drowning NemoClaw personality
    texts.extend(brain_texts * BRAIN_UPSAMPLE)
    print(f"  Brain vault: {len(brain_texts)} base × {BRAIN_UPSAMPLE} = {len(brain_texts) * BRAIN_UPSAMPLE} samples")

    # Source 2: ARC reasoning (pre-formatted ChatML)
    arc_count = 0
    if os.path.exists(ARC_JSONL):
        with open(ARC_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                sample = json.loads(line)
                if "text" in sample:
                    texts.append(sample["text"])
                    arc_count += 1
        print(f"  ARC reasoning: {arc_count} samples")
    else:
        print(f"  ARC reasoning: skipped (run preprocess_arc.py first)")

    if not texts:
        print(f"WARNING: No training data found. Using placeholder.")
        return Dataset.from_dict({
            "text": [
                "<start_of_turn>user\nWhat is the capital of Germany?<end_of_turn>\n<start_of_turn>model\nThe capital of Germany is Berlin.<end_of_turn>",
                "<start_of_turn>user\nExplain QLoRA in one sentence.<end_of_turn>\n<start_of_turn>model\nQLoRA quantizes a pretrained model to 4-bit and trains low-rank adapters in full precision on top.<end_of_turn>",
            ]
        })

    print(f"  Total: {len(texts)} training samples")
    return Dataset.from_dict({"text": texts})


def main():
    print("Loading Gemma 4 E4B Target (EXTREME VRAM MODE)...")
    print("WARNING: This will use ~7.5GB VRAM. Monitor nvidia-smi closely.")

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/gemma-4-E4B-it-bnb-4bit",
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=DTYPE,
        load_in_4bit=LOAD_IN_4BIT,
    )

    model = FastLanguageModel.get_peft_model(
        model, r=8,  # Lower rank to save VRAM (16 is too much for 7B on 8GB)
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_alpha=8, lora_dropout=0, bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    dataset = load_brain_dataset()

    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        packing=False,
        args=TrainingArguments(
            per_device_train_batch_size=1,   # CANNOT go higher on 8GB
            gradient_accumulation_steps=4,   # Simulate batch of 4
            warmup_steps=3,
            max_steps=20,                    # Shorter cycle due to VRAM pressure
            learning_rate=1e-4,              # Slightly lower LR for bigger model
            fp16=True, bf16=False,
            logging_steps=1,
            optim="adamw_8bit",
            output_dir=os.path.join(OUTPUT_DIR, "checkpoints_target"),
        ),
    )

    print("Training 7B target (this will be slow)...")
    trainer.train()

    output_path = os.path.join(OUTPUT_DIR, "custom_gemma4_e4b")
    print(f"Exporting GGUF to {output_path}...")
    model.save_pretrained_gguf(output_path, tokenizer, quantization_method="q4_k_m")
    print("Target E4B training complete.")


if __name__ == "__main__":
    main()
