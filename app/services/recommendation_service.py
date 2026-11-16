"""Recommendation engine: rule-based template matching, persistence, and feedback.
Loaded and driven directly from the structured Assessment Knowledge Pack.
"""

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
from app.knowledge_pack import get_recommendation_rules


def seed_recommendation_templates(db: Session):
    """Ensure all recommendation rules from the knowledge pack exist in the database."""
    catalog = get_recommendation_rules()
    for item in catalog["rules"]:
        existing = db.get(RecommendationTemplate, item["id"])
        evidence_str = item.get("evidence", "unreviewed_seed")
        try:
            evidence_enum = EvidenceLevel(evidence_str)
        except ValueError:
            evidence_enum = EvidenceLevel.unreviewed_seed

        if not existing:
            template = RecommendationTemplate(
                id=item["id"],
                emotion=item["criteria"].get("emotion") or item.get("target_code", "general"),
                title=item["title"],
                body=item["body"],
                rules=item["criteria"],
                evidence=evidence_enum,
                active=True,
            )
            db.add(template)
        else:
            # Update content from knowledge pack
            existing.title = item["title"]
            existing.body = item["body"]
            existing.rules = item["criteria"]
            existing.evidence = evidence_enum
            existing.active = True

    db.commit()


def match_and_generate_recommendations(db: Session, session_id: uuid.UUID) -> List[Recommendation]:
    """Match active recommendation templates against session emotion assessments and temperament scores."""
    session = db.get(AssessmentSession, session_id)
    if not session:
        return []

    emotions = db.scalars(
        select(EmotionAssessment).where(EmotionAssessment.session_id == session_id)
    ).all()

    temperament_scores = db.scalars(
        select(TemperamentScore).where(TemperamentScore.session_id == session_id)
    ).all()
    temperament_dict = {
        ts.dimension.lower(): float(ts.score) if ts.score is not None else 0.0
        for ts in temperament_scores
    }

    templates = db.scalars(
        select(RecommendationTemplate).where(RecommendationTemplate.active.is_(True))
    ).all()

    created_recs = []
    band_order = {"low": 1, "moderate": 2, "high": 3}

    # Match emotion-based templates
    for ea in emotions:
        user_band_val = band_order.get(ea.band.value if hasattr(ea.band, "value") else str(ea.band).lower(), 1)

        for tmpl in templates:
            rules = tmpl.rules or {}
            target_emotion = rules.get("emotion") or tmpl.emotion
            if not target_emotion or target_emotion.lower() != ea.emotion.lower():
                continue

            # Check min_band or min_intensity requirement
            min_band = rules.get("min_band", "low")
            if user_band_val < band_order.get(min_band, 1):
                continue

            min_intensity = rules.get("min_intensity", 0)
            if ea.intensity < min_intensity:
                continue

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
                "match_type": "emotion",
                "matched_emotion": ea.emotion,
                "user_intensity": ea.intensity,
                "user_band": ea.band.value if hasattr(ea.band, "value") else str(ea.band),
                "matched_rule": rules,
            }

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

    # Match temperament-based templates
    for tmpl in templates:
        rules = tmpl.rules or {}
        target_temp = rules.get("temperament")
        if not target_temp:
            continue

        target_temp_lower = target_temp.lower()
        if target_temp_lower in temperament_dict:
            score = temperament_dict[target_temp_lower]
            min_score = float(rules.get("min_normalized_score", 70.0))
            if score >= min_score:
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
                    "match_type": "temperament",
                    "matched_temperament": target_temp,
                    "score": score,
                    "min_required": min_score,
                }

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
