"""Pydantic schemas for emotional self-report, check-in, and contextual follow-up payloads."""

import uuid
from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field


EMOTION_TYPE = Literal[
    "anger", "anxiety", "fear", "sadness", "stress",
    "guilt", "jealousy", "loneliness", "joy"
]


class EmotionSelfReportRequest(BaseModel):
    """Body for POST /api/v1/emotions/sessions/{session_id}."""

    emotion:         EMOTION_TYPE
    frequency:       Literal["rarely", "sometimes", "often", "very_often"]
    intensity:       int = Field(ge=0, le=10, description="Subjective intensity 0–10")
    duration:        Literal["minutes", "hours", "days", "weeks", "varies"]
    trigger:         str | None = Field(default=None, max_length=1000)
    response:        str | None = Field(default=None, max_length=1000)
    coping_strategy: str | None = Field(default=None, max_length=1000)
    impact:          str | None = Field(default=None, max_length=1000)


class EmotionCheckInRequest(BaseModel):
    """Body for POST /api/v1/emotions/check-in."""

    user_id:           str = Field(min_length=1, max_length=320)
    session_id:        Optional[uuid.UUID] = None
    selected_emotions: List[EMOTION_TYPE] = Field(
        min_length=1,
        description="Current emotions selected by user during check-in"
    )
    notes:             Optional[str] = Field(default=None, max_length=1000)


class ContextualQuestion(BaseModel):
    """An optional contextual inquiry generated based on selected emotions."""

    emotion:          str
    question_id:      str
    question_text:    str
    kind:             str  # "scale_10", "choice", "text"
    options:          Optional[List[str]] = None
    common_triggers:  Optional[List[str]] = None
    adaptive_options: Optional[List[str]] = None
    is_optional:      bool = True


class EmotionCheckInResponse(BaseModel):
    """Response returned upon completing an emotion check-in."""

    check_in_id:                     str
    user_id:                         str
    session_id:                      Optional[uuid.UUID] = None
    selected_emotions:               List[str]
    construct_type:                  str = "current_emotional_experiences"
    contextual_follow_up_questions:  List[ContextualQuestion]
    message:                         str


class ContextualFollowUpAnswer(BaseModel):
    """Single answer to an optional contextual follow-up question."""

    emotion:         EMOTION_TYPE
    intensity:       Optional[int] = Field(default=5, ge=0, le=10)
    frequency:       Optional[Literal["rarely", "sometimes", "often", "very_often"]] = "sometimes"
    duration:        Optional[Literal["minutes", "hours", "days", "weeks", "varies"]] = "hours"
    trigger:         Optional[str] = Field(default=None, max_length=1000)
    impact:          Optional[str] = Field(default=None, max_length=1000)
    coping_strategy: Optional[str] = Field(default=None, max_length=1000)


class ContextualFollowUpSubmitRequest(BaseModel):
    """Body for POST /api/v1/emotions/check-in/follow-up."""

    user_id:    str
    session_id: Optional[uuid.UUID] = None
    answers:    List[ContextualFollowUpAnswer]


class ConstructFrameworkResponse(BaseModel):
    """Formal conceptual definition distinguishing the three assessment constructs."""

    framework: str
    constructs: Dict[str, Dict[str, Any]]
