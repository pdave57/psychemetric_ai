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
    calculate_eq_scores,
    describe_score,
    SCORING_VERSION,
    DIMENSIONS,
    EQ_DIMENSIONS,
)
from app.services.narrative_service import generate_narrative_report

DISCLAIMER = (
    "Classical temperaments are used as a reflective framework, not validated diagnoses. "
    "Scores are not clinical diagnoses or predictions. "
    "Emotional information is self-reported, not a clinical assessment."
)


def start_assessment(
    db: Session,
    user_id,
    code: str = repo.TEMPERAMENT_20_CODE,
    version: str = repo.TEMPERAMENT_20_VERSION,
    resume_if_active: bool = False,
):
    """Create or resume an assessment session for *user_id* on the named instrument version.

    If *user_id* corresponds to a registered user, validates that active
    consent for `assessment_processing` is recorded.
    If *resume_if_active* is True, checks for an existing in-progress session.
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

    if resume_if_active:
        active = repo.get_active_session_for_user(db, user_id, instrument_code=code)
        if active:
            questions = repo.get_questions(db, active.version_id)
            return active, questions

    instrument = repo.get_instrument(db, code, version)
    if not instrument:
        raise HTTPException(404, "Instrument version not found")

    session   = repo.create_session(db, user_id, instrument)
    questions = repo.get_questions(db, instrument.id)
    return session, questions


def get_assessment_progress(db: Session, session_id):
    """Return the completion progress of a session, including answered items and next question."""
    s = db.get(repo.AssessmentSession, session_id)
    if not s:
        raise HTTPException(404, "Session not found")

    instrument = db.get(AssessmentVersion, s.version_id)
    questions = repo.get_questions(db, s.version_id)
    responses = repo.get_responses(db, session_id)

    answered_map = {r.question_id: r.likert_value for r in responses}
    answered_count = len(answered_map)
    total_count = len(questions)

    remaining_questions = [q for q in questions if q.id not in answered_map]
    next_q = remaining_questions[0] if remaining_questions else None

    next_question_payload = None
    if next_q:
        options = repo.get_options(db, next_q.id)
        next_question_payload = {
            "id": str(next_q.id),
            "code": next_q.code,
            "text": next_q.text,
            "area": next_q.area,
            "kind": next_q.kind.value if hasattr(next_q.kind, "value") else str(next_q.kind),
            "reverse_coded": next_q.reverse_coded,
            "sort_order": next_q.sort_order,
            "options": [{"code": o.code, "text": o.text} for o in options],
            "index": answered_count,
            "total": total_count,
        }

    progress_pct = round((answered_count / total_count * 100), 1) if total_count > 0 else 0.0

    return {
        "session_id": s.id,
        "user_id": str(s.user_id),
        "status": s.status.value if hasattr(s.status, "value") else str(s.status),
        "instrument_code": instrument.instrument if instrument else "unknown",
        "instrument_version": instrument.version if instrument else "unknown",
        "total_questions": total_count,
        "answered_count": answered_count,
        "remaining_count": len(remaining_questions),
        "progress_percentage": progress_pct,
        "current_question_index": answered_count,
        "next_question": next_question_payload,
        "answers": [
            {"question_id": r.question_id, "likert_value": r.likert_value, "seq": r.seq}
            for r in responses
        ],
        "remaining_questions": [
            {
                "id": str(q.id),
                "code": q.code,
                "text": q.text,
                "area": q.area,
                "reverse_coded": q.reverse_coded,
                "sort_order": q.sort_order,
            }
            for q in remaining_questions
        ],
        "resumed": answered_count > 0,
    }


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
    db.commit()
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
    is_eq = bool(instrument and instrument.instrument == "psychemetre_eq_25")
    if is_eq:
        values = calculate_eq_scores(qs, rs)
        dimension_list = EQ_DIMENSIONS
    else:
        values = calculate_temperament_scores(qs, rs)
        dimension_list = DIMENSIONS

    output = []

    for d in dimension_list:
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
            "temperament_scores": output if not is_eq else [],
            "eq_scores": output if is_eq else [],
            "scores": output,
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
    dominant_dim = leaders[0]["dimension"].capitalize() if leaders else "Unknown"
    return {
        "session_id":          session_id,
        "report_id":           report.id,
        "instrument":          instrument.instrument,
        "instrument_version":  instrument.version,
        "scoring_version":     SCORING_VERSION,
        "status":              "completed",
        "dominant":            dominant_dim,
        "temperament":         dominant_dim,
        "summary":             narrative_payload.get("narrative") or (describe_score(leaders[0]["normalized_score"]) if leaders else ""),
        "scores":              output,
        "temperament_scores":  output,
        "eq_scores":           output if is_eq else None,
        "emotion_assessments": emotion_payload,
        "study_summary":       narrative_payload.get("narrative"),
        "narrative":           narrative_payload.get("narrative"),
        "narrative_report":    narrative_payload,
        "leading_tendencies":  [x["dimension"] for x in leaders[:2]],
        "disclaimer":          DISCLAIMER,
    }
