#!/bin/bash
# AOS Sovereign Inference Engine Launcher
# Architecture: Gemma 4 E4B (Target) + Gemma 4 E2B (Speculative Drafter)
# Drafter speed: extremely fast | Same Gemma tokenizer = high acceptance rate
# Hardware: GTX 1070 (8GB VRAM) | Q4 KV cache compression

echo "=========================================================="
echo "⚡ IGNITING SOVEREIGN AI SPECULATIVE ENGINE ⚡"
echo "Target:  Gemma-4-E4B-it (Q4_K_M)"
echo "Drafter: Gemma-4-E2B-it (Q4_K_M)"
echo "Sampling Defaults: temp=1.0 | top_p=0.95 | top_k=64"
echo "Port: 1238 | Context: 8192 | Hardware: GTX 1070"
echo "=========================================================="

# Kill leftover nodes
pkill -9 -f "llama-server" || true

# Wait until VRAM is freed (less than 500MB used)
echo "Waiting for VRAM to clear..."
while [ $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) -gt 500 ]; do
  sleep 1
done
echo "VRAM cleared."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEVSTACK_DIR="$(dirname "$SCRIPT_DIR")"

"$DEVSTACK_DIR/TurboQuant/build/bin/llama-server" \
  -m ~/.lmstudio/models/unsloth/gemma-4-E4B-it-GGUF/gemma-4-E4B-it-Q4_K_M.gguf \
  -md ~/.lmstudio/models/unsloth/gemma-4-E2B-it-GGUF/gemma-4-E2B-it-Q4_K_M.gguf \
  -c 8192 \
  -ctk q8_0 -ctv q8_0 \
  --temp 1.0 --top-p 0.95 --top-k 64 \
  --port 1238
