"""
AOS Features — Inference Domain
Public API for the inference feature slice.
"""
# NOTE: We intentionally do NOT re-export `router` here to avoid
# shadowing the `aos.features.inference.router` submodule.
# Use: from aos.features.inference.router import router
# Or:  import aos.features.inference.router as inf_mod

from aos.features.inference.service import (  # noqa: F401
    set_backend_url,
    shadow_evaluation,
    schedule_cooldown,
)

__all__ = ["set_backend_url", "shadow_evaluation", "schedule_cooldown"]
