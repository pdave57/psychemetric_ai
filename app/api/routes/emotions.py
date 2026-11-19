"""Emotion check-in, contextual follow-up, and self-report routes."""

import uuid
from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.knowledge_pack import get_emotion_indicators_bank
from app.schemas.emotion import (
    EmotionSelfReportRequest,
    EmotionCheckInRequest,
    EmotionCheckInResponse,
    ContextualFollowUpSubmitRequest,
    ConstructFrameworkResponse,
)
from app.services.emotion_service import (
    record_emotion_self_report,
    record_emotion_check_in,
    record_contextual_follow_up,
    get_construct_framework_info,
)

router = APIRouter()


@router.get("/framework/constructs", response_model=ConstructFrameworkResponse)
def get_framework_constructs():
    """Retrieve the formal construct definitions distinguishing Temperament, Skills, and Emotions."""
    return get_construct_framework_info()


@router.get("/check-in/options")
def get_check_in_options():
    """List all available discrete emotions for check-in with descriptions, triggers, and adaptive responses."""
    bank = get_emotion_indicators_bank()
    return {
        "title": "Emotion Check-in Catalog",
        "construct": "current_emotional_experiences",
        "description": "Select any emotions currently active in your present experience.",
        "emotions": [
            {
                "code": e["code"],
                "label": e["label"],
                "valence": e["valence"],
                "arousal": e["arousal"],
                "description": e["description"],
                "common_triggers": e.get("common_triggers", []),
                "adaptive_responses": e.get("adaptive_responses", []),
            }
            for e in bank.get("emotions", [])
        ]
    }


@router.post("/check-in", response_model=EmotionCheckInResponse)
def create_check_in(payload: EmotionCheckInRequest, db: Session = Depends(get_db)):
    """Record an emotion check-in where the user selects current emotions, returning optional contextual follow-ups."""
    return record_emotion_check_in(db, payload)


@router.post("/check-in/follow-up")
def submit_contextual_follow_up(payload: ContextualFollowUpSubmitRequest, db: Session = Depends(get_db)):
    """Submit responses to optional contextual follow-up questions linked to an emotion check-in."""
    return record_contextual_follow_up(db, payload)


@router.post("/sessions/{session_id}")
def create(session_id: uuid.UUID, payload: EmotionSelfReportRequest, db: Session = Depends(get_db)):
    """Legacy single emotional self-report endpoint."""
    x = record_emotion_self_report(db, session_id, payload)
    return {
        "id":           x.id,
        "session_id":   x.session_id,
        "emotion":      x.emotion,
        "intensity":    x.intensity,
        "burden_index": float(x.burden_index),
        "band":         x.band.value if hasattr(x.band, "value") else str(x.band),
        "status":       "recorded_as_self_report",
    }
