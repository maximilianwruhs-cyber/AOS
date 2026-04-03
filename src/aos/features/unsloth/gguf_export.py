"""
Shared GGUF export utility for AOS training scripts.
Uses TurboQuant's llama.cpp build instead of Unsloth's sudo-requiring installer.
"""

import os
import subprocess
import sys

# Paths to TurboQuant llama.cpp tools
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AOS_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))
TURBOQUANT_DIR = os.path.join(AOS_ROOT, "..", "TurboQuant")
CONVERTER = os.path.join(TURBOQUANT_DIR, "convert_hf_to_gguf.py")
QUANTIZER = os.path.join(TURBOQUANT_DIR, "build", "bin", "llama-quantize")


def export_to_gguf(model, tokenizer, output_dir: str, quant_method: str = "q4_k_m"):
    """
    Export a fine-tuned model to GGUF format.
    
    1. Merge LoRA adapters and save 16-bit HF weights
    2. Convert HF → GGUF F16 using TurboQuant's converter
    3. Quantize GGUF F16 → target quant using TurboQuant's quantizer
    
    Args:
        model: The Unsloth model with LoRA adapters
        tokenizer: The model's tokenizer
        output_dir: Directory to save merged HF weights
        quant_method: GGUF quantization type (q4_k_m, q8_0, etc.)
    
    Returns:
        Path to the final quantized GGUF file, or None on failure
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Step 1: Save merged 16-bit weights
    print(f"[GGUF] Saving merged 16-bit weights to {output_dir}...")
    model.save_pretrained_merged(output_dir, tokenizer, save_method="merged_16bit")
    print(f"[GGUF] Merged weights saved.")
    
    # Step 2: Convert HF → GGUF F16
    f16_gguf = f"{output_dir}.f16.gguf"
    print(f"[GGUF] Converting HF → GGUF F16...")
    
    if not os.path.exists(CONVERTER):
        print(f"[GGUF] WARNING: Converter not found at {CONVERTER}")
        print(f"[GGUF] Merged HF weights are at: {output_dir}")
        return None
    
    result = subprocess.run(
        [sys.executable, CONVERTER, output_dir, "--outfile", f16_gguf, "--outtype", "f16"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"[GGUF] Conversion failed: {result.stderr[-500:]}")
        return None
    print(f"[GGUF] F16 GGUF created: {f16_gguf}")
    
    # Step 3: Quantize
    quant_gguf = f"{output_dir}.{quant_method.upper()}.gguf"
    print(f"[GGUF] Quantizing to {quant_method}...")
    
    if not os.path.exists(QUANTIZER):
        print(f"[GGUF] WARNING: Quantizer not found at {QUANTIZER}")
        return f16_gguf
    
    result = subprocess.run(
        [QUANTIZER, f16_gguf, quant_gguf, quant_method],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"[GGUF] Quantization failed: {result.stderr[-500:]}")
        return f16_gguf
    
    # Cleanup F16 (it's large and we have the quantized version)
    os.remove(f16_gguf)
    print(f"[GGUF] Done: {quant_gguf}")
    return quant_gguf
