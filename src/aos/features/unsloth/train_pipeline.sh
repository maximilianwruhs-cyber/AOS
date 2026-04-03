#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# NemoClaw Orchestrated Unsloth Training Pipeline
# Trains all 3 models SEQUENTIALLY with proper lifecycle phases.
# Hardware: GTX 1070 (8GB VRAM) — one model at a time!
# ═══════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AOS_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="$AOS_ROOT/data/training_logs"
MODEL_DIR="$AOS_ROOT/data/models"

mkdir -p "$LOG_DIR" "$MODEL_DIR"

echo "═══════════════════════════════════════════════════════════"
echo "⚡ NEMOCLAW AUTONOMOUS TRAINING CYCLE ⚡"
echo "Timestamp:  $TIMESTAMP"
echo "AOS Root:   $AOS_ROOT"
echo "═══════════════════════════════════════════════════════════"

# ─── GLOBAL SETUP PHASE ─────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════╗"
echo "║  PHASE 0: GLOBAL SETUP              ║"
echo "╚══════════════════════════════════════╝"

echo "[SETUP] Killing all inference servers to reclaim VRAM..."
pkill -9 -f "llama-server" || true
sleep 3

echo "[SETUP] Verifying GPU state..."
nvidia-smi --query-gpu=memory.used,memory.total,temperature.gpu --format=csv,noheader 2>/dev/null || echo "  nvidia-smi unavailable, proceeding blind"

echo "[SETUP] Activating Python environment..."
source "$AOS_ROOT/.venv/bin/activate"

echo "[SETUP] Global setup complete."
echo ""

# ─── TRAINING FUNCTION ──────────────────────────────────────────
train_model() {
    local MODEL_NAME="$1"
    local TRAIN_SCRIPT="$2"
    local MODEL_NUM="$3"
    local LOG_FILE="$LOG_DIR/train_${MODEL_NAME}_${TIMESTAMP}.log"

    echo "╔══════════════════════════════════════╗"
    echo "║  MODEL $MODEL_NUM/3: $MODEL_NAME"
    echo "╚══════════════════════════════════════╝"

    # ── Warmup Phase ──
    echo "  [WARMUP] Clearing GPU caches..."
    python3 -c "import torch; torch.cuda.empty_cache(); print('  [WARMUP] CUDA cache cleared')" 2>/dev/null || true
    sleep 2

    echo "  [WARMUP] Pre-flight VRAM check..."
    nvidia-smi --query-gpu=memory.used --format=csv,noheader 2>/dev/null || echo "  [WARMUP] nvidia-smi unavailable"

    # ── Training Phase ──
    echo "  [TRAIN] Starting QLoRA fine-tuning for $MODEL_NAME..."
    echo "  [TRAIN] Logging to: $LOG_FILE"

    if python3 "$TRAIN_SCRIPT" 2>&1 | tee "$LOG_FILE"; then
        echo "  [TRAIN] $MODEL_NAME training SUCCEEDED."
    else
        echo "  [TRAIN] ERROR: $MODEL_NAME training FAILED. Check $LOG_FILE"
        echo "  [TRAIN] Continuing to next model..."
        return 1
    fi

    # ── Cooldown Phase ──
    echo "  [COOLDOWN] Flushing GPU memory..."
    python3 -c "import torch; torch.cuda.empty_cache(); import gc; gc.collect()" 2>/dev/null || true
    sleep 5

    echo "  [COOLDOWN] Post-training VRAM check..."
    nvidia-smi --query-gpu=memory.used --format=csv,noheader 2>/dev/null || echo "  [COOLDOWN] nvidia-smi unavailable"

    echo "  [COOLDOWN] $MODEL_NAME cycle complete."
    echo ""
    return 0
}

# ─── SEQUENTIAL TRAINING CYCLES ─────────────────────────────────

