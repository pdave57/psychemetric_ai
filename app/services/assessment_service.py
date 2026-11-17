"""Assessment service: start, answer, and complete assessment sessions.

This module owns the commit/rollback transaction boundaries.  Repository
functions add and flush ORM objects; this service commits the final state
atomically so that scores, the report snapshot, and the completed session
status are written together or not at all.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AssessmentVersion,
    Question,
    QuestionOption,
    TemperamentScore,
    AssessmentReport,
    User,
    ConsentRecord,
    ConsentType,
    EmotionAssessment,
)
from app.repositories import assessment_repository as repo
from app.services.scoring_service import (
    calculate_temperament_scores,
    describe_score,
    SCORING_VERSION,
    DIMENSIONS,
)
from app.services.narrative_service import generate_narrative_report

DISCLAIMER = (
    "Classical temperaments are used as a reflective framework, not validated diagnoses. "
    "Scores are not clinical diagnoses or predictions. "
    "Emotional information is self-reported, not a clinical assessment."
)


def start_assessment(db: Session, user_id, code: str, version: str):
    """Create a new session for *user_id* on the named instrument version.

    If *user_id* corresponds to a registered user, validates that active
    consent for `assessment_processing` is recorded.
    Returns (session, questions). Raises 403 if consent missing, 404 if instrument not found.
    """
    # Check consent if user_id resolves to an existing registered user
    try:
        user_uuid = uuid.UUID(str(user_id))
        user = db.get(User, user_uuid)
        if user:
            # Check latest consent for assessment_processing
            consent = db.scalar(
                select(ConsentRecord)
                .where(
                    ConsentRecord.user_id == user.id,
                    ConsentRecord.type == ConsentType.assessment_processing
                )
                .order_by(ConsentRecord.created_at.desc())
            )
            if not consent or not consent.granted:
                raise HTTPException(
                    status_code=403,
                    detail="Consent for 'assessment_processing' is required before starting an assessment."
                )
    except (ValueError, TypeError):
        pass

    instrument = repo.get_instrument(db, code, version)
    if not instrument:
        raise HTTPException(404, "Instrument version not found")

    session   = repo.create_session(db, user_id, instrument)
    questions = repo.get_questions(db, instrument.id)
    return session, questions


def submit_answer(db: Session, session_id, question_id, likert_value: int):
    """Record a Likert answer for *(session_id, question_id)*.

    Validates that the session exists and is in progress, that the
    question belongs to the session's instrument, and that the value is
    in the valid 1–5 range.
    """
    s = db.get(repo.AssessmentSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    if s.status != "in_progress":
        raise HTTPException(409, "Assessment is not in progress")

    q = db.get(Question, question_id)
    if not q or q.version_id != s.version_id:
        raise HTTPException(400, "Question does not belong to this instrument")

    if not (1 <= likert_value <= 5):
        raise HTTPException(422, "Likert value must be between 1 and 5")

    # Determine the sequence number: position among answers already given.
    existing_responses = repo.get_responses(db, session_id)
    seq = len(existing_responses) + 1

    repo.save_response(db, session_id, question_id, likert_value, seq)
    return {"saved": True, "session_id": session_id, "question_id": question_id}


def complete_assessment(db: Session, session_id):
    """Score the session, persist results atomically, and return the report.

    Steps (all in one transaction):
      1. Validate all required questions are answered.
      2. Calculate temperament scores.
      3. Persist TemperamentScore rows.
      4. Persist AssessmentReport snapshot.
      5. Mark session completed.
      6. Commit.
    """
    s = db.get(repo.AssessmentSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    if s.status != "in_progress":
        raise HTTPException(409, "Assessment is not in progress")

    instrument = db.get(AssessmentVersion, s.version_id)
    qs = repo.get_questions(db, s.version_id)
    rs = repo.get_responses(db, session_id)

    answered = {r.question_id for r in rs}
    missing  = [q.code for q in qs if q.is_core and q.id not in answered]
    if missing:
        raise HTTPException(
            422,
            detail={"message": "Required answers are missing", "missing_question_codes": missing},
        )

    # Map responses to the format expected by scoring_service.
    values = calculate_temperament_scores(qs, rs)
    output = []

    for d in DIMENSIONS:
        v = values[d]
        if v is None:
            continue
        desc = describe_score(v["normalized_score"])
        output.append({"dimension": d, **v, "interpretation": desc})
        db.add(TemperamentScore(
            session_id = session_id,
            dimension  = d,
            score      = v["normalized_score"],    # 0–100 scale
            n_items    = v["n_items"],
            n_areas    = v.get("n_areas", 1),
            confidence = 1.0,                      # Placeholder; full IRT in a later milestone.
        ))
    db.flush()

    emotion_rows = db.scalars(
        select(EmotionAssessment).where(EmotionAssessment.session_id == session_id)
    ).all()
    emotion_payload = [
        {
            "emotion": row.emotion,
            "frequency": row.frequency,
            "intensity": row.intensity,
            "duration": row.duration,
            "impact": row.impact,
            "burden_index": float(row.burden_index),
            "band": row.band.value,
        }
        for row in emotion_rows
    ]
    narrative_payload = generate_narrative_report(
        scores=output,
        user_id=str(s.user_id),
        emotion_rows=emotion_payload,
    )

    report = AssessmentReport(
        session_id = session_id,
        structured = {
            "temperament_scores": output,
            "emotion_assessments": emotion_payload,
        },
        narrative = narrative_payload,
        llm_model = narrative_payload.get("llm_model"),
        prompt_version = narrative_payload.get("prompt_version"),
    )
    db.add(report)
    db.flush()

    s.status       = "completed"
    s.completed_at = datetime.now(timezone.utc)
    db.commit()

    leaders = sorted(output, key=lambda x: x["normalized_score"], reverse=True)
    return {
        "session_id":          session_id,
        "report_id":           report.id,
        "instrument":          instrument.instrument,
        "instrument_version":  instrument.version,
        "scoring_version":     SCORING_VERSION,
        "status":              "completed",
        "temperament_scores":  output,
        "emotion_assessments": emotion_payload,
        "study_summary":       narrative_payload.get("narrative"),
        "narrative":           narrative_payload.get("narrative"),
        "narrative_report":    narrative_payload,
        "leading_tendencies":  [x["dimension"] for x in leaders[:2]],
        "disclaimer":          DISCLAIMER,
    }
