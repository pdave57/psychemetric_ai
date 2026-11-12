"""Questions routes: list questions for an existing session."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AssessmentSession
from app.repositories.assessment_repository import get_questions, get_options

router = APIRouter()


@router.get("/sessions/{session_id}")
def questions(session_id: uuid.UUID, db: Session = Depends(get_db)):
    s = db.get(AssessmentSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    return [
        {
            "id":            q.id,
            "code":          q.code,
            "text":          q.text,
            "area":          q.area,
            "kind":          q.kind,
            "reverse_coded": q.reverse_coded,
            "sort_order":    q.sort_order,
            "options":       [{"code": o.code, "text": o.text} for o in get_options(db, q.id)],
        }
        for q in get_questions(db, s.version_id)
    ]
