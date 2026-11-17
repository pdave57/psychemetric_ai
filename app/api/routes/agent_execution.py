"""Interactive and streaming assessment execution via LangGraph orchestration."""

import uuid
import json
import asyncio
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.agents.graph import build_assessment_graph
from app.models.session import AssessmentSession
from app.models.enums import SessionStatus

router = APIRouter()

# Shared in-memory checkpointer for graphs
graph_engine = build_assessment_graph()


class AgentStepRequest(BaseModel):
    session_id: str
    user_id: str = "user"
    answer_value: Optional[int] = None
    free_text: Optional[str] = None
    dimension: Optional[str] = "sanguine"


@router.post("/step")
def run_agent_step(payload: AgentStepRequest, db: Session = Depends(get_db)):
    """Run one step of the interactive assessment graph using thread checkpointing."""
    thread_config = {"configurable": {"thread_id": payload.session_id}}

    current_state = graph_engine.get_state(thread_config)

    answers = []
    if current_state and current_state.values:
        answers = list(current_state.values.get("answers", []))

    if payload.answer_value is not None or payload.free_text:
        answers.append({
            "question_id": f"q_{len(answers)+1}",
            "value": payload.answer_value,
            "free_text": payload.free_text,
            "dimension": payload.dimension or "sanguine",
        })

    input_state = {
        "session_id": payload.session_id,
        "user_id": payload.user_id,
        "answers": answers,
        "total_questions": 4,  # short interactive threshold for graph demo
    }

    result = graph_engine.invoke(input_state, config=thread_config)

    # Sync back to DB if session exists
    try:
        session_uuid = uuid.UUID(payload.session_id)
        sess = db.get(AssessmentSession, session_uuid)
        if sess:
            if result.get("safety_flagged"):
                sess.status = SessionStatus.safety_paused
            elif result.get("phase") == "completed":
                sess.status = SessionStatus.completed
            db.commit()
    except Exception:
        pass

    return {
        "session_id": payload.session_id,
        "phase": result.get("phase"),
        "interrupted": result.get("interrupted"),
        "safety_flagged": result.get("safety_flagged"),
        "safety_event": result.get("safety_event"),
        "temperament_scores": result.get("temperament_scores"),
        "narrative_report": result.get("narrative_report"),
    }


class NarrativeSampleRequest(BaseModel):
    user_id: str = "demo_user"
    scores: Optional[list[dict]] = None


@router.post("/narrative/sample")
def generate_sample_narrative(payload: Optional[NarrativeSampleRequest] = None):
    """Generate a live reflective narrative sample using the active LLM."""
    scores = (payload and payload.scores) or [
        {"dimension": "sanguine", "score": 75.0, "interpretation": "High reflective social engagement"},
        {"dimension": "choleric", "score": 60.0, "interpretation": "Goal-oriented drive"},
        {"dimension": "melancholic", "score": 82.0, "interpretation": "Deep analytical reflection"},
        {"dimension": "phlegmatic", "score": 45.0, "interpretation": "Steady calm presence"},
    ]
    user_id = (payload and payload.user_id) or "demo_user"
    from app.services.narrative_service import generate_narrative_report
    report = generate_narrative_report(scores=scores, user_id=user_id)
    return {
        "status": "success",
        "scores": scores,
        "narrative": report.get("narrative"),
        "llm_model": report.get("llm_model"),
        "prompt_version": report.get("prompt_version"),
        "numeric_consistency_verified": report.get("numeric_consistency_verified"),
    }


@router.get("/stream/{session_id}")
async def stream_assessment_events(session_id: str):
    """Server-Sent Events (SSE) stream delivering assessment events in real-time."""
    async def event_generator():
        yield f"event: connect\ndata: {json.dumps({'session_id': session_id, 'status': 'connected'})}\n\n"
        await asyncio.sleep(0.1)

        thread_config = {"configurable": {"thread_id": session_id}}
        state = graph_engine.get_state(thread_config)
        values = state.values if state else {}

        yield f"event: state\ndata: {json.dumps({'phase': values.get('phase', 'in_progress'), 'safety_flagged': values.get('safety_flagged', False)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )
