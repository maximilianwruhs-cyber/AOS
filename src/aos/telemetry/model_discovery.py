"""
AOS — Model Discovery
Auto-discovers locally available Ollama models for multi-model competition.
"""
import requests
import sys
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path

import aos.config as config


@dataclass
class ModelInfo:
    name: str
    size_bytes: int
    parameter_size: str  # e.g., "7.6B", "1.5B"
    family: str          # e.g., "qwen2", "llama"
    quantization: str    # e.g., "Q4_K_M", "F16"

    @property
    def size_gb(self) -> float:
        return round(self.size_bytes / (1024 ** 3), 2)

    @property
    def is_embedding(self) -> bool:
        """Embedding models can't do generation."""
        return "embed" in self.name.lower() or "bert" in self.family.lower()

    def __repr__(self):
        return f"<Model {self.name} | {self.parameter_size} | {self.quantization} | {self.size_gb}GB>"


def discover_models(ollama_url: str = None, exclude_embeddings: bool = True) -> List[ModelInfo]:
    """
    Auto-discover all locally available Ollama models.
    Filters out embedding models by default (they can't generate text).
    """
    url = ollama_url or config.OLLAMA_URL
    try:
        resp = requests.get(f"{url}/models", timeout=10)
        data = resp.json()
    except Exception as e:
        print(f"  [DISCOVERY] Failed to reach LM Studio at {url}: {e}")
        return []

    models = []
    for m in data.get("data", []):
        name = m.get("id", "unknown")
        # OpenAI format doesn't natively expose params/quant as cleanly, we parse from ID if possible
        info = ModelInfo(
            name=name,
            size_bytes=m.get("size", 0) if "size" in m else 0, # Often zero in simple API
            parameter_size="unknown",
            family="unknown",
            quantization="unknown",
        )

        if exclude_embeddings and info.is_embedding:
            continue

        models.append(info)

    # Sort by parameter size (smallest first → interesting for efficiency)
    models.sort(key=lambda m: m.size_bytes)
    return models


def print_discovered_models(models: List[ModelInfo]):
    """Pretty-print discovered models."""
    print(f"\n  {'='*55}")
    print(f"  DISCOVERED MODELS ({len(models)} generative)")
    print(f"  {'='*55}")
    print(f"  {'Model':<30} {'Params':>8} {'Size':>7} {'Quant':<8}")
    print(f"  {'─'*30} {'─'*8} {'─'*7} {'─'*8}")
    for m in models:
        print(f"  {m.name:<30} {m.parameter_size:>8} {m.size_gb:>6.1f}G {m.quantization:<8}")
    print(f"  {'='*55}\n")
