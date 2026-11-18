"""Tests for Emotional Intelligence (EQ) instrument seeding, scoring, and end-to-end flows."""

import uuid
from types import SimpleNamespace
import pytest
from fastapi import HTTPException

from app.models import AssessmentReport, TemperamentScore
from app.repositories.assessment_repository import (
    seed_initial_instrument,
    verify_eq_migration,
    EQ_25_CODE,
    EQ_25_VERSION,
)
from app.services.scoring_service import calculate_eq_scores, EQ_DIMENSIONS
from app.services.assessment_service import (
    start_assessment,
    submit_answer,
    complete_assessment,
)
from app.agents.state import create_initial_state
from app.agents.planner import create_assessment_plan, planner_node
from app.agents.question_agent import load_canonical_questions, get_next_question
from app.agents.report_agent import report_agent_scoring_node, report_agent_node


def test_eq_instrument_seeded_and_verified(db):
    """Verify that EQ-25 questions and options are correctly migrated and seeded into the DB."""
    seed_initial_instrument(db)
    stats = verify_eq_migration(db)

    assert stats["migrated"] is True
    assert stats["instrument_code"] == EQ_25_CODE
    assert stats["version"] == EQ_25_VERSION
    assert stats["total_questions"] == 25
    assert stats["total_options"] == 125  # 25 questions * 5 options each

    expected_dimensions = {"self_awareness", "self_regulation", "intrinsic_motivation", "empathy", "social_skills"}
    assert set(stats["dimension_counts"].keys()) == expected_dimensions
    for dim, count in stats["dimension_counts"].items():
        assert count == 5, f"Expected 5 items for {dim}, found {count}"


def test_calculate_eq_scores_logic():
    """Unit test for calculate_eq_scores function with direct and reverse-scored items."""
    # 5 items: 4 regular + 1 reverse-coded
    questions = [
        SimpleNamespace(id="q1", loads={"self_awareness": 1.0}, reverse_coded=False, weight=1.0, area="self_awareness"),
        SimpleNamespace(id="q2", loads={"self_awareness": 1.0}, reverse_coded=True, weight=1.0, area="self_awareness"),
        SimpleNamespace(id="q3", loads={"empathy": 1.0}, reverse_coded=False, weight=1.0, area="empathy"),
    ]
    # Responses: q1=5, q2=1 (reversed: 6 - 1 = 5), q3=3
    responses = [
        SimpleNamespace(question_id="q1", likert_value=5),
        SimpleNamespace(question_id="q2", likert_value=1),
        SimpleNamespace(question_id="q3", likert_value=3),
    ]

    scores = calculate_eq_scores(questions, responses)
    # self_awareness: mean is (5 + 5)/2 = 5.0 -> norm = (5.0 - 1)/4 * 100 = 100.0
    assert scores["self_awareness"] is not None
    assert scores["self_awareness"]["raw_mean"] == 5.0
    assert scores["self_awareness"]["normalized_score"] == 100.0
    assert scores["self_awareness"]["n_items"] == 2

    # empathy: mean is 3.0 -> norm = (3.0 - 1)/4 * 100 = 50.0
    assert scores["empathy"] is not None
    assert scores["empathy"]["raw_mean"] == 3.0
    assert scores["empathy"]["normalized_score"] == 50.0

    # Unanswered dimensions should be None
    assert scores["self_regulation"] is None
    assert scores["intrinsic_motivation"] is None
    assert scores["social_skills"] is None


def test_eq_assessment_service_flow(db):
    """Test start, submit, and complete flow for the psychemetre_eq_25 instrument."""
    seed_initial_instrument(db)
    user_id = str(uuid.uuid4())

    session, questions = start_assessment(db, user_id, EQ_25_CODE, EQ_25_VERSION)
    assert len(questions) == 25

    # Incomplete completion must fail
    with pytest.raises(HTTPException) as exc_info:
        complete_assessment(db, session.id)
    assert exc_info.value.status_code == 422
    assert len(exc_info.value.detail["missing_question_codes"]) == 25

    # Answer all 25 questions
    for q in questions:
        submit_answer(db, session.id, q.id, 4)

    result = complete_assessment(db, session.id)

    assert result["status"] == "completed"
    assert result["instrument"] == EQ_25_CODE
    assert "eq_scores" in result
    assert result["eq_scores"] is not None
    assert len(result["eq_scores"]) == 5

    dim_names = {x["dimension"] for x in result["eq_scores"]}
    assert dim_names == set(EQ_DIMENSIONS)

    # Check database persistence
    saved_scores = db.query(TemperamentScore).filter_by(session_id=session.id).all()
    assert len(saved_scores) == 5
    saved_dims = {s.dimension for s in saved_scores}
    assert saved_dims == set(EQ_DIMENSIONS)

    report = db.get(AssessmentReport, result["report_id"])
    assert report is not None
    assert "eq_scores" in report.structured
    assert len(report.structured["eq_scores"]) == 5


def test_eq_agents_orchestration():
    """Verify that agents handle psychemetre_eq_25 questions and scoring."""
    state = create_initial_state(
        session_id="test_eq_session",
        instrument_code=EQ_25_CODE,
        instrument_version=EQ_25_VERSION,
    )
    assert state["total_questions"] == 25
    assert state["plan"]["target_dimensions"] == list(EQ_DIMENSIONS)

    canonical_qs = load_canonical_questions(EQ_25_CODE)
    assert len(canonical_qs) == 25
    assert canonical_qs[0]["code"].startswith("EQ_")

    first_q = get_next_question(state)
    assert first_q is not None
    assert first_q["code"] == "EQ_SA01"

    # Simulate answering all 25 items
    state["answers"] = [
        {
            "question_id": q["code"],
            "value": 4,
            "dimension": q.get("dimension", "self_awareness"),
            "reverse_coded": q.get("reverse_coded", False),
            "area": q.get("dimension", "self_awareness"),
        }
        for q in canonical_qs
    ]

    # Planner should route to scoring
    plan_result = planner_node(state)
    assert plan_result["phase"] == "scoring"

    # Scoring node should compute EQ scores
    scoring_result = report_agent_scoring_node(state)
    assert scoring_result["phase"] == "narrative"
    assert "eq_scores" in scoring_result
    assert len(scoring_result["eq_scores"]["dimensions"]) == 5


def test_eq_api_client_flow(client, db):
    """Test full HTTP API cycle for EQ-25."""
    seed_initial_instrument(db)
    user_id = str(uuid.uuid4())

    # 1. Start session
    start_resp = client.post(
        "/api/v1/assessments/start",
        json={
            "user_id": user_id,
            "instrument_code": EQ_25_CODE,
            "instrument_version": EQ_25_VERSION,
        },
    )
    assert start_resp.status_code == 200, start_resp.text
    session_data = start_resp.json()
    session_id = session_data["session_id"]
    questions = session_data["questions"]
    assert len(questions) == 25

    # 2. Answer all questions
    for q in questions:
        ans_resp = client.post(
            f"/api/v1/assessments/{session_id}/answers",
            json={"question_id": q["id"], "value": 5},
        )
        assert ans_resp.status_code == 200

    # 3. Complete assessment
    complete_resp = client.post(f"/api/v1/assessments/{session_id}/complete")
    assert complete_resp.status_code == 200, complete_resp.text
    comp_data = complete_resp.json()
    assert comp_data["status"] == "completed"
    assert comp_data["instrument"] == EQ_25_CODE
    assert len(comp_data["eq_scores"]) == 5
