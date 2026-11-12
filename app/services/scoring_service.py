"""Scoring engine for the PsychemetreAI temperament questionnaire.

Weights, reverse-scoring, and normalisation are PROVISIONAL pending
expert review and psychometric validation.  The scoring version string
is embedded in every TemperamentScore row so that historical scores
remain attributable to the algorithm that produced them.
"""

from collections import defaultdict

DIMENSIONS = ("sanguine", "choleric", "melancholic", "phlegmatic")

SCORING_VERSION = "provisional-0.2.0"


def calculate_temperament_scores(questions, responses):
    """Return a dict mapping each dimension to its score dict (or None).

    ``questions``  — list of Question ORM objects (or SimpleNamespace in tests).
    ``responses``  — list of UserResponse ORM objects (or SimpleNamespace).

    Each response is expected to have a ``likert_value`` attribute.
    For backward compatibility with legacy ``raw_value`` attribute,
    the function falls back to ``raw_value`` when ``likert_value`` is absent.

    Returns::

        {
            "sanguine":    {"raw_mean": 3.5, "normalized_score": 62.5, "n_items": 4, "n_areas": 1},
            "choleric":    None,   # no items answered
            ...
        }
    """
    # Support both ORM objects (likert_value) and legacy SimpleNamespace (raw_value).
    def _value(r):
        return getattr(r, "likert_value", None) or getattr(r, "raw_value", None)

    response_map = {r.question_id: _value(r) for r in responses}
    totals  = defaultdict(float)
    weights = defaultdict(float)
    counts  = defaultdict(int)
    areas   = defaultdict(set)

    for q in questions:
        # Determine which dimension this question loads onto.
        loads = getattr(q, "loads", None)
        if loads:
            # New model: loads is a dict {dimension: weight}.
            for dimension, load in loads.items():
                if dimension not in DIMENSIONS:
                    continue
                if q.id not in response_map:
                    continue
                x = response_map[q.id]
                if x is None:
                    continue
                # Reverse-coding uses either attribute name.
                reverse = getattr(q, "reverse_coded", False) or getattr(q, "reverse_scored", False)
                if reverse:
                    x = 6 - x
                w = float(load) * float(getattr(q, "weight", 1.0) or 1.0)
                totals[dimension]  += x * w
                weights[dimension] += w
                counts[dimension]  += 1
                areas[dimension].add(getattr(q, "area", "default"))
        else:
            # Legacy path: dimension stored directly on the question.
            dimension = getattr(q, "dimension", None)
            if dimension not in DIMENSIONS:
                continue
            if q.id not in response_map:
                continue
            x = response_map[q.id]
            if x is None:
                continue
            reverse = getattr(q, "reverse_scored", False) or getattr(q, "reverse_coded", False)
            if reverse:
                x = 6 - x
            w = float(getattr(q, "weight", 1.0) or 1.0)
            totals[dimension]  += x * w
            weights[dimension] += w
            counts[dimension]  += 1
            areas[dimension].add("default")

    result = {}
    for d in DIMENSIONS:
        if not weights[d]:
            result[d] = None
            continue
        mean = totals[d] / weights[d]
        result[d] = {
            "raw_mean":         round(mean, 2),
            "normalized_score": round((mean - 1) / 4 * 100, 1),
            "n_items":          counts[d],
            "n_areas":          len(areas[d]),
        }
    return result


def describe_score(score: float | None) -> str:
    """Return a plain-language interpretation of a normalised 0–100 score."""
    if score is None:
        return "Insufficient responses."
    if score >= 70:
        return "More frequently endorsed in this questionnaire; treat as a reflective tendency."
    if score >= 40:
        return "Moderately endorsed; context may influence this tendency."
    return "Less frequently endorsed; this does not mean the tendency is absent."
