"""
AOS Benchmark — Evaluator
Scores model outputs against verifiable ground truth.
Async-compatible for non-blocking LLM-as-Judge calls.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import config
from simulation.sandbox_executor import SandboxExecutor

import httpx


GENERIC_QUALITY_RUBRIC = """
Rate the response quality on these dimensions:
1. Relevance: Does it answer what was asked?
2. Correctness: Is the information accurate?
3. Completeness: Does it cover the topic adequately?
4. Clarity: Is it well-structured and understandable?
Give an overall score from 0.0 to 1.0 based on how well the response satisfies these criteria.
Reply with ONLY a decimal number between 0.0 and 1.0. Nothing else.
SCORE:
"""


def _normalize(text: str) -> str:
    """Strip whitespace, punctuation, lowercase for comparison."""
    text = text.strip().lower()
    text = re.sub(r'[^a-z0-9.]', '', text)
    return text


def _extract_number(text: str) -> str | None:
    """Extract the first number from text."""
    m = re.search(r'-?\d+\.?\d*', text)
    return m.group(0) if m else None


def score_math(output: str, expected: str) -> float:
    """Score a math task: 1.0 if correct, 0.0 if not."""
    extracted = _extract_number(output)
    if extracted is None:
        return 0.0
    try:
        return 1.0 if float(extracted) == float(expected) else 0.0
    except ValueError:
        return 0.0


def score_factual(output: str, expected: str) -> float:
    """Score a factual task: 1.0 if answer is contained in output."""
    return 1.0 if expected.lower() in output.lower() else 0.0


def score_code(output: str, test_code: str) -> float:
    """Score a code task: extract Python code, run with test, check for PASS."""
    code = output
    match = re.search(r'```(?:python)?\s*\n(.*?)```', output, re.DOTALL)
    if match:
        code = match.group(1)

    dangerous = ['import os', 'import subprocess', 'import shutil', 'open(', '__import__',
                 'eval(', 'exec(', 'system(', 'rmdir', 'unlink']
    for d in dangerous:
        if d in code:
            return 0.0

    full_code = f"{code}\n{test_code}"
    executor = SandboxExecutor(timeout=5)
    success, msg = executor.run_code(full_code)
    return 1.0 if success and 'PASS' in msg else 0.0


async def score_reasoning(output: str, rubric: str, judge_url: str = None,
                          judge_model: str = None) -> float:
    """Score a reasoning task using LLM-as-judge with a structured rubric."""
    judge_url = judge_url or config.OLLAMA_URL
    judge_model = judge_model or config.DEFAULT_MODEL

    judge_prompt = (
        f"You are a strict, impartial evaluator. Score the following response against the rubric.\n\n"
        f"RUBRIC:\n{rubric}\n\n"
        f"RESPONSE:\n{output[:800]}\n\n"
        f"Score from 0.0 to 1.0 based on how well the response satisfies the rubric.\n"
        f"Reply with ONLY a decimal number between 0.0 and 1.0. Nothing else.\n"
        f"SCORE:"
    )

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{judge_url}/chat/completions",
                json={
                    "model": judge_model,
                    "messages": [{"role": "user", "content": judge_prompt}],
                    "temperature": 0.1,
                    "max_tokens": 10
                },
                timeout=30.0,
            )
        text = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "0.0")
        m = re.search(r'([0-1]\.\d+|[01])', text)
        return float(m.group(1)) if m else 0.0
    except Exception:
        return _heuristic_reasoning_score(output, rubric)


async def score_generic_quality(output: str, judge_url: str = None,
                                judge_model: str = None) -> float:
    """Score any response with a generic quality rubric. Used by Shadow Evaluator."""
    return await score_reasoning(output, GENERIC_QUALITY_RUBRIC, judge_url, judge_model)


def _heuristic_reasoning_score(output: str, rubric: str) -> float:
    """Fallback scoring when LLM judge is unavailable."""
    if len(output.strip()) < 20:
        return 0.0
    keywords = re.findall(r'\b[A-Za-z]{4,}\b', rubric.lower())
    if not keywords:
        return 0.5
    hits = sum(1 for kw in keywords if kw in output.lower())
    return min(1.0, hits / max(1, len(keywords) * 0.5))


async def score_task(task: dict, output: str, **kwargs) -> float:
    """Score any task based on its type."""
    task_type = task.get("type", "")

    if task_type == "math":
        return score_math(output, task["answer"])
    elif task_type == "factual":
        return score_factual(output, task["answer"])
    elif task_type == "code":
        return score_code(output, task["test"])
    elif task_type == "reasoning":
        return await score_reasoning(output, task["rubric"], **kwargs)
    else:
        return 0.0

