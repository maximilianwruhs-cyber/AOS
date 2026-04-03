"""
Unsloth QLoRA Fine-Tuning: Qwen2.5-0.5B (Speculative Drafter)
Hardware target: GTX 1070 (8GB VRAM)
This model is tiny — we can afford larger batch sizes and longer sequences.
"""

from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import Dataset
import torch
import os
import glob
import json

from gguf_export import export_to_gguf

# ──────────────────────────────────────────────
# VRAM config — 0.5B model is very light
# ──────────────────────────────────────────────
MAX_SEQ_LENGTH = 1024
DTYPE = None
LOAD_IN_4BIT = True

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AOS_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))
BRAIN_DIR = os.path.join(AOS_ROOT, "AOS_Brain", "02_Memory_Logs")
ARC_JSONL = os.path.join(AOS_ROOT, "data", "training", "arc_reasoning_drafter.jsonl")
OUTPUT_DIR = os.path.join(AOS_ROOT, "data", "models")
BRAIN_UPSAMPLE = 3  # Lower multiplier since drafter has fewer ARC samples


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
                    f"<start_of_turn>system\nYou are a fast code completion drafter.<end_of_turn>\n"
                    f"<start_of_turn>user\nComplete:<end_of_turn>\n"
                    f"<start_of_turn>model\n{content}<end_of_turn>"
                )
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
                "<start_of_turn>user\nComplete this code: def hello(<end_of_turn>\n<start_of_turn>model\ndef hello(name):\n    return f'Hello, {name}!'<end_of_turn>",
                "<start_of_turn>user\nFix: for i in range(len(arr)):<end_of_turn>\n<start_of_turn>model\nfor i in range(len(arr) - 1):<end_of_turn>",
            ]
        })

    print(f"  Total: {len(texts)} training samples")
    return Dataset.from_dict({"text": texts})


def main():
    print("Loading Gemma 4 E2B Drafter...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/gemma-4-E2B-it-bnb-4bit",
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=DTYPE,
        load_in_4bit=LOAD_IN_4BIT,
    )

    model = FastLanguageModel.get_peft_model(
        model, r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16, lora_dropout=0, bias="none",
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
            per_device_train_batch_size=4,
            gradient_accumulation_steps=2,
            warmup_steps=5,
            max_steps=30,
            learning_rate=2e-4,
            fp16=True, bf16=False,
            logging_steps=1,
            optim="adamw_8bit",
            output_dir=os.path.join(OUTPUT_DIR, "checkpoints_drafter"),
        ),
    )

    print("Training drafter...")
    trainer.train()

    # Export merged weights + GGUF conversion
    output_path = os.path.join(OUTPUT_DIR, "custom_gemma4_e2b")
    export_to_gguf(model, tokenizer, output_path, quant_method="q4_k_m")
    print("Drafter E2B training complete.")


if __name__ == "__main__":
    main()
