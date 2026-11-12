"""Emotion self-report service.

Records a user's self-reported emotional state linked to an assessment
session.  The service does not infer or classify emotions — all values
are user-supplied.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import AssessmentSession, EmotionAssessment, EmotionBand


def _compute_burden_index(frequency: str, intensity: int, duration: str) -> Decimal:
    """Derive a simple composite burden index from self-reported dimensions.

    This is a provisional formula pending expert psychometric review.
    Scale: 0–100.
    """
    freq_weights = {"rarely": 1, "sometimes": 2, "often": 3, "very_often": 4}
    dur_weights  = {"minutes": 1, "hours": 2, "days": 3, "weeks": 4, "varies": 2}
    f = freq_weights.get(frequency, 1)
    d = dur_weights.get(duration, 1)
    # Max possible: 4 * 10 * 4 = 160; normalise to 100.
    raw = (f * intensity * d) / 160 * 100
    return Decimal(str(round(raw, 1)))


def _compute_band(burden_index: Decimal) -> EmotionBand:
    """Assign a coarse intensity band from the burden index."""
    if burden_index >= 60:
        return EmotionBand.high
    if burden_index >= 30:
        return EmotionBand.moderate
    return EmotionBand.low


def record_emotion_self_report(db: Session, session_id, payload):
    """Persist an emotional self-report and return the saved row.

    Validates that the session exists before inserting.  Computes
    ``burden_index`` and ``band`` from the structured self-report fields.
    If a ``trigger`` is supplied in the payload it is stored as an
    ``EmotionalTrigger`` child row.
    """
    if not db.get(AssessmentSession, session_id):
        raise HTTPException(404, "Session not found")

    data         = payload.model_dump()
    # trigger is stored in the separate EmotionalTrigger table, not on EmotionAssessment.
    trigger_text = data.pop("trigger", None)

    burden_index = _compute_burden_index(
        data["frequency"], data["intensity"], data["duration"]
    )
    band = _compute_band(burden_index)

    row = EmotionAssessment(
        session_id    = session_id,
        burden_index  = burden_index,
        band          = band,
        source        = "structured",
        **data,
    )
    db.add(row)
    db.flush()

    if trigger_text:
        from app.models import EmotionalTrigger
        db.add(EmotionalTrigger(
            emotion_assessment_id = row.id,
            trigger_code          = trigger_text,
        ))

    db.commit()
    db.refresh(row)
    return row
