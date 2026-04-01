#!/bin/bash
# =============================================================================
# AOS Sovereign Gateway Launcher
# Starts the FastAPI/Uvicorn backend that handles telemetry and the VS Codium Dashboard
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Starting AOS sovereign Gateway..."
cd "$SCRIPT_DIR" || exit 1

# Activate virtual environment if present
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Ensure src module pathing is strictly enforced
export PYTHONPATH="src"

# Launch application
python3 -m aos.gateway.app
