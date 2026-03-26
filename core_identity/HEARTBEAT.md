# HEARTBEAT.md – GZMO Pulse (LOCAL ONLY)
# ──────────────────────────────────────
# Last tuned: 2026-03-20
# Purpose: Minimal local checks.

## Execution Rules
- Total reasoning + output < ~500 tokens.
- Late night (23:00–08:00) → HEARTBEAT_OK unless critical.

## Checklist
1. Evolution State (Local)
   - Ensure Obulus project is present and local Ollama is expected.

2. Token Efficiency
   - Run `scripts/gzmo_watchdog.py`.
   - Alert if > 100k tokens in main session.

3. Git Health
   - quick check if local is ahead.

## State Tracking
Update memory/heartbeat-state.json.
