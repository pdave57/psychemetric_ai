import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import AssessmentInstrument, UserResponse
from app.repositories import assessment_repository as repo


def test_seed_is_idempotent_and_keeps_sixteen_questions(db):
    first = repo.seed_initial_instrument(db)
    db.flush()
    second = repo.seed_initial_instrument(db)
    assert first.id == second.id
    assert len(repo.get_questions(db, first.id)) == 16
    assert sum(len(repo.get_options(db, q.id)) for q in repo.get_questions(db, first.id)) == 80


def test_response_upsert_updates_existing_answer(db):
    instrument = repo.seed_initial_instrument(db)
    session = repo.create_session(db, "repo-user", instrument)
    question = repo.get_questions(db, instrument.id)[0]
    repo.save_response(db, session.id, question.id, 2)
    repo.save_response(db, session.id, question.id, 5)
    db.commit()
    rows = db.scalars(select(UserResponse).where(UserResponse.session_id == session.id)).all()
    assert len(rows) == 1
    assert rows[0].raw_value == 5


def test_repository_flush_can_be_rolled_back_by_service_boundary(db):
    instrument = repo.seed_initial_instrument(db)
    session = repo.create_session(db, "rollback-user", instrument)
    question = repo.get_questions(db, instrument.id)[0]
    repo.save_response(db, session.id, question.id, 4)
    db.rollback()
    assert repo.get_responses(db, session.id) == []


def test_database_unique_constraint_rejects_duplicate_response(db):
    instrument = repo.seed_initial_instrument(db)
    session = repo.create_session(db, "unique-user", instrument)
    question = repo.get_questions(db, instrument.id)[0]
    repo.save_response(db, session.id, question.id, 3)
    db.commit()
    db.add(UserResponse(session_id=session.id, question_id=question.id, raw_value=4))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_instrument_version_unique_constraint(db):
    db.add(AssessmentInstrument(code="duplicate", version="1.0", title="first"))
    db.commit()
    db.add(AssessmentInstrument(code="duplicate", version="1.0", title="duplicate"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