echo "╔══════════════════════════════════════╗"
echo "║  PHASE 1: SEQUENTIAL TRAINING       ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Model 1: Qwen2.5-0.5B Drafter (smallest, fastest, safest first)
train_model "qwen_drafter_05b" "$SCRIPT_DIR/train_qwen_drafter.py" "1"
DRAFTER_OK=$?

# Model 2: Ministral-3B FIM (medium, autocomplete)
train_model "ministral_3b_fim" "$SCRIPT_DIR/train_ministral_3b.py" "2"
FIM_OK=$?

# Model 3: Qwen2.5-7B Target (largest, most VRAM-hungry, last)
train_model "qwen_target_7b" "$SCRIPT_DIR/train_qwen_7b.py" "3"
TARGET_OK=$?

# ─── GLOBAL COOLDOWN PHASE ──────────────────────────────────────
echo "╔══════════════════════════════════════╗"
echo "║  PHASE 2: GLOBAL COOLDOWN           ║"
echo "╚══════════════════════════════════════╝"

echo "[COOLDOWN] Final GPU memory flush..."
python3 -c "import torch; torch.cuda.empty_cache(); import gc; gc.collect()" 2>/dev/null || true
sleep 3

echo "[COOLDOWN] Verifying exported GGUFs..."
for gguf in "$MODEL_DIR"/*.gguf; do
    if [ -f "$gguf" ]; then
        SIZE=$(du -h "$gguf" | cut -f1)
        echo "  Found: $(basename "$gguf") ($SIZE)"
    fi
done

# ─── REBOOT PHASE ───────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════╗"
echo "║  PHASE 3: ENGINE REBOOT             ║"
echo "╚══════════════════════════════════════╝"

echo "[REBOOT] Relaunching Sovereign Command Center..."
cd "$AOS_ROOT"
./start_engine.sh > engine.log 2>&1 &
ENGINE_PID=$!
sleep 3

./start_autocomplete.sh > autocomplete.log 2>&1 &
AUTO_PID=$!
sleep 2

echo "[REBOOT] Engine PID: $ENGINE_PID | Autocomplete PID: $AUTO_PID"

# ─── BENCHMARK PHASE ────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════╗"
echo "║  PHASE 4: POST-TRAINING BENCHMARK   ║"
echo "╚══════════════════════════════════════╝"

echo "[BENCH] Waiting 10s for engines to fully warm up..."
sleep 10

echo "[BENCH] Running full benchmark suite against freshly trained models..."
BENCH_LOG="$LOG_DIR/benchmark_post_train_$TIMESTAMP.log"

python3 -m aos.features.benchmark.runner bench \
    --model "qwen2.5-7b" \
    --suite full \
    --ollama-url "http://127.0.0.1:1238/v1" \
    --quiet 2>&1 | tee "$BENCH_LOG"

BENCH_OK=$?

if [ $BENCH_OK -eq 0 ]; then
    echo "[BENCH] Benchmark completed successfully."
    echo "[BENCH] Running comparison leaderboard..."
    python3 -m aos.features.benchmark.runner compare 2>&1 | tee -a "$BENCH_LOG"
else
    echo "[BENCH] WARNING: Benchmark failed. Check $BENCH_LOG"
fi

# ─── SUMMARY ────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "⚡ TRAINING CYCLE COMPLETE ⚡"
echo "═══════════════════════════════════════════════════════════"
echo "  Drafter (0.5B):   $([ $DRAFTER_OK -eq 0 ] && echo '✅ OK' || echo '❌ FAILED')"
echo "  FIM (3B):         $([ $FIM_OK -eq 0 ] && echo '✅ OK' || echo '❌ FAILED')"
echo "  Target (7B):      $([ $TARGET_OK -eq 0 ] && echo '✅ OK' || echo '❌ FAILED')"
echo "  Logs:             $LOG_DIR"
echo "  Timestamp:        $TIMESTAMP"
echo "  Inference:        RESUMED"
echo "═══════════════════════════════════════════════════════════"
