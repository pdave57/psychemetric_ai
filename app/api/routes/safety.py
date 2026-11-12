"""Safety routes: retrieve safety resources, status, and resume safety-paused sessions."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.safety_protocol import VERIFIED_RESOURCES
from app.services.safety_service import resume_paused_session
from app.models.session import AssessmentSession

router = APIRouter()


@router.get("/resources")
def get_safety_resources():
    """Return verified mental health crisis contacts and emergency hotlines."""
    return {"resources": VERIFIED_RESOURCES}


@router.post("/sessions/{session_id}/resume")
def resume_session(session_id: uuid.UUID, db: Session = Depends(get_db)):
    """Resume a session that was paused due to a safety check after safety acknowledgment."""
    session = db.get(AssessmentSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    resumed = resume_paused_session(db, session_id)
    if not resumed:
        raise HTTPException(
            status_code=400,
            detail=f"Session is in state '{session.status}', not 'safety_paused'."
        )
    return {"session_id": session_id, "status": "in_progress", "resumed": True}
