"""Pydantic schemas for emotional self-report API payloads."""

from typing import Literal
from pydantic import BaseModel, Field


class EmotionSelfReportRequest(BaseModel):
    """Body for POST /api/v1/emotions/sessions/{session_id}."""

    emotion:         Literal["anger", "anxiety", "fear", "sadness", "stress",
                             "guilt", "jealousy", "loneliness", "joy"]
    frequency:       Literal["rarely", "sometimes", "often", "very_often"]
    intensity:       int = Field(ge=0, le=10, description="Subjective intensity 0–10")
    duration:        Literal["minutes", "hours", "days", "weeks", "varies"]
    trigger:         str | None = Field(default=None, max_length=1000)
    response:        str | None = Field(default=None, max_length=1000)
    coping_strategy: str | None = Field(default=None, max_length=1000)
    impact:          str | None = Field(default=None, max_length=1000)
