"""Narrative generation, prompt versioning, and numeric consistency validator."""

import json
import re
from typing import Dict, Any, Tuple
from app.core.llm import BaseLLM, get_llm

PROMPT_VERSION = "v1.0.0-temperament-narrative"

NARRATIVE_SYSTEM_PROMPT = """You are PsychemetreAI's reflective assessment assistant.
Translate quantitative temperament scores into thoughtful, grounded reflective prose.
CRITICAL RULES:
1. Do NOT make clinical diagnoses or psychological disorder assertions.
2. Frame scores as 'reflective tendencies' or 'behavioral inclinations'.
3. Every numeric score you mention in prose MUST EXACTLY match the provided scores.
4. Keep the tone empathetic, objective, and culturally neutral.
"""


def format_scores_context(scores: list[dict]) -> str:
    lines = []
    for s in scores:
        dim = s.get("dimension")
        val = s.get("score") or s.get("normalized_score")
        interp = s.get("interpretation", "")
        lines.append(f"- {dim}: {val}/100 ({interp})")
    return "\n".join(lines)


def validate_numeric_consistency(narrative_text: str, scores: list[dict]) -> Tuple[bool, list[str]]:
    """Verify that numbers in the narrative text don't hallucinate or contradict official scores."""
    valid_numbers = set()
    for s in scores:
        val = s.get("score") or s.get("normalized_score")
        if val is not None:
            valid_numbers.add(float(val))
            valid_numbers.add(int(round(float(val))))

    # Extract all numbers mentioned in text
    extracted_nums = [float(n) for n in re.findall(r"\b\d+(?:\.\d+)?\b", narrative_text)]
    discrepancies = []

    for num in extracted_nums:
        # Ignore scale references like 100 or 1-5
        if num in (100.0, 5.0, 1.0, 10.0, 0.0):
            continue
        # If a score-like number appears but doesn't match any score
        closest_match = any(abs(num - v) < 0.1 for v in valid_numbers)
        if not closest_match and num > 10:
            discrepancies.append(f"Unverified number '{num}' appeared in narrative.")

    is_valid = len(discrepancies) == 0
    return is_valid, discrepancies


def generate_narrative_report(
    scores: list[dict],
    user_id: str,
    llm: BaseLLM = None
) -> Dict[str, Any]:
    """Generate narrative synthesis with prompt versioning and numeric validation."""
    llm = llm or get_llm()

    context = format_scores_context(scores)
    prompt = f"User Scores:\n{context}\n\nPlease generate a 2-3 paragraph reflective summary."

    generated_text = llm.generate(prompt=prompt, system=NARRATIVE_SYSTEM_PROMPT, max_tokens=600)

    # Validate numbers
    is_valid, discrepancies = validate_numeric_consistency(generated_text, scores)
    if not is_valid:
        # If discrepancy detected, fallback to safe deterministic synthesis
        lead_dims = [s["dimension"] for s in sorted(scores, key=lambda x: x.get("score") or x.get("normalized_score") or 0, reverse=True)[:2]]
        generated_text = (
            f"Your responses suggest prominent reflective tendencies in the {lead_dims[0]} "
            f"and {lead_dims[1]} dimensions. These reflect preferred ways of engaging with decisions, "
            f"social contexts, and tasks."
        )

    return {
        "narrative": generated_text,
        "prompt_version": PROMPT_VERSION,
        "llm_model": getattr(llm, "model", "NullLLM"),
        "numeric_consistency_verified": is_valid,
        "discrepancies": discrepancies,
    }
