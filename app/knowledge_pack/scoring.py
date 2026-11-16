"""Pure domain psychometric scoring engine.

Implements standard Likert dimension scoring with reverse-key correction,
minimum-answer integrity gates, temperament normalization, emotional intelligence
competency scoring, and emotion burden indicator computation.
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict


def score_likert_dimension(
    answers: List[int],
    reverse_keys: Optional[List[bool]] = None,
    minimum_answers: int = 1,
    scale_min: int = 1,
    scale_max: int = 5,
) -> Dict[str, Any]:
    """Score a single Likert dimension with reverse-key correction.

    Parameters:
      answers: list of integer responses (e.g. [1, 2, 3, 4, 5])
      reverse_keys: list of bools indicating which items to invert.
      minimum_answers: threshold below which dimension is marked 'incomplete'.
      scale_min: minimum scale score (e.g. 1)
      scale_max: maximum scale score (e.g. 5)

    Returns:
      dict with:
        - "raw_mean": arithmetic mean (or None if incomplete)
        - "score": 0.0 to 100.0 normalized score (or None if incomplete)
        - "status": "complete" or "incomplete"
        - "n_items": number of valid answers submitted
    """
    if reverse_keys is None:
        reverse_keys = [False] * len(answers)

    # Validate range
    for val in answers:
        if val < scale_min or val > scale_max:
            raise ValueError(f"Answer {val} outside valid scale range [{scale_min}, {scale_max}].")

    if len(answers) < minimum_answers or len(answers) == 0:
        return {
            "raw_mean": None,
            "score": None,
            "status": "incomplete",
            "n_items": len(answers),
        }

    corrected_values = []
    for val, rev in zip(answers, reverse_keys):
        if rev:
            corrected = (scale_min + scale_max) - val
        else:
            corrected = val
        corrected_values.append(corrected)

    mean_val = sum(corrected_values) / len(corrected_values)
    # Scale from [scale_min, scale_max] -> [0.0, 100.0]
    norm_score = round(((mean_val - scale_min) / (scale_max - scale_min)) * 100.0, 1)

    return {
        "raw_mean": round(mean_val, 2),
        "score": norm_score,
        "status": "complete",
        "n_items": len(answers),
    }


def score_temperaments(
    dimension_answers: Dict[str, List[int]],
    dimension_reverse_keys: Optional[Dict[str, List[bool]]] = None,
    minimum_answers_per_dim: int = 8,
) -> Dict[str, Any]:
    """Score all four classical temperament dimensions.

    Parameters:
      dimension_answers: dict mapping dimension ('sanguine', 'choleric', etc.) to answer lists
      dimension_reverse_keys: optional dict mapping dimension to bool reverse keys
      minimum_answers_per_dim: required threshold for full completion

    Returns:
      dict with dimension breakdown, status ('complete' or 'partial'), and leading tendencies
    """
    dims = ["sanguine", "choleric", "melancholic", "phlegmatic"]
    results = {}
    is_fully_complete = True

    for d in dims:
        answers = dimension_answers.get(d, [])
        revs = (dimension_reverse_keys or {}).get(d, [False] * len(answers))
        dim_res = score_likert_dimension(
            answers=answers,
            reverse_keys=revs,
            minimum_answers=minimum_answers_per_dim,
            scale_min=1,
            scale_max=5,
        )
        results[d] = dim_res
        if dim_res["status"] != "complete":
            is_fully_complete = False

    # Rank leading tendencies among completed dimensions
    completed_dims = [
        (d, res["score"])
        for d, res in results.items()
        if res["score"] is not None
    ]
    completed_dims.sort(key=lambda x: x[1], reverse=True)

    return {
        "status": "complete" if is_fully_complete else "partial",
        "dimensions": results,
        "leading_tendencies": [d for d, _ in completed_dims[:2]],
    }


def score_emotional_intelligence(
    domain_answers: Dict[str, List[int]],
    domain_reverse_keys: Optional[Dict[str, List[bool]]] = None,
    minimum_answers_per_domain: int = 3,
) -> Dict[str, Any]:
    """Score the five Goleman emotional intelligence competency domains."""
    domains = ["self_awareness", "self_regulation", "intrinsic_motivation", "empathy", "social_skills"]
    results = {}
    is_fully_complete = True

    for dom in domains:
        answers = domain_answers.get(dom, [])
        revs = (domain_reverse_keys or {}).get(dom, [False] * len(answers))
        dom_res = score_likert_dimension(
            answers=answers,
            reverse_keys=revs,
            minimum_answers=minimum_answers_per_domain,
            scale_min=1,
            scale_max=5,
        )
        results[dom] = dom_res
        if dom_res["status"] != "complete":
            is_fully_complete = False

    return {
        "status": "complete" if is_fully_complete else "partial",
        "domains": results,
    }


def score_emotion_indicator(
    frequency_val: Any,
    intensity: int,
    duration_val: Any,
    impact_val: Optional[Any] = 1,
) -> Dict[str, Any]:
    """Calculate the emotional burden index from frequency, intensity, duration, and impact.

    Supports both numeric and string values ('rarely', 'several hours', etc.).
    """
    if intensity < 0 or intensity > 10:
        raise ValueError(f"Intensity {intensity} out of range [0, 10].")

    # Map frequencies
    freq_map = {
        "rarely": 1, 1: 1,
        "sometimes": 2, 2: 2,
        "often": 3, 3: 3,
        "very_often": 4, 4: 4,
    }
    freq_weight = freq_map.get(str(frequency_val).lower(), freq_map.get(frequency_val, 2))

    # Map durations
    dur_map = {
        "minutes": 1, 1: 1, "a few minutes": 1,
        "hours": 2, 2: 2, "several hours": 2,
        "days": 3, 3: 3, "multiple days": 3,
        "weeks": 4, 4: 4, "varies": 2,
    }
    dur_weight = dur_map.get(str(duration_val).lower(), dur_map.get(duration_val, 2))

    # Map impact
    imp_map = {
        "none": 1, 1: 1,
        "mild": 2, 2: 2,
        "moderate": 3, 3: 3,
        "severe": 4, 4: 4,
    }
    imp_weight = imp_map.get(str(impact_val).lower(), imp_map.get(impact_val, 1))

    # Calculate burden index (0.0 to 100.0)
    # Maximum base: 4 * 10 * 4 = 160
    burden_raw = ((freq_weight * intensity * dur_weight) / 160.0) * 100.0
    # Modulate slightly by functioning impact
    burden_index = round(min(100.0, max(0.0, burden_raw * (1.0 + (imp_weight - 1) * 0.05))), 1)

    if burden_index >= 60.0:
        band = "high"
    elif burden_index >= 30.0:
        band = "moderate"
    else:
        band = "low"

    return {
        "status": "complete",
        "score": burden_index,
        "burden_index": burden_index,
        "band": band,
    }
