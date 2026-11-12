"""Assessment routes: start, answer, and complete an assessment session."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.assessment import AssessmentStartRequest, AnswerSubmitRequest
from app.services.assessment_service import start_assessment, submit_answer, complete_assessment
from app.repositories.assessment_repository import get_options

router = APIRouter()


@router.post("/start")
def start(payload: AssessmentStartRequest, db: Session = Depends(get_db)):
    s, qs = start_assessment(db, payload.user_id, payload.instrument_code, payload.instrument_version)
    return {
        "id":          s.id,
        "user_id":     s.user_id,
        "version_id":  s.version_id,
        "status":      s.status,
        "questions": [
            {
                "id":           q.id,
                "code":         q.code,
                "text":         q.text,
                "area":         q.area,
                "kind":         q.kind,
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


@router.post("/{session_id}/answers")
def answer(session_id: uuid.UUID, payload: AnswerSubmitRequest, db: Session = Depends(get_db)):
    return submit_answer(db, session_id, payload.question_id, payload.value)


@router.post("/{session_id}/complete")
def complete(session_id: uuid.UUID, db: Session = Depends(get_db)):
    return complete_assessment(db, session_id)
