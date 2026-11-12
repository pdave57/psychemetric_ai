"""Recommendations routes: listing, triggering generation, and user feedback."""

import uuid
from typing import Optional, Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.recommendation_service import (
    match_and_generate_recommendations,
    record_recommendation_feedback,
    seed_recommendation_templates,
)
from app.models.recommendation import Recommendation, RecommendationTemplate

router = APIRouter()


class FeedbackRequest(BaseModel):
    event: Literal["status_change", "check_in", "feedback"]
    status: Optional[Literal["suggested", "accepted", "in_progress", "completed", "dismissed"]] = None
    helpfulness: Optional[int] = Field(default=None, ge=1, le=5)
    outcome_rating: Optional[int] = Field(default=None, ge=0, le=10)
    note: Optional[str] = None


@router.post("/sessions/{session_id}/generate")
def generate_recommendations(session_id: uuid.UUID, db: Session = Depends(get_db)):
    """Evaluate session results against recommendation rules and generate personalized recommendations."""
    seed_recommendation_templates(db)
    recs = match_and_generate_recommendations(db, session_id)
    return {
        "session_id": session_id,
        "count": len(recs),
        "recommendations": [
            {
                "id": r.id,
                "template_id": r.template_id,
                "status": r.status.value,
                "rationale": r.rationale,
                "created_at": r.created_at,
            }
            for r in recs
        ]
    }


@router.get("/sessions/{session_id}")
def get_session_recommendations(session_id: uuid.UUID, db: Session = Depends(get_db)):
    """Retrieve all recommendations for a session including template details."""
    recs = db.scalars(
        select(Recommendation).where(Recommendation.session_id == session_id)
    ).all()

    result = []
    for r in recs:
        template = db.get(RecommendationTemplate, r.template_id)
        result.append({
            "id": r.id,
            "template_id": r.template_id,
            "title": template.title if template else r.template_id,
            "body": template.body if template else {},
            "evidence": template.evidence.value if template else "unreviewed_seed",
            "status": r.status.value,
            "rationale": r.rationale,
            "created_at": r.created_at,
        })
    return {"session_id": session_id, "recommendations": result}


@router.post("/{recommendation_id}/feedback")
def submit_feedback(
    recommendation_id: uuid.UUID,
    payload: FeedbackRequest,
    db: Session = Depends(get_db)
):
    """Update status, submit rating or note on a recommendation."""
    try:
        hist = record_recommendation_feedback(
            db=db,
            recommendation_id=recommendation_id,
            event=payload.event,
            status=payload.status,
            helpfulness=payload.helpfulness,
            outcome_rating=payload.outcome_rating,
            note=payload.note,
        )
        return {
            "history_id": hist.id,
            "recommendation_id": hist.recommendation_id,
            "event": hist.event,
            "status": hist.status.value if hist.status else None,
            "created_at": hist.created_at,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
