"""Pydantic schemas for assessment API request/response payloads."""

import uuid
from pydantic import BaseModel, Field


class AssessmentStartRequest(BaseModel):
    """Body for POST /api/v1/assessments/start."""

    user_id:            str = Field(min_length=1, max_length=320)
    instrument_code:    str = "psychemetre_temperament_40"
    instrument_version: str = "1.0.0"


class AnswerSubmitRequest(BaseModel):
    """Body for POST /api/v1/assessments/{session_id}/answers."""

    question_id:  uuid.UUID
    value:        int = Field(ge=1, le=5, description="Likert value 1–5")
