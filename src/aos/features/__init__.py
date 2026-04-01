"""
AOS Features — Inference Domain
Public API: router, set_backend_url, shadow_evaluation
"""
from aos.features.inference.router import router, set_backend_url
from aos.features.inference.service import shadow_evaluation, schedule_cooldown

__all__ = ["router", "set_backend_url", "shadow_evaluation", "schedule_cooldown"]
