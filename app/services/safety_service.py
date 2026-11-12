"""Safety monitoring service: detect safety risks, pause sessions, and log events."""

import uuid
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.safety import SafetyEvent
from app.models.session import AssessmentSession
from app.models.enums import SafetyLevel, SessionStatus
from app.core.safety_protocol import screen_text_for_safety, VERIFIED_RESOURCES


def check_and_handle_safety_risk(
    db: Session,
    session_id: uuid.UUID,
    text: Optional[str],
    question_id: Optional[uuid.UUID] = None,
    user_consented_store_text: bool = False
) -> Optional[Dict[str, Any]]:
    """Scan text for safety risks.

    If a risk is detected:
      1. Records a SafetyEvent row.
      2. If critical, pauses the AssessmentSession (status="safety_paused").
      3. Returns safety payload with verified support resources.
    """
    risk = screen_text_for_safety(text)
    if not risk:
        return None

    level_enum = SafetyLevel.critical if risk["level"] == "critical" else SafetyLevel.high

    # Encrypted/raw text stored ONLY if consent granted
    raw_text_enc = text.encode("utf-8") if user_consented_store_text and text else None

    event = SafetyEvent(
        session_id=session_id,
        level=level_enum,
        categories=risk["categories"],
        detector=risk["detector"],
        question_id=question_id,
        raw_text_enc=raw_text_enc,
    )
    db.add(event)

    # Pause session if critical
    session = db.get(AssessmentSession, session_id)
    if session and risk["level"] == "critical":
        session.status = SessionStatus.safety_paused

    db.commit()
    db.refresh(event)

    return {
        "safety_triggered": True,
        "event_id": str(event.id),
        "level": risk["level"],
        "message": risk["message"],
        "resources": risk["resources"],
    }


def resume_paused_session(db: Session, session_id: uuid.UUID) -> bool:
    """Allow user or administrator to resume a paused session after safety acknowledgment."""
    session = db.get(AssessmentSession, session_id)
    if not session or session.status != SessionStatus.safety_paused:
        return False
    session.status = SessionStatus.in_progress
    db.commit()
    return True
