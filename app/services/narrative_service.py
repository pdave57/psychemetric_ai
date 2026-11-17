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


def format_emotion_context(emotion_rows: list[dict] | None) -> str:
    """Render a compact, human-readable emotion summary for the LLM prompt."""
    if not emotion_rows:
        return "No emotion self-reports were submitted."

    lines = []
    for item in emotion_rows:
        lines.append(
            "- "
            f"{item.get('emotion', 'emotion')}: "
            f"intensity={item.get('intensity', 'n/a')}/10, "
            f"frequency={item.get('frequency', 'n/a')}, "
            f"duration={item.get('duration', 'n/a')}, "
            f"impact={item.get('impact', 'n/a')}, "
            f"burden_index={item.get('burden_index', 'n/a')}, "
            f"band={item.get('band', 'n/a')}"
        )
    return "\n".join(lines)


def generate_narrative_report(
    scores: list[dict],
    user_id: str,
    llm: BaseLLM = None,
    emotion_rows: list[dict] | None = None,
) -> Dict[str, Any]:
    """Generate a temperament + emotion narrative with prompt versioning and numeric validation."""
    llm = llm or get_llm()

    context = format_scores_context(scores)
    emotion_context = format_emotion_context(emotion_rows)
    prompt = (
        f"User Scores:\n{context}\n\n"
        f"Emotion Self-Reports:\n{emotion_context}\n\n"
        "Please generate a 2-3 paragraph reflective summary that explains the temperament pattern and "
        "how the reported emotions may reinforce or soften those tendencies."
    )

    generated_text = llm.generate(prompt=prompt, system=NARRATIVE_SYSTEM_PROMPT, max_tokens=600)

    # Validate numbers in the narrative, including temperament scores.
    is_valid, discrepancies = validate_numeric_consistency(generated_text, scores)
    if not is_valid:
        lead_dims = [
            s["dimension"]
            for s in sorted(
                scores,
                key=lambda x: x.get("score") or x.get("normalized_score") or 0,
                reverse=True,
            )[:2]
        ]
        if len(lead_dims) < 2:
            lead_dims = [s["dimension"] for s in scores[:2]]
        generated_text = (
            f"Your responses suggest prominent reflective tendencies in the {lead_dims[0]} "
            f"and {lead_dims[1]} dimensions. These patterns can shape how you engage with decisions, "
            f"social settings, and daily demands."
        )

    return {
        "narrative": generated_text,
        "prompt_version": PROMPT_VERSION,
        "llm_model": getattr(llm, "model", "NullLLM"),
        "numeric_consistency_verified": is_valid,
        "discrepancies": discrepancies,
    }
