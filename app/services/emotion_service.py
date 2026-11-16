"""Emotion self-report service.

Records a user's self-reported emotional state linked to an assessment
session. Utilizes scoring parameters from the Assessment Knowledge Pack.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import AssessmentSession, EmotionAssessment, EmotionBand
from app.knowledge_pack.scoring import score_emotion_indicator


def record_emotion_self_report(db: Session, session_id, payload):
    """Persist an emotional self-report and return the saved row.

    Validates that the session exists before inserting. Computes
    ``burden_index`` and ``band`` using the knowledge pack's
    psychometric formulas. If a ``trigger`` is supplied in the payload,
    it is stored as an ``EmotionalTrigger`` child row.
    """
    if not db.get(AssessmentSession, session_id):
        raise HTTPException(404, "Session not found")

    data = payload.model_dump()
    trigger_text = data.pop("trigger", None)

    # Compute burden index using knowledge pack psychometrics
    scored = score_emotion_indicator(
        frequency_val=data["frequency"],
        intensity=data["intensity"],
        duration_val=data["duration"],
        impact_val=data.get("impact", "none") or "none",
    )
    burden_index = Decimal(str(scored["burden_index"]))
    band = EmotionBand(scored["band"])

    row = EmotionAssessment(
        session_id=session_id,
        burden_index=burden_index,
        band=band,
        source="structured",
        **data,
    )
    db.add(row)
    db.flush()

    if trigger_text:
        from app.models import EmotionalTrigger
        db.add(EmotionalTrigger(
            emotion_assessment_id=row.id,
            trigger_code=trigger_text,
        ))

    db.commit()
    db.refresh(row)
    return row
