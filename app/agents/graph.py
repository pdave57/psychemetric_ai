"""LangGraph assessment orchestration workflow with checkpointing, interrupt, and safety halt."""

import uuid
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.state import AssessmentGraphState
from app.core.safety_protocol import screen_text_for_safety
from app.services.scoring_service import calculate_temperament_scores, describe_score, DIMENSIONS
from app.services.narrative_service import generate_narrative_report


# Node 1: Safety Screener Node
def safety_check_node(state: AssessmentGraphState) -> Dict[str, Any]:
    """Check any recent user answers or free text for crisis or self-harm signals."""
    answers = state.get("answers", [])
    if answers:
        latest = answers[-1]
        text_val = latest.get("free_text") or latest.get("text")
        if text_val:
            risk = screen_text_for_safety(text_val)
            if risk:
                return {
                    "safety_flagged": True,
                    "safety_event": risk,
                    "phase": "halted",
                    "interrupted": True,
                }
    return {"safety_flagged": False}


# Node 2: Question Delivery Node
def question_node(state: AssessmentGraphState) -> Dict[str, Any]:
    """Determine the next question to pose to the user or mark questioning complete."""
    answers = state.get("answers", [])
    total = state.get("total_questions", 16)
    idx = len(answers)

    if idx >= total:
        return {"phase": "scoring", "interrupted": False}

    return {
        "current_question_index": idx,
        "phase": "questioning",
        "interrupted": True,  # Interrupted so client/user can answer
    }


# Node 3: Scoring & Analysis Node
def scoring_node(state: AssessmentGraphState) -> Dict[str, Any]:
    """Compute temperament scores deterministically."""
    from types import SimpleNamespace

    answers = state.get("answers", [])
    responses = [
        SimpleNamespace(question_id=a.get("question_id"), likert_value=a.get("value"))
        for a in answers
    ]

    # Dummy questions structure for state scoring
    questions = [
        SimpleNamespace(
            id=a.get("question_id"),
            loads={a.get("dimension", "sanguine"): 1.0},
            reverse_coded=False,
            weight=1.0,
            area="general"
        )
        for a in answers
    ]

    scores_dict = calculate_temperament_scores(questions, responses)
    formatted_scores = []
    for d in DIMENSIONS:
        val = scores_dict.get(d)
        if val:
            formatted_scores.append({
                "dimension": d,
                **val,
                "interpretation": describe_score(val["normalized_score"])
            })

    return {
        "temperament_scores": {"dimensions": formatted_scores},
        "phase": "narrative"
    }


# Node 4: Narrative Synthesis Node
def narrative_node(state: AssessmentGraphState) -> Dict[str, Any]:
    """Generate reflective narrative synthesis using LLM / validator."""
    scores_data = state.get("temperament_scores", {}).get("dimensions", [])
    report = generate_narrative_report(scores=scores_data, user_id=state.get("user_id", "demo"))
    return {
        "narrative_report": report,
        "phase": "completed",
        "interrupted": False
    }


# Routing condition
def should_continue_router(state: AssessmentGraphState) -> Literal["safety_halt", "question_node", "scoring_node"]:
    if state.get("safety_flagged"):
        return "safety_halt"
    phase = state.get("phase")
    if phase == "scoring":
        return "scoring_node"
    return "question_node"


def build_assessment_graph(checkpointer=None):
    """Build and compile the LangGraph workflow."""
    checkpointer = checkpointer or MemorySaver()

    builder = StateGraph(AssessmentGraphState)

    builder.add_node("safety_check", safety_check_node)
    builder.add_node("question_node", question_node)
    builder.add_node("scoring_node", scoring_node)
    builder.add_node("narrative_node", narrative_node)

    # Halt node
    def safety_halt_node(state: AssessmentGraphState) -> Dict[str, Any]:
        return {"phase": "halted"}
    builder.add_node("safety_halt", safety_halt_node)

    # Edges
    builder.add_edge(START, "safety_check")

    builder.add_conditional_edges(
        "safety_check",
        should_continue_router,
        {
            "safety_halt": "safety_halt",
            "question_node": "question_node",
            "scoring_node": "scoring_node",
        }
    )

    builder.add_edge("question_node", END)
    builder.add_edge("scoring_node", "narrative_node")
    builder.add_edge("narrative_node", END)
    builder.add_edge("safety_halt", END)

    return builder.compile(checkpointer=checkpointer)
