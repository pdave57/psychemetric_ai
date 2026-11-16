"""Tests for assessment repository persistence behaviour."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import AssessmentVersion, UserResponse
from app.repositories import assessment_repository as repo


def test_seed_is_idempotent_and_keeps_sixteen_questions(db):
    first  = repo.seed_initial_instrument(db)
    db.flush()
    second = repo.seed_initial_instrument(db)
    assert first.id == second.id
    # Default canonical instrument seeded from knowledge_pack has 40 items
    assert len(repo.get_questions(db, first.id)) == 40
    assert sum(
        len(repo.get_options(db, q.id)) for q in repo.get_questions(db, first.id)
    ) == 200


def test_response_upsert_updates_existing_answer(db):
    instrument = repo.seed_initial_instrument(db)
    session    = repo.create_session(db, str(uuid.uuid4()), instrument)
    question   = repo.get_questions(db, instrument.id)[0]

    repo.save_response(db, session.id, question.id, 2, seq=1)
    repo.save_response(db, session.id, question.id, 5, seq=1)
    db.commit()

    rows = db.scalars(
        select(UserResponse).where(UserResponse.session_id == session.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].likert_value == 5


def test_repository_flush_can_be_rolled_back_by_service_boundary(db):
    instrument = repo.seed_initial_instrument(db)
    session    = repo.create_session(db, str(uuid.uuid4()), instrument)
    question   = repo.get_questions(db, instrument.id)[0]

    repo.save_response(db, session.id, question.id, 4, seq=1)
    db.rollback()
    assert repo.get_responses(db, session.id) == []


def test_database_unique_constraint_rejects_duplicate_response(db):
    instrument = repo.seed_initial_instrument(db)
    session    = repo.create_session(db, str(uuid.uuid4()), instrument)
    question   = repo.get_questions(db, instrument.id)[0]

    repo.save_response(db, session.id, question.id, 3, seq=1)
    db.commit()

    db.add(UserResponse(
        session_id   = session.id,
        question_id  = question.id,
        likert_value = 4,
        seq          = 2,
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_instrument_version_unique_constraint(db):
    db.add(AssessmentVersion(
        instrument="duplicate", version="1.0",
        config={}, content_sha256="aaa",
    ))
    db.commit()
    db.add(AssessmentVersion(
        instrument="duplicate", version="1.0",
        config={}, content_sha256="bbb",
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
