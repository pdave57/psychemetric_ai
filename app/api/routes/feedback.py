"""User feedback routes: public submission & survey schema, restricted review access."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_optional, require_feedback_access
from app.core.database import get_db, run_sync
from app.models.feedback import UserFeedback
from app.models.user import User
from app.schemas.feedback import (
    FeedbackItemResponse,
    FeedbackQuestion,
    FeedbackQuestionsResponse,
    FeedbackSubmitRequest,
    FeedbackSubmitResponse,
    FeedbackSummaryResponse,
)

router = APIRouter()

MODERN_FEEDBACK_QUESTIONS: List[FeedbackQuestion] = [
    FeedbackQuestion(
        id="experience_rating",
        order=1,
        prompt="Overall, how would you rate your experience with Agent Bleu?",
        kind="scale_1_10",
        required=True,
        min_value=1,
        max_value=10,
        min_label="Needs major work",
        max_label="Exceptional",
    ),
    FeedbackQuestion(
        id="ease_of_use",
        order=2,
        prompt="How clear and effortless was the assessment flow?",
        kind="scale_1_5",
        required=True,
        min_value=1,
        max_value=5,
        min_label="Confusing",
        max_label="Effortless",
    ),
    FeedbackQuestion(
        id="insightfulness",
        order=3,
        prompt="How accurate and insightful did your results and reflections feel?",
        kind="scale_1_5",
        required=True,
        min_value=1,
        max_value=5,
        min_label="Not relevant",
        max_label="Deeply insightful",
    ),
    FeedbackQuestion(
        id="most_valuable_aspect",
        order=4,
        prompt="Which part of the experience stood out most, and would you recommend us?",
        kind="choice_and_recommend",
        required=True,
        options=[
            {"value": "assessment_flow", "label": "Interactive Assessment Flow"},
            {"value": "reflective_insights", "label": "Reflective Narrative & Insights"},
            {"value": "emotional_checkin", "label": "Emotional Check-in"},
            {"value": "ui_design", "label": "Visual Design & Clarity"},
            {"value": "privacy_controls", "label": "Privacy & Safeguards"},
            {"value": "other", "label": "Other"},
        ],
    ),
    FeedbackQuestion(
        id="improvement_comment",
        order=5,
        prompt="What is one thing we could improve or add to make your experience better?",
        kind="text",
        required=False,
    ),
]


@router.get("/questions", response_model=FeedbackQuestionsResponse)
async def get_feedback_questions():
    """Return the modern 5-question feedback survey structure."""
    return FeedbackQuestionsResponse(
        title="Share Your Experience",
        description="A quick 5-question check-in (takes under 30 seconds) to help us improve Agent Bleu.",
        questions=MODERN_FEEDBACK_QUESTIONS,
    )


@router.post("", response_model=FeedbackSubmitResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=FeedbackSubmitResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def submit_feedback(
    payload: FeedbackSubmitRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Submit user feedback (1-10 experience rating + 5-question modern survey)."""
    comment = payload.improvement_comment.strip() if payload.improvement_comment else None

    def _save() -> UserFeedback:
        entry = UserFeedback(
            user_id=current_user.id if current_user else None,
            session_id=payload.session_id,
            experience_rating=payload.experience_rating,
            ease_of_use=payload.ease_of_use,
            insightfulness=payload.insightfulness,
            most_valuable_aspect=payload.most_valuable_aspect,
            would_recommend=payload.would_recommend,
            improvement_comment=comment or None,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    entry = await run_sync(_save)
    return FeedbackSubmitResponse(
        id=entry.id,
        experience_rating=entry.experience_rating,
        created_at=entry.created_at,
    )


@router.get("", response_model=List[FeedbackItemResponse])
@router.get("/", response_model=List[FeedbackItemResponse], include_in_schema=False)
async def list_feedback(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    min_rating: Optional[int] = Query(default=None, ge=1, le=10),
    max_rating: Optional[int] = Query(default=None, ge=1, le=10),
    _: User = Depends(require_feedback_access),
    db: Session = Depends(get_db),
):
    """List submitted user feedback. Restricted strictly to pdave57@gmail.com."""
    def _list() -> list[UserFeedback]:
        stmt = select(UserFeedback).order_by(UserFeedback.created_at.desc())
        if min_rating is not None:
            stmt = stmt.where(UserFeedback.experience_rating >= min_rating)
        if max_rating is not None:
            stmt = stmt.where(UserFeedback.experience_rating <= max_rating)
        stmt = stmt.offset(offset).limit(limit)
        return list(db.scalars(stmt).all())

    return await run_sync(_list)


@router.get("/summary", response_model=FeedbackSummaryResponse)
async def get_feedback_summary(
    _: User = Depends(require_feedback_access),
    db: Session = Depends(get_db),
):
    """Return aggregated feedback metrics. Restricted strictly to pdave57@gmail.com."""
    rows = await run_sync(lambda: db.scalars(select(UserFeedback)).all())
    total = len(rows)
    distribution = {rating: 0 for rating in range(1, 11)}
    aspect_breakdown: dict[str, int] = {}

    if total == 0:
        return FeedbackSummaryResponse(
            total_responses=0,
            average_experience_rating=None,
            average_ease_of_use=None,
            average_insightfulness=None,
            recommendation_rate_pct=None,
            aspect_breakdown={},
            rating_distribution=distribution,
        )

    for row in rows:
        distribution[row.experience_rating] = distribution.get(row.experience_rating, 0) + 1
        aspect_breakdown[row.most_valuable_aspect] = aspect_breakdown.get(row.most_valuable_aspect, 0) + 1

    recommend_count = sum(1 for r in rows if r.would_recommend)
    return FeedbackSummaryResponse(
        total_responses=total,
        average_experience_rating=round(sum(r.experience_rating for r in rows) / total, 2),
        average_ease_of_use=round(sum(r.ease_of_use for r in rows) / total, 2),
        average_insightfulness=round(sum(r.insightfulness for r in rows) / total, 2),
        recommendation_rate_pct=round((recommend_count / total) * 100, 1),
        aspect_breakdown=aspect_breakdown,
        rating_distribution=distribution,
    )


@router.get("/{feedback_id}", response_model=FeedbackItemResponse)
async def get_feedback_detail(
    feedback_id: uuid.UUID,
    _: User = Depends(require_feedback_access),
    db: Session = Depends(get_db),
):
    """Retrieve a single feedback entry. Restricted strictly to pdave57@gmail.com."""
    entry = await run_sync(db.get, UserFeedback, feedback_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback entry not found.")
    return entry


@router.delete("/{feedback_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feedback_entry(
    feedback_id: uuid.UUID,
    _: User = Depends(require_feedback_access),
    db: Session = Depends(get_db),
):
    """Delete a feedback entry. Restricted strictly to pdave57@gmail.com."""
    def _delete() -> None:
        entry = db.get(UserFeedback, feedback_id)
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback entry not found.")
        db.delete(entry)
        db.commit()

    await run_sync(_delete)
