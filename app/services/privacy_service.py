"""Privacy service: GDPR/NDPR data export and cascade purge/deletion jobs."""

import uuid
from typing import Dict, Any
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from app.models.user import User, ConsentRecord
from app.models.session import AssessmentSession, UserResponse
from app.models.result import TemperamentScore, EmotionAssessment, EmotionalTrigger, AssessmentReport
from app.models.recommendation import Recommendation, RecommendationHistory
from app.models.safety import SafetyEvent, AuditLog
from app.models.feedback import UserFeedback


def export_user_data(db: Session, user_id: uuid.UUID) -> Dict[str, Any]:
    """Export complete data archive for a user (Right of Access / Portability)."""
    user = db.get(User, user_id)
    if not user:
        return {}

    consents = db.scalars(
        select(ConsentRecord).where(ConsentRecord.user_id == user_id)
    ).all()

    sessions = db.scalars(
        select(AssessmentSession).where(AssessmentSession.user_id == str(user_id))
    ).all()

    session_data = []
    for s in sessions:
        responses = db.scalars(
            select(UserResponse).where(UserResponse.session_id == s.id)
        ).all()
        scores = db.scalars(
            select(TemperamentScore).where(TemperamentScore.session_id == s.id)
        ).all()
        emotions = db.scalars(
            select(EmotionAssessment).where(EmotionAssessment.session_id == s.id)
        ).all()
        report = db.scalar(
            select(AssessmentReport).where(AssessmentReport.session_id == s.id)
        )

        session_data.append({
            "session_id": str(s.id),
            "status": s.status.value,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            "responses": [
                {"question_id": str(r.question_id), "likert_value": r.likert_value}
                for r in responses
            ],
            "scores": [
                {"dimension": sc.dimension, "score": float(sc.score) if sc.score else None}
                for sc in scores
            ],
            "emotions": [
                {"emotion": ea.emotion, "intensity": ea.intensity, "band": ea.band.value}
                for ea in emotions
            ],
            "report": report.structured if report else None,
        })

    # Log audit event (never logging data content)
    db.add(AuditLog(actor_id=user_id, action="data.export", object_type="User", object_id=str(user_id)))
    db.commit()

    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "created_at": user.created_at.isoformat(),
        },
        "consents": [
            {"type": c.type.value, "version": c.version, "granted": c.granted}
            for c in consents
        ],
        "assessments": session_data,
    }


def purge_user_data(db: Session, user_id: uuid.UUID) -> bool:
    """Permanently delete all user records and associated assessment data (Right to Erasure)."""
    user = db.get(User, user_id)
    if not user:
        return False

    # Find and delete sessions
    sessions = db.scalars(
        select(AssessmentSession).where(AssessmentSession.user_id == str(user_id))
    ).all()
    for s in sessions:
        db.delete(s)

    # Anonymize submitted feedback so aggregate metrics remain intact without PII link
    feedback_rows = db.scalars(
        select(UserFeedback).where(UserFeedback.user_id == user_id)
    ).all()
    for fb in feedback_rows:
        fb.user_id = None

    # Delete user (cascades to consent_records, recommendations)
    db.delete(user)

    # Append-only audit record
    db.add(AuditLog(actor_id=user_id, action="data.delete", object_type="User", object_id=str(user_id)))
    db.commit()
    return True
