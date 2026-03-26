# AOS Core Identity Scripts

This directory contains the distilled "personality" and behavioral rules of the Agentic OS, salvaged directly from the original OpenClaw architectural design.

When configuring the system prompt for `AOS` (specifically inside LM Studio or `aos_daemon.py`), these files define the sovereign intelligence profile:
- `IDENTITY.md`: Who AOS is (Chief of Staff).
- `MEMORY.md`: How AOS extracts logs without database sprawl.
- `AGENTS.md` & `TOOLS.md`: The operational parameters.
- `HEARTBEAT.md` & `SOUL.md`: Ethical and behavioral governors.

These exist as markdown blueprints so that any frontier class model (`llama-3-70b`, `gpt-4o`) can read them autonomously to adopt the correct persona when hooked up to the AOS Python Engine.
