"""State definitions for the LangGraph-based assessment orchestration."""

import uuid
from typing import TypedDict, Optional, List, Dict, Any


class AssessmentGraphState(TypedDict, total=False):
    """Execution state carried across LangGraph nodes."""

    session_id: str
    user_id: str
    instrument_code: str
    instrument_version: str

    # Questionnaire progress
    current_question_index: int
    total_questions: int
    pending_question: Optional[Dict[str, Any]]
    answers: List[Dict[str, Any]]

    # Safety signals
    safety_flagged: bool
    safety_event: Optional[Dict[str, Any]]

    # Results & synthesis
    temperament_scores: Optional[Dict[str, Any]]
    emotion_burden: Optional[Dict[str, Any]]
    narrative_report: Optional[Dict[str, Any]]

    # Execution control
    phase: str  # "greeting" | "questioning" | "emotion_exploration" | "scoring" | "narrative" | "completed" | "halted"
    interrupted: bool
