"""State definitions for the LangGraph-based assessment orchestration."""

from typing import TypedDict, Optional, List, Dict, Any


class AssessmentGraphState(TypedDict, total=False):
    """Execution state carried across LangGraph agent nodes."""

    # 1. Identity & Session
    session_id: str
    user_id: str
    instrument_code: str
    instrument_version: str

    # 2. Execution Plan & Flow Control (managed by planner.py)
    plan: Optional[Dict[str, Any]]
    phase: str  # "greeting" | "planning" | "questioning" | "evaluating_response" | "scoring" | "narrative" | "completed" | "halted"
    interrupted: bool
    error: Optional[str]
    step_count: int

    # 3. Questionnaire & Progress (managed by question_agent.py)
    questions: Optional[List[Dict[str, Any]]]
    current_question_index: int
    total_questions: int
    pending_question: Optional[Dict[str, Any]]

    # 4. Responses & User Input (managed by response_agent.py)
    answers: List[Dict[str, Any]]
    last_user_message: Optional[str]
    extracted_emotions: Optional[List[Dict[str, Any]]]

    # 5. Safety Signals & Interventions (managed by safety_agent.py)
    safety_flagged: bool
    safety_level: Optional[str]  # "high" | "critical"
    safety_event: Optional[Dict[str, Any]]
    safety_message: Optional[str]
    verified_resources: Optional[List[Dict[str, Any]]]

    # 6. Scoring, RAG & Narrative (managed by report_agent.py)
    temperament_scores: Optional[Dict[str, Any]]
    eq_scores: Optional[Dict[str, Any]]
    leading_tendencies: Optional[List[str]]
    rag_citations: Optional[List[Dict[str, Any]]]
    narrative_report: Optional[Dict[str, Any]]
    recommendations: Optional[List[Dict[str, Any]]]
    report_id: Optional[str]


def create_initial_state(
    session_id: str,
    user_id: str = "guest_user",
    instrument_code: str = "psychemetre_temperament_20",
    instrument_version: str = "1.0.0",
    total_questions: Optional[int] = None,
) -> AssessmentGraphState:
    """Create a pristine, well-structured initial state for assessment orchestration."""
    is_eq = instrument_code == "psychemetre_eq_25"
    if total_questions is None:
        if is_eq:
            total_questions = 25
        elif instrument_code == "psychemetre_temperament_40":
            total_questions = 40
        elif instrument_code == "innermap_temperament":
            total_questions = 16
        else:
            total_questions = 20

    target_dimensions = (
        ["self_awareness", "self_regulation", "intrinsic_motivation", "empathy", "social_skills"]
        if is_eq
        else ["sanguine", "choleric", "melancholic", "phlegmatic"]
    )

    return {
        "session_id": session_id,
        "user_id": user_id,
        "instrument_code": instrument_code,
        "instrument_version": instrument_version,
        "phase": "questioning",
        "interrupted": False,
        "error": None,
        "step_count": 0,
        "current_question_index": 0,
        "total_questions": total_questions,
        "questions": None,
        "pending_question": None,
        "answers": [],
        "last_user_message": None,
        "extracted_emotions": [],
        "safety_flagged": False,
        "safety_level": None,
        "safety_event": None,
        "safety_message": None,
        "verified_resources": None,
        "temperament_scores": None,
        "eq_scores": None,
        "leading_tendencies": None,
        "rag_citations": None,
        "narrative_report": None,
        "recommendations": None,
        "report_id": None,
        "plan": {
            "target_dimensions": target_dimensions,
            "stages": ["questioning", "scoring", "narrative", "completed"],
            "current_stage": "questioning",
        },
    }
