"""Validation utilities for assessment items and responses."""

from typing import Dict, Any, Union


def validate_answer(question: Dict[str, Any], answer: Union[int, str, float]) -> bool:
    """Validate user answer against the question's response type and bounds."""
    response_type = question.get("response_type") or question.get("scale") or "likert_5"

    if "likert_5" in response_type:
        if not isinstance(answer, (int, float)) or int(answer) < 1 or int(answer) > 5:
            raise ValueError(f"Invalid answer '{answer}' for 5-point Likert question (expected 1 to 5).")
        return True

    if "likert_7" in response_type:
        if not isinstance(answer, (int, float)) or int(answer) < 1 or int(answer) > 7:
            raise ValueError(f"Invalid answer '{answer}' for 7-point Likert question (expected 1 to 7).")
        return True

    if response_type == "intensity_10":
        if not isinstance(answer, (int, float)) or int(answer) < 0 or int(answer) > 10:
            raise ValueError(f"Invalid intensity '{answer}' (expected 0 to 10).")
        return True

    return True
