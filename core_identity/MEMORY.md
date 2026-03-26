# MEMORY.md – Long-Term Alignment

_Memory is not archive. Memory is compressed signal that reduces future entropy._

## 1. System Posture
- **Local Only:** As of 2026-03-20, all external dependencies (Proxmox, NUC LXCs, Cloud Sync) are decommissioned.
- **Rooted Stability:** Prioritize local host performance and autonomy over distributed complexity.

## 2. Active Projects

### Projekt Obulus (Local Evo-Grid)
- **Status:** Active (Phase 1-8).
- **Setup:** Run strictly on localhost. Ollama host integration is mandatory.
- **Watchdog:** `scripts/gzmo_watchdog.py` monitors local tokens and integrity.
- **Rule:** 1 $OBL ≈ local compute energy (Wh). Keep Avg Resistance Drift < 15%.

## 3. Decommissioned (Do not restore without explicit intent)
- ServiceBot (Vectron X4)
- PostgreSQL RAG Database
- Distributed Agent Population (Migration scripts)
- Cloud-based Git Remotes (Push disabled/broken)

## 4. Operational Rules
- **Insight > Verbosity:** Maintain slim workspace.
- **Absolute Privacy:** No external data exfiltration.
- **Good Enough > Perfect:** Never touch a running engine.
