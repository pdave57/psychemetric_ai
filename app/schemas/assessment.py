"""Pydantic schemas for assessment API request/response payloads."""

import uuid
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AssessmentStartRequest(BaseModel):
    """Body for POST /api/v1/assessments/start."""

    user_id:            str = Field(min_length=1, max_length=320)
    instrument_code:    str = "psychemetre_temperament_20"
    instrument_version: str = "1.0.0"
    resume_if_active:   bool = Field(
        default=False,
        description="If True and an in-progress session exists for this user and instrument, resume it."
    )


class AnswerSubmitRequest(BaseModel):
    """Body for POST /api/v1/assessments/{session_id}/answers."""

    question_id:  uuid.UUID
    value:        int = Field(ge=1, le=5, description="Likert value 1–5")


class AnswerRecord(BaseModel):
    """Record of an answer already given in a session."""

    question_id:  uuid.UUID
    likert_value: int
    seq:          int


class AssessmentProgressResponse(BaseModel):
    """Payload representing current progress in an assessment session."""

    session_id:             uuid.UUID
    user_id:                str
    status:                 str
    instrument_code:        str
    instrument_version:     str
    total_questions:        int
    answered_count:         int
    remaining_count:        int
    progress_percentage:    float
    next_question:          Optional[Dict[str, Any]] = None
    answers:                List[AnswerRecord] = []
    resumed:                bool = False
