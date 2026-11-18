"""Strategic assessment orchestrator and workflow planner agent.

Plans the psychometric inquiry trajectory, coordinates node sequencing,
monitors questionnaire completeness thresholds, and routes states
across safety, question delivery, response evaluation, and synthesis.
"""

from typing import Dict, Any, List, Optional, Literal
from app.agents.state import AssessmentGraphState


def create_assessment_plan(
    total_questions: int = 16,
    target_dimensions: Optional[List[str]] = None,
    instrument_code: str = "psychemetre_temperament_40",
) -> Dict[str, Any]:
    """Generate a structured assessment plan with stages and coverage targets."""
    if target_dimensions is None:
        if instrument_code == "psychemetre_eq_25":
            dims = ["self_awareness", "self_regulation", "intrinsic_motivation", "empathy", "social_skills"]
        else:
            dims = ["sanguine", "choleric", "melancholic", "phlegmatic"]
    else:
        dims = target_dimensions

    items_per_dim = total_questions // len(dims) if dims else 0
    return {
        "target_dimensions": dims,
        "total_items": total_questions,
        "items_per_dimension": items_per_dim,
        "stages": ["questioning", "evaluating_response", "scoring", "narrative", "completed"],
        "current_stage": "questioning",
        "adaptive_inquiry": False,
    }


def planner_node(state: AssessmentGraphState) -> Dict[str, Any]:
    """Planner node: assesses assessment completion, updates roadmap, and sets next phase."""
    if state.get("safety_flagged"):
        return {
            "phase": "halted",
            "interrupted": True,
        }

    answers = state.get("answers", [])
    total = state.get("total_questions", 16)
    answered_count = len(answers)
    instrument_code = state.get("instrument_code", "psychemetre_temperament_40")

    plan = state.get("plan") or create_assessment_plan(
        total_questions=total,
        instrument_code=instrument_code,
    )

    # If all items answered, transition to scoring
    if answered_count >= total:
        plan["current_stage"] = "scoring"
        return {
            "phase": "scoring",
            "interrupted": False,
            "plan": plan,
            "step_count": state.get("step_count", 0) + 1,
        }

    # Otherwise, stay in questioning phase
    plan["current_stage"] = "questioning"
    return {
        "phase": "questioning",
        "current_question_index": answered_count,
        "interrupted": True,
        "plan": plan,
        "step_count": state.get("step_count", 0) + 1,
    }


def route_from_planner(state: AssessmentGraphState) -> Literal["safety_halt", "question_node", "scoring_node", "narrative_node"]:
    """Conditional router determining the next destination node in the graph."""
    if state.get("safety_flagged") or state.get("phase") == "halted":
        return "safety_halt"

    phase = state.get("phase")
    if phase == "scoring":
        return "scoring_node"
    if phase == "narrative":
        return "narrative_node"

    return "question_node"
