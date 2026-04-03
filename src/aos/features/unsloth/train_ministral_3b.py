"""
Unsloth QLoRA Fine-Tuning: Qwen2.5-3B (FIM / Autocomplete)
Hardware target: GTX 1070 (8GB VRAM)
Ingests markdown logs from AOS_Brain vault as organic training data.
"""

from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import Dataset
import torch
import os
import glob

from gguf_export import export_to_gguf

# ──────────────────────────────────────────────
# VRAM-constrained hyperparameters
# ──────────────────────────────────────────────
MAX_SEQ_LENGTH = 512
DTYPE = None  # Auto-detect (FP16 for GTX 1070)
LOAD_IN_4BIT = True

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AOS_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))
BRAIN_DIR = os.path.join(AOS_ROOT, "AOS_Brain", "02_Memory_Logs")
OUTPUT_DIR = os.path.join(AOS_ROOT, "data", "models")


def load_brain_dataset() -> Dataset:
    """Ingest markdown from AOS_Brain vault only. No ARC data for FIM model."""
    texts = []

    md_files = glob.glob(os.path.join(BRAIN_DIR, "*.md"))
    for fpath in md_files:
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                texts.append(
                    f"<start_of_turn>system\nYou are NemoClaw, a sovereign AI coding assistant.<end_of_turn>\n"
                    f"<start_of_turn>user\nSummarize this insight:<end_of_turn>\n"
                    f"<start_of_turn>model\n{content}<end_of_turn>"
                )
    print(f"  Brain vault: {len(texts)} samples (FIM model — no ARC data)")

    if not texts:
        print(f"WARNING: No training data found. Using placeholder.")
        return Dataset.from_dict({
            "text": [
                "<start_of_turn>user\nWhat is the capital of Germany?<end_of_turn>\n<start_of_turn>model\nThe capital of Germany is Berlin.<end_of_turn>",
                "<start_of_turn>user\nFix the off-by-one error in the loop.<end_of_turn>\n<start_of_turn>model\nChange `i < len(arr)` to `i < len(arr) - 1` to avoid IndexError.<end_of_turn>",
            ]
        })

    print(f"  Total: {len(texts)} training samples")
    return Dataset.from_dict({"text": texts})


def prepare_model():
    """Load the base model with 4-bit quantization and inject LoRA adapters."""
    print("Loading Qwen2.5-3B for FIM/Autocomplete...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/Qwen2.5-3B-Instruct-bnb-4bit",
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=DTYPE,
        load_in_4bit=LOAD_IN_4BIT,
    )

    print("Injecting LoRA Adapters...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    return model, tokenizer


def train(model, tokenizer, dataset: Dataset):
    """Run the SFTTrainer with extreme memory constraints."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        dataset_num_proc=2,
        packing=False,
        args=TrainingArguments(
            per_device_train_batch_size=1,
            gradient_accumulation_steps=4,
            warmup_steps=5,
            max_steps=30,
            learning_rate=2e-4,
            fp16=True,
            bf16=False,
            logging_steps=1,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=3407,
            output_dir=os.path.join(OUTPUT_DIR, "checkpoints_3b"),
        ),
    )

    print("Starting QLoRA training cycle...")
    trainer.train()
    print("Training complete.")

    return model, tokenizer


if __name__ == "__main__":
    model, tokenizer = prepare_model()
    dataset = load_brain_dataset()
    model, tokenizer = train(model, tokenizer, dataset)
    
    output_path = os.path.join(OUTPUT_DIR, "custom_qwen_3b")
    export_to_gguf(model, tokenizer, output_path, quant_method="q4_k_m")
    print("3B FIM training complete.")
