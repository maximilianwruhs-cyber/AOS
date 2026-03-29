#!/usr/bin/env python3
"""
AOS — LM Studio MCP Bridge Server

Exposes locally-running LM Studio models as MCP tools so that any
MCP-compatible IDE (VS Codium, Antigravity, Gemini CLI) can delegate
tasks to your private, on-device AI.

Requirements (auto-installed by uv):
    fastmcp, httpx

Usage:
    uv run --with fastmcp --with httpx config/lm_studio_mcp.py
"""

import httpx
from fastmcp import FastMCP

mcp = FastMCP("LM Studio Bridge")

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
DEFAULT_TIMEOUT = 120.0


@mcp.tool()
def ask_lm_studio(prompt: str, system_prompt: str = "") -> str:
    """
    Sends a query to a locally running LM Studio instance and returns its answer.
    LM Studio must be running with the local server active on port 1234.
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": "local-model",  # LM Studio uses whatever model is loaded
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2048,
    }

    try:
        response = httpx.post(LM_STUDIO_URL, json=payload, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except httpx.ConnectError:
        return (
            "❌ Cannot connect to LM Studio on port 1234.\n"
            "Make sure LM Studio is running and the Local Server is ON."
        )
    except Exception as e:
        return f"❌ Error communicating with LM Studio: {e}"


if __name__ == "__main__":
    mcp.run()
