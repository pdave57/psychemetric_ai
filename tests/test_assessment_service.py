"""Tests for assessment service: start, submit, and complete flows."""

import uuid

import pytest
from fastapi import HTTPException

from app.models import AssessmentReport, TemperamentScore
from app.repositories.assessment_repository import seed_initial_instrument
from app.services.assessment_service import start_assessment, submit_answer, complete_assessment


def test_missing_required_answers_rejected(db):
    seed_initial_instrument(db)
    s, qs = start_assessment(db, str(uuid.uuid4()), "innermap_temperament", "0.1.0")
    with pytest.raises(HTTPException) as exc:
        complete_assessment(db, s.id)
    assert exc.value.status_code == 422
    assert len(exc.value.detail["missing_question_codes"]) == 16


def test_instrument_versions_coexist(db):
    from app.models import AssessmentVersion
    db.add_all([
        AssessmentVersion(
            instrument="x", version="1.0",
            config={}, content_sha256="abc",
        ),
        AssessmentVersion(
            instrument="x", version="1.1",
            config={}, content_sha256="def",
        ),
    ])
    db.commit()
    assert db.query(AssessmentVersion).filter_by(instrument="x").count() == 2


def test_completed_assessment_persists_scores_and_report(db):
    seed_initial_instrument(db)
    session, questions = start_assessment(db, str(uuid.uuid4()), "innermap_temperament", "0.1.0")

    for question in questions:
        submit_answer(db, session.id, question.id, 4)

    result = complete_assessment(db, session.id)

    report = db.get(AssessmentReport, result["report_id"])
    assert report is not None
    assert report.session_id == session.id
    assert report.structured["temperament_scores"]
    assert len(db.query(TemperamentScore).filter_by(session_id=session.id).all()) == 4
    assert "not validated diagnoses" in result["disclaimer"]
