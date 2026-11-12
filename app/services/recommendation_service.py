"""Recommendation engine: rule-based template matching, persistence, and feedback."""

import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recommendation import (
    RecommendationTemplate,
    Recommendation,
    RecommendationHistory,
)
from app.models.result import EmotionAssessment, TemperamentScore
from app.models.session import AssessmentSession
from app.models.enums import RecStatus, EvidenceLevel, EmotionBand

# Seed templates for common emotion / temperament patterns
SEED_TEMPLATES = [
    {
        "id": "rec_pause_ground",
        "emotion": "anxiety",
        "title": "5-4-3-2-1 Sensory Grounding Technique",
        "body": {
            "why": "Grounding techniques help down-regulate nervous system arousal by reorienting attention to immediate sensory input.",
            "what": "A structured sensory awareness exercise you can practice when noticing elevated anxiety.",
            "how": [
                "Acknowledge 5 things you can see around you.",
                "Acknowledge 4 things you can physically feel.",
                "Acknowledge 3 things you can hear.",
                "Acknowledge 2 things you can smell.",
                "Acknowledge 1 thing you can taste or are grateful for."
            ],
            "measure": "Rate your anxiety 0–10 before and 10 minutes after practicing.",
            "professional_support_when": "Seek professional clinical guidance if anxiety consistently impairs your work, relationships, or sleep."
        },
        "rules": {
            "min_band": "moderate",
            "trigger_any": ["stress", "work", "deadline", "unknown"],
            "response_any": []
        },
        "evidence": EvidenceLevel.research_supported,
    },
    {
        "id": "rec_box_breathing",
        "emotion": "stress",
        "title": "Box Breathing (4x4 Reset)",
        "body": {
            "why": "Controlled rhythmic breathing stimulates the vagus nerve and activates the parasympathetic relaxation response.",
            "what": "Four equal intervals of breath to regain physiological equilibrium.",
            "how": [
                "Inhale gently through your nose for 4 counts.",
                "Hold your breath at the top for 4 counts.",
                "Exhale slowly through your mouth for 4 counts.",
                "Hold your lungs empty for 4 counts.",
                "Repeat this cycle 4 to 6 times."
            ],
            "measure": "Observe heart rate deceleration and muscle tension relief.",
            "professional_support_when": "If severe chronic stress is accompanied by persistent physical symptoms or panic attacks."
        },
        "rules": {
            "min_band": "low",
            "trigger_any": [],
            "response_any": []
        },
        "evidence": EvidenceLevel.research_supported,
    },
    {
        "id": "rec_cognitive_reappraisal",
        "emotion": "anger",
        "title": "Perspective Shift & Tactical Delay",
        "body": {
            "why": "High emotional reactivity can narrow cognitive flexibility; a structured pause prevents impulsive interpersonal conflict.",
            "what": "A 90-second cooling-off protocol paired with alternative interpretation questions.",
            "how": [
                "Pause for 90 seconds before sending or saying any response.",
                "Ask yourself: 'What is another plausible explanation for this other person's behavior?'",
                "Identify what is within your direct control right now."
            ],
            "measure": "Track how often you avoid regretting impulsive reactions.",
            "professional_support_when": "If anger leads to property destruction, physical altercations, or severe relationship rupture."
        },
        "rules": {
            "min_band": "moderate",
            "trigger_any": ["conflict", "disagreement", "interpersonal"],
            "response_any": []
        },
        "evidence": EvidenceLevel.expert_reviewed,
    }
]


def seed_recommendation_templates(db: Session):
    """Ensure baseline recommendation templates exist in the database."""
    for item in SEED_TEMPLATES:
        existing = db.get(RecommendationTemplate, item["id"])
        if not existing:
            template = RecommendationTemplate(
                id=item["id"],
                emotion=item["emotion"],
                title=item["title"],
                body=item["body"],
                rules=item["rules"],
                evidence=item["evidence"],
                active=True,
            )
            db.add(template)
    db.commit()


def match_and_generate_recommendations(db: Session, session_id: uuid.UUID) -> List[Recommendation]:
    """Match active recommendation templates against session emotion assessments and temperament scores."""
    session = db.get(AssessmentSession, session_id)
    if not session:
        return []

    emotions = db.scalars(
        select(EmotionAssessment).where(EmotionAssessment.session_id == session_id)
    ).all()

    templates = db.scalars(
        select(RecommendationTemplate).where(RecommendationTemplate.active.is_(True))
    ).all()

    created_recs = []
    # Band hierarchy for comparison
    band_order = {"low": 1, "moderate": 2, "high": 3}

    for ea in emotions:
        user_band_val = band_order.get(ea.band.value if hasattr(ea.band, "value") else str(ea.band), 1)

        for tmpl in templates:
            # Check emotion match
            if tmpl.emotion.lower() != ea.emotion.lower():
                continue

            # Check min_band requirement
            min_band = tmpl.rules.get("min_band", "low")
            if user_band_val < band_order.get(min_band, 1):
                continue

            # Check if recommendation already exists for this session & template
            existing = db.scalar(
                select(Recommendation).where(
                    Recommendation.session_id == session_id,
                    Recommendation.template_id == tmpl.id,
                )
            )
            if existing:
                created_recs.append(existing)
                continue

            rationale = {
                "matched_emotion": ea.emotion,
                "user_intensity": ea.intensity,
                "user_band": ea.band.value if hasattr(ea.band, "value") else str(ea.band),
                "matched_rule": tmpl.rules,
            }

            # Generate new recommendation
            # user_id on session is string/UUID
            try:
                user_uuid = uuid.UUID(str(session.user_id))
            except Exception:
                user_uuid = None

            if user_uuid:
                rec = Recommendation(
                    user_id=user_uuid,
                    session_id=session_id,
                    template_id=tmpl.id,
                    rationale=rationale,
                    status=RecStatus.suggested,
                )
                db.add(rec)
                created_recs.append(rec)

    db.commit()
    for r in created_recs:
        db.refresh(r)
    return created_recs


def record_recommendation_feedback(
    db: Session,
    recommendation_id: uuid.UUID,
    event: str,
    status: Optional[str] = None,
    helpfulness: Optional[int] = None,
    outcome_rating: Optional[int] = None,
    note: Optional[str] = None
) -> RecommendationHistory:
    """Record an interaction event, status update, or rating for a recommendation."""
    rec = db.get(Recommendation, recommendation_id)
    if not rec:
        raise ValueError("Recommendation not found")

    rec_status_enum = None
    if status:
        rec_status_enum = RecStatus(status)
        rec.status = rec_status_enum

    note_enc = note.encode("utf-8") if note else None

    history = RecommendationHistory(
        recommendation_id=recommendation_id,
        event=event,
        status=rec_status_enum,
        helpfulness=helpfulness,
        outcome_rating=outcome_rating,
        note_enc=note_enc,
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return history
