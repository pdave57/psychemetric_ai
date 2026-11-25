"""Pydantic schemas for user feedback submission, survey questions, and analytics."""

import uuid
from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


FeedbackAspect = Literal[
    "assessment_flow",
    "reflective_insights",
    "emotional_checkin",
    "ui_design",
    "privacy_controls",
    "other",
]


class FeedbackQuestion(BaseModel):
    """Metadata for a single question in the modern 5-question feedback survey."""

    id: str
    order: int
    prompt: str
    kind: Literal["scale_1_10", "scale_1_5", "choice_and_recommend", "text"]
    required: bool
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    min_label: Optional[str] = None
    max_label: Optional[str] = None
    options: Optional[List[Dict[str, str]]] = None


class FeedbackQuestionsResponse(BaseModel):
    """Schema returned by GET /api/v1/feedback/questions."""

    title: str
    description: str
    questions: List[FeedbackQuestion]


class FeedbackSubmitRequest(BaseModel):
    """Payload for submitting user feedback (1-10 experience + 5-question survey)."""

    session_id: Optional[str] = Field(default=None, max_length=128)
    experience_rating: int = Field(
        ...,
        ge=1,
        le=10,
        description="Overall experience score from 1 (very poor) to 10 (exceptional).",
    )
    ease_of_use: int = Field(
        ...,
        ge=1,
        le=5,
        description="How clear and easy to follow the experience was (1-5).",
    )
    insightfulness: int = Field(
        ...,
        ge=1,
        le=5,
        description="How insightful and relevant the results felt (1-5).",
    )
    most_valuable_aspect: FeedbackAspect = Field(
        ...,
        description="Which part of the platform provided the most value.",
    )
    would_recommend: bool = Field(
        default=True,
        description="Whether the user would recommend Agent Bleu to others.",
    )
    improvement_comment: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Open-ended suggestion on what to improve or add.",
    )


class FeedbackSubmitResponse(BaseModel):
    """Confirmation returned after submitting feedback (does not expose others' feedback)."""

    id: uuid.UUID
    experience_rating: int
    created_at: datetime
    message: str = "Thank you for your feedback!"


class FeedbackItemResponse(BaseModel):
    """Full feedback entry visible only to the authorized reviewer."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    session_id: Optional[str] = None
    experience_rating: int
    ease_of_use: int
    insightfulness: int
    most_valuable_aspect: str
    would_recommend: bool
    improvement_comment: Optional[str] = None
    created_at: datetime


class FeedbackSummaryResponse(BaseModel):
    """Aggregated feedback metrics visible only to the authorized reviewer."""

    total_responses: int
    average_experience_rating: Optional[float] = None
    average_ease_of_use: Optional[float] = None
    average_insightfulness: Optional[float] = None
    recommendation_rate_pct: Optional[float] = None
    aspect_breakdown: Dict[str, int]
    rating_distribution: Dict[int, int]
