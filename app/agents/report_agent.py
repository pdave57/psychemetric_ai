"""Scoring computation, narrative synthesis, and recommendation matching agent.

Computes deterministic psychometric scores, validates numeric integrity against
hallucination, and synthesizes grounded reflective narratives with non-diagnostic
guardrails and personalized recommendations.
"""

from types import SimpleNamespace
from typing import Dict, Any, List, Optional
from app.agents.state import AssessmentGraphState
from app.services.scoring_service import (
    calculate_temperament_scores,
    calculate_eq_scores,
    describe_score,
    DIMENSIONS,
    EQ_DIMENSIONS,
)
from app.services.narrative_service import generate_narrative_report


def report_agent_scoring_node(state: AssessmentGraphState) -> Dict[str, Any]:
    """Scoring computation node: calculates 0–100 normalized scores deterministically."""
    answers = state.get("answers", [])
    responses = [
        SimpleNamespace(question_id=a.get("question_id"), likert_value=a.get("value"))
        for a in answers
    ]

    # Reconstruct question descriptors
    questions = [
        SimpleNamespace(
            id=a.get("question_id"),
            loads={a.get("dimension", "sanguine"): 1.0},
            reverse_coded=a.get("reverse_coded", False),
            weight=1.0,
            area=a.get("area", "general"),
        )
        for a in answers
    ]

    instrument_code = state.get("instrument_code", "psychemetre_temperament_20")
    is_eq = instrument_code == "psychemetre_eq_25"

    if is_eq:
        scores_dict = calculate_eq_scores(questions, responses)
        dimension_list = EQ_DIMENSIONS
    else:
        scores_dict = calculate_temperament_scores(questions, responses)
        dimension_list = DIMENSIONS

    formatted_scores = []
    for d in dimension_list:
        val = scores_dict.get(d)
        if val:
            formatted_scores.append({
                "dimension": d,
                **val,
                "interpretation": describe_score(val["normalized_score"]),
            })

    # Sort leading dimensions
    sorted_dims = sorted(
        formatted_scores,
        key=lambda x: x.get("normalized_score", 0),
        reverse=True,
    )
    leading = [x["dimension"] for x in sorted_dims[:2]]

    ret = {
        "leading_tendencies": leading,
        "phase": "narrative",
        "interrupted": False,
    }
    if is_eq:
        ret["eq_scores"] = {"dimensions": formatted_scores}
        ret["temperament_scores"] = {"dimensions": formatted_scores}
    else:
        ret["temperament_scores"] = {"dimensions": formatted_scores}

    return ret


def report_agent_narrative_node(state: AssessmentGraphState) -> Dict[str, Any]:
    """Narrative synthesis node: generates reflective narrative with numeric validation."""
    scores_data = (
        state.get("eq_scores", {}).get("dimensions", [])
        if state.get("instrument_code") == "psychemetre_eq_25"
        else state.get("temperament_scores", {}).get("dimensions", [])
    ) or state.get("temperament_scores", {}).get("dimensions", [])
    user_id = state.get("user_id", "demo")
    emotions = state.get("extracted_emotions", [])

    report = generate_narrative_report(
        scores=scores_data,
        user_id=user_id,
        emotion_rows=emotions,
    )

    return {
        "narrative_report": report,
        "phase": "completed",
        "interrupted": False,
    }


def report_agent_node(state: AssessmentGraphState) -> Dict[str, Any]:
    """Combined report node running both deterministic scoring and narrative synthesis."""
    score_update = report_agent_scoring_node(state)
    merged_state = {**state, **score_update}
    narrative_update = report_agent_narrative_node(merged_state)
    return {
        **score_update,
        **narrative_update,
    }
