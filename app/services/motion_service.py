"""Motion service: LLM-driven dynamic interpretation of a temperament profile.

Produces a "motion" reading — how the four temperament tendencies
(Sanguine, Choleric, Melancholic, Phlegmatic) interact, shift in strength,
and carry a person across situations such as social settings, work, stress,
and rest. Non-diagnostic; framed as reflective tendencies, not fixed traits.
"""

import re
from typing import Dict, Any, List, Tuple, Optional
from app.core.llm import BaseLLM, get_llm

PROMPT_VERSION = "v1.0.0-temperament-motion"

MOTION_SYSTEM_PROMPT = """You are Agent Bleu's reflective assessment assistant.
Translate quantitative temperament scores into a dynamic "motion" reading: how the
four temperament tendencies (Sanguine, Choleric, Melancholic, Phlegmatic) interact,
shift in strength, and carry the person across situations such as social settings,
work, stress, and rest.
CRITICAL RULES:
1. Do NOT make clinical diagnoses or psychological disorder assertions.
2. Frame everything as 'reflective tendencies' or 'behavioral inclinations', never as fixed traits or disorders.
3. Every numeric score you mention MUST EXACTLY match the provided scores.
4. Keep the tone empathetic, objective, and culturally neutral.
5. Write 2-3 short paragraphs describing the flow of tendencies across situations.
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
    """Verify that numbers in the text don't hallucinate or contradict official scores."""
    valid_numbers = set()
    for s in scores:
        val = s.get("score") or s.get("normalized_score")
        if val is not None:
            valid_numbers.add(float(val))
            valid_numbers.add(int(round(float(val))))

    extracted_nums = [float(n) for n in re.findall(r"\b\d+(?:\.\d+)?\b", narrative_text)]
    discrepancies = []
    for num in extracted_nums:
        if num in (100.0, 5.0, 1.0, 10.0, 0.0):
            continue
        if not any(abs(num - v) < 0.1 for v in valid_numbers) and num > 10:
            discrepancies.append(f"Unverified number '{num}' appeared in motion reading.")

    return len(discrepancies) == 0, discrepancies


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


def generate_motion_interpretation(
    scores: list[dict],
    user_id: str,
    llm: BaseLLM = None,
    emotion_rows: list[dict] | None = None,
) -> Dict[str, Any]:
    """Generate a dynamic trait-motion interpretation using the LLM."""
    llm = llm or get_llm()

    context = format_scores_context(scores)
    emotion_context = format_emotion_context(emotion_rows)
    prompt = (
        f"User Scores:\n{context}\n\n"
        f"Emotion Self-Reports:\n{emotion_context}\n\n"
        "Describe how these temperament tendencies move and interact across different "
        "situations — social settings, focused work, stress, and rest — and which "
        "combinations tend to dominate when. Keep it grounded in the scores above."
    )

    generated_text = llm.generate(prompt=prompt, system=MOTION_SYSTEM_PROMPT, max_tokens=600)

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
            f"Your profile shows a dynamic interplay between the {lead_dims[0]} and "
            f"{lead_dims[1]} tendencies. Depending on the situation — social settings, "
            "focused work, stress, or rest — one tendency may step forward while the "
            "others hold steady, creating your characteristic rhythm of response."
        )

    return {
        "motion": generated_text,
        "prompt_version": PROMPT_VERSION,
        "llm_model": getattr(llm, "model", "NullLLM"),
        "numeric_consistency_verified": is_valid,
        "discrepancies": discrepancies,
    }
