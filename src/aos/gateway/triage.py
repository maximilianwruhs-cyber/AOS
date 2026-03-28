"""
AOS Gateway — Prompt Complexity Triage
Classifies incoming prompts as 'tiny' or 'heavy' for model selection.
"""


def assess_complexity(messages: list) -> str:
    """Triage the payload complexity."""
    full_text = " ".join([m.get("content", "") for m in messages if isinstance(m.get("content"), str)])
    heavy_keywords = ["write code", "analyze", "explain", "python", "javascript", "c++", "refactor", "debug", "architect"]
    if len(full_text) > 1000:
        return "heavy"
    for kw in heavy_keywords:
        if kw in full_text.lower():
            return "heavy"
    return "tiny"
