"""Assessment routes: start, answer, and complete an assessment session."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db, run_sync
from app.schemas.assessment import (
    AssessmentStartRequest,
    AnswerSubmitRequest,
    AssessmentProgressResponse,
)
from app.services.assessment_service import (
    start_assessment,
    submit_answer,
    complete_assessment,
    get_assessment_progress,
)
from app.repositories.assessment_repository import get_options, get_active_session_for_user

router = APIRouter()


@router.post("/start")
async def start(payload: AssessmentStartRequest, db: Session = Depends(get_db)):
    def _start() -> dict:
        s, qs = start_assessment(
            db,
            payload.user_id,
            payload.instrument_code,
            payload.instrument_version,
            resume_if_active=payload.resume_if_active,
        )
        return {
            "id":          s.id,
            "session_id":  str(s.id),
            "user_id":     s.user_id,
            "version_id":  s.version_id,
            "status":      s.status.value if hasattr(s.status, "value") else str(s.status),
            "questions": [
                {
                    "id":           q.id,
                    "code":         q.code,
                    "text":         q.text,
                    "area":         q.area,
                    "kind":         q.kind.value if hasattr(q.kind, "value") else str(q.kind),
                    "reverse_coded":q.reverse_coded,
                    "sort_order":   q.sort_order,
                    "options": [
                        {"code": o.code, "text": o.text}
                        for o in get_options(db, q.id)
                    ],
                }
                for q in qs
            ],
        }

    return await run_sync(_start)


@router.get("/{session_id}/progress", response_model=AssessmentProgressResponse)
async def get_progress(session_id: uuid.UUID, db: Session = Depends(get_db)):
    """Retrieve the progress and next question for an in-progress session."""
    return await run_sync(get_assessment_progress, db, session_id)


@router.get("/{session_id}/resume", response_model=AssessmentProgressResponse)
async def resume(session_id: uuid.UUID, db: Session = Depends(get_db)):
    """Resume an assessment session where the user stopped after interruption."""
    return await run_sync(get_assessment_progress, db, session_id)


@router.get("/user/{user_id}/active", response_model=Optional[AssessmentProgressResponse])
async def get_active_session(user_id: str, db: Session = Depends(get_db)):
    """Find and return progress for a user's most recent active in-progress assessment."""
    def _get_active():
        active = get_active_session_for_user(db, user_id)
        if not active:
            return None
        return get_assessment_progress(db, active.id)

    return await run_sync(_get_active)


@router.post("/{session_id}/answers")
async def answer(session_id: uuid.UUID, payload: AnswerSubmitRequest, db: Session = Depends(get_db)):
    return await run_sync(submit_answer, db, session_id, payload.question_id, payload.value)


@router.post("/{session_id}/complete")
async def complete(session_id: uuid.UUID, db: Session = Depends(get_db)):
    return await run_sync(complete_assessment, db, session_id)
