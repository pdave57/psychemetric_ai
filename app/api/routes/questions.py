"""Questions routes: list questions for an existing session.

Endpoints
---------
GET /sessions/{session_id}
    Return every question (with its answer options) for the session's
    instrument version as a single JSON payload.

GET /sessions/{session_id}/stream
    Server-Sent Events (``text/event-stream``) stream of the same
    questions. Each question is emitted as its own ``question`` event
    carrying the question body and its answer options, followed by a
    final ``complete`` event. This lets a client render the assessment
    incrementally instead of waiting for the whole instrument to load.
"""

import asyncio
import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AssessmentSession
from app.repositories.assessment_repository import get_questions, get_options

router = APIRouter()


def _question_payload(q, options) -> dict:
    """Serialize one question plus its answer options for SSE transport."""
    return {
        "type":          "question",
        "id":            str(q.id),
        "code":          q.code,
        "text":          q.text,
        "area":          q.area,
        "kind":          q.kind,
        "reverse_coded": q.reverse_coded,
        "sort_order":    q.sort_order,
        "options":       [{"code": o.code, "text": o.text} for o in options],
    }


async def _question_event_stream(
    session: AssessmentSession, db: Session
) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted question events, one per instrument item."""
    questions = get_questions(db, session.version_id)
    total = len(questions)

    for q in questions:
        options = get_options(db, q.id)
        payload = jsonable_encoder(_question_payload(q, options))
        # ``id`` lets a reconnecting client resume after this event via
        # the Last-Event-ID header.
        yield (
            f"event: question\n"
            f"id: {q.code}\n"
            f"data: {json.dumps(payload)}\n\n"
        )
        # Yield control to the event loop so Starlette can flush the
        # chunk to the client before the next question is serialized.
        await asyncio.sleep(0)

    complete = jsonable_encoder(
        {
            "type": "complete",
            "session_id": str(session.id),
            "total_questions": total,
        }
    )
    yield f"event: complete\ndata: {json.dumps(complete)}\n\n"


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


@router.get("/sessions/{session_id}/stream")
async def questions_stream(session_id: uuid.UUID, db: Session = Depends(get_db)):
    """Stream the session's questions and answer options as Server-Sent Events.

    Event stream shape::

        event: question
        id: SAN01
        data: {"id": "...", "code": "SAN01", "text": "...", ..., "options": [...]}

        event: complete
        data: {"session_id": "...", "total_questions": 40}
    """
    # Validate the session up front (synchronously) so a missing session
    # becomes a 404 instead of an aborting event stream.
    s = db.get(AssessmentSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")

    return StreamingResponse(
        _question_event_stream(s, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # disable buffering behind nginx
        },
    )
