#!/bin/bash
# AOS Training Orchestrator
# Executes SFT and GRPO training sequentially

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AOS_DIR="$(dirname "$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")")"

echo "=========================================================="
echo "⚡ AOS TRAINING ORCHESTRATOR ⚡"
echo "Target: Gemma 4 E4B | Drafter: Gemma 4 E2B"
echo "=========================================================="

cd "$AOS_DIR"
source .venv/bin/activate

echo ""
echo "[1/4] Preprocessing Data..."
python3 -m aos.features.unsloth.preprocess_arc --format gemma4 --drafter-cap 300 --augment

echo ""
echo "[2/4] Training Target SFT (Gemma 4 E4B)..."
python3 -m aos.features.unsloth.train_gemma4_e4b

echo ""
echo "[3/4] Training Drafter SFT (Gemma 4 E2B)..."
python3 -m aos.features.unsloth.train_gemma4_e2b

echo ""
echo "[4/4] Training Target GRPO (Gemma 4 E4B)..."
python3 -m aos.features.unsloth.train_grpo_arc

echo ""
echo "=========================================================="
echo "🎯 ALL TRAINING PHASES COMPLETED SUCCESSFULLY!"
echo "Models exported to: $AOS_DIR/data/models/"
echo "You can now push them to LM Studio and start the engine."
echo "=========================================================="
