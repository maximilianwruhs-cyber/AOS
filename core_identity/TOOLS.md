# LOCAL-BINDINGS.md
# ──────────────────────────────────────
# GZMO's Environment-Specific Cheat Sheet & Bindings
# Last audited: 2026-03-21
# Purpose: Device names, IPs, aliases, voices — stuff unique to *this* setup.
#          Never commit secrets here. Use vault / .secrets / env vars.
#
# ⚠️ POST-PURGE NOTICE (2026-03-20): All entries below predate the local-only
#    transition. Entries marked [UNVERIFIED] need confirmation before use.
# Rules:
#   - Risk-tagged entries require explicit user confirmation before use
#   - If something looks stale → flag in HEARTBEAT.md review
#   - Format: YAML per section for easy parsing / future tool access

## cameras [UNVERIFIED — verify IPs are still reachable]
living-room:
  description: "Main area, 180° wide-angle, ceiling mount"
  rtsp_url: "rtsp://admin:REDACTED@192.168.1.55:554/stream1"   # high_risk
  motion_zone: "entryway + sofa"
  preferred_resolution: "1280x720"
  risk: high                # → always ask before streaming / recording

front-door:
  description: "Entrance, motion-triggered, night vision"
  rtsp_url: "rtsp://admin:REDACTED@192.168.1.56:554/stream1"   # high_risk
  risk: high

## ssh [UNVERIFIED — verify hosts are still reachable]
home-server:
  host: "192.168.1.100"
  user: "admin"
  port: 22
  key_comment: "2025-12 ed25519 GZMO@home"
  aliases:
    - "update": "sudo apt update && sudo apt upgrade -y && sudo apt autoremove"
    - "logs-nginx": "docker logs -f --tail 300 nginx-proxy"
  risk: medium              # → warn before sudo / destructive commands

backup-nas:
  host: "192.168.1.101"
  user: "gzmo"
  aliases:
    - "mount": "sshfs gzmo@192.168.1.101:/volume1/backup /mnt/nas-backup"
  risk: low

## tts & audio
preferred_voice: "Nova"               # warm, slightly British, natural prosody
default_speaker: "Kitchen HomePod"
volume_default: 0.65
fallback_voice: "Daniel"              # crisp, neutral, good for long reads
quiet_hours_start: "22:00"
quiet_hours_end:   "07:30"
risk: low

## network & services [UNVERIFIED — verify endpoints are still active]
tailscale_exit_node: "home-server"       # may be decommissioned
preferred_dns: "1.1.1.1"
homeassistant_url: "http://192.168.1.10:8123"   # may be decommissioned
risk: low

## high-risk global flags
high_risk_keywords:
  - "rtsp://"
  - "password"
  - "token"
  - "sudo rm"
  - "dd if="
  - "mkfs"
confirmation_required_for:
  - high_risk
  - any command containing high_risk_keywords

## heartbeat hooks (auto-refresh candidates)
auto_refresh_candidates:
  - "Scan local network for new .local / mDNS devices every 30 days"
  - "Check if home-server IP changed (tailscale status) every 14 days"
  - "Ping known cameras → flag offline ones in next heartbeat"

## usage notes for GZMO
- When user mentions a camera/SSH alias → resolve via this file first
- Never inject full secrets into reasoning trace or prompt
- If entry missing or looks wrong → propose update + ask user
- Prefer calling a lightweight get_binding() helper if implemented

_End LOCAL-BINDINGS.md_
