"""Tests for the restructured 20-item Temperament assessment, historical coexistence, and session resumption."""

import uuid
from types import SimpleNamespace
import pytest
from fastapi import HTTPException

from app.models import AssessmentReport, TemperamentScore, AssessmentVersion
from app.repositories.assessment_repository import (
    seed_initial_instrument,
    verify_temperament_20_migration,
    get_instrument,
    TEMPERAMENT_20_CODE,
    TEMPERAMENT_20_VERSION,
    TEMPERAMENT_40_CODE,
    TEMPERAMENT_40_VERSION,
)
from app.schemas.assessment import AssessmentStartRequest
from app.services.scoring_service import calculate_temperament_scores, DIMENSIONS
from app.services.assessment_service import (
    start_assessment,
    submit_answer,
    complete_assessment,
    get_assessment_progress,
)
from app.agents.state import create_initial_state
from app.agents.planner import create_assessment_plan, planner_node
from app.agents.question_agent import load_canonical_questions, get_next_question
from app.agents.report_agent import report_agent_scoring_node


def test_temperament_20_migration_and_areas(db):
    """Verify that the 20-item temperament questionnaire is seeded with exact behavioural areas."""
    seed_initial_instrument(db)
    stats = verify_temperament_20_migration(db)

    assert stats["migrated"] is True
    assert stats["instrument_code"] == TEMPERAMENT_20_CODE
    assert stats["version"] == TEMPERAMENT_20_VERSION
    assert stats["total_questions"] == 20
    assert stats["total_options"] == 100  # 20 questions * 5 options each

    expected_dims = {"sanguine", "choleric", "melancholic", "phlegmatic"}
    assert set(stats["dimension_counts"].keys()) == expected_dims
    for dim, count in stats["dimension_counts"].items():
        assert count == 5, f"Expected 5 items for {dim}, found {count}"

    areas = stats["behavioural_areas"]
    assert set(areas["sanguine"]) == {"sociability", "enthusiasm", "expressiveness", "optimism", "spontaneity"}
    assert set(areas["choleric"]) == {"assertiveness", "leadership", "decisiveness", "competitiveness", "goal_orientation"}
    assert set(areas["melancholic"]) == {"attention_to_detail", "reflection", "planning", "sensitivity", "perfectionism"}
    assert set(areas["phlegmatic"]) == {"patience", "emotional_steadiness", "cooperation", "conflict_avoidance", "consistency"}


def test_historical_compatibility_coexistence(db):
    """Ensure original 40-item and new 20-item instruments coexist simultaneously."""
    seed_initial_instrument(db)

    inst_20 = get_instrument(db, TEMPERAMENT_20_CODE, TEMPERAMENT_20_VERSION)
    assert inst_20 is not None
    assert inst_20.config["total_items"] == 20

    inst_40 = get_instrument(db, TEMPERAMENT_40_CODE, TEMPERAMENT_40_VERSION)
    assert inst_40 is not None
    assert inst_40.config["total_items"] == 40


def test_pydantic_schema_defaults():
    """Verify Pydantic schema default instrument is updated to 20-item version."""
    req = AssessmentStartRequest(user_id="user_123")
    assert req.instrument_code == "psychemetre_temperament_20"
    assert req.instrument_version == "1.0.0"
    assert req.resume_if_active is False


def test_session_interruption_and_resumption_flow(db):
    """Verify that a user who is interrupted can seamlessly continue where they stopped."""
    seed_initial_instrument(db)
    user_id = f"user_{uuid.uuid4()}"

    # 1. Start assessment with 20 items
    session, questions = start_assessment(db, user_id, TEMPERAMENT_20_CODE, TEMPERAMENT_20_VERSION)
    assert len(questions) == 20
    session_id = session.id

    # 2. User answers first 7 questions then gets interrupted
    for q in questions[:7]:
        submit_answer(db, session_id, q.id, 4)

    # 3. Check progress and resume status
    progress = get_assessment_progress(db, session_id)
    assert progress["session_id"] == session_id
    assert progress["total_questions"] == 20
    assert progress["answered_count"] == 7
    assert progress["remaining_count"] == 13
    assert progress["current_question_index"] == 7
    assert progress["progress_percentage"] == 35.0
    assert progress["resumed"] is True

    # Next question must be question #8 (0-indexed 7)
    assert progress["next_question"] is not None
    assert progress["next_question"]["code"] == questions[7].code
    assert progress["next_question"]["index"] == 7

    # 4. User restarts with resume_if_active=True
    resumed_session, resumed_qs = start_assessment(
        db, user_id, TEMPERAMENT_20_CODE, TEMPERAMENT_20_VERSION, resume_if_active=True
    )
    assert resumed_session.id == session_id

    # 5. User finishes the remaining 13 questions
    for q in questions[7:]:
        submit_answer(db, session_id, q.id, 5)

    # 6. Complete assessment successfully
    final_result = complete_assessment(db, session_id)
    assert final_result["status"] == "completed"
    assert final_result["instrument"] == TEMPERAMENT_20_CODE
    assert len(final_result["temperament_scores"]) == 4

    # All 4 dimensions should have 5 items answered across 5 distinct areas
    for score_entry in final_result["temperament_scores"]:
        assert score_entry["n_items"] == 5
        assert score_entry["n_areas"] == 5


def test_api_resume_and_active_user_endpoints(client, db):
    """Test HTTP API /resume and /user/{user_id}/active endpoints."""
    seed_initial_instrument(db)
    user_id = f"test_api_user_{uuid.uuid4()}"

    # 1. Start session
    start_resp = client.post(
        "/api/v1/assessments/start",
        json={"user_id": user_id},  # Defaults to 20-item instrument
    )
    assert start_resp.status_code == 200, start_resp.text
    session_id = start_resp.json()["session_id"]
    questions = start_resp.json()["questions"]
    assert len(questions) == 20

    # 2. Submit answers for 3 items
    for q in questions[:3]:
        ans_resp = client.post(
            f"/api/v1/assessments/{session_id}/answers",
            json={"question_id": q["id"], "value": 4},
        )
        assert ans_resp.status_code == 200

    # 3. Query /resume endpoint
    resume_resp = client.get(f"/api/v1/assessments/{session_id}/resume")
    assert resume_resp.status_code == 200
    res_data = resume_resp.json()
    assert res_data["answered_count"] == 3
    assert res_data["remaining_count"] == 17
    assert res_data["next_question"]["code"] == questions[3]["code"]

    # 4. Query /user/{user_id}/active
    active_resp = client.get(f"/api/v1/assessments/user/{user_id}/active")
    assert active_resp.status_code == 200
    act_data = active_resp.json()
    assert act_data["session_id"] == session_id
    assert act_data["answered_count"] == 3


def test_agent_orchestration_with_resumed_answers():
    """Verify that agent state resumes gracefully from where the user left off."""
    canonical_qs = load_canonical_questions(TEMPERAMENT_20_CODE)
    assert len(canonical_qs) == 20

    state = create_initial_state(
        session_id="agent_resume_session",
        instrument_code=TEMPERAMENT_20_CODE,
    )
    assert state["total_questions"] == 20

    # Simulate 10 answers already provided prior to interruption
    state["answers"] = [
        {
            "question_id": q["code"],
            "value": 4,
            "dimension": q.get("dimension", "sanguine"),
            "reverse_coded": q.get("reverse_coded", False),
            "area": q.get("area", "sociability"),
        }
        for q in canonical_qs[:10]
    ]

    # Next question must be item 11 (0-indexed 10, MEL01)
    next_q = get_next_question(state)
    assert next_q is not None
    assert next_q["code"] == "MEL01"
    assert next_q["index"] == 10

    # Now add the remaining 10 answers
    state["answers"].extend([
        {
            "question_id": q["code"],
            "value": 5,
            "dimension": q.get("dimension", "melancholic"),
            "reverse_coded": q.get("reverse_coded", False),
            "area": q.get("area", "planning"),
        }
        for q in canonical_qs[10:]
    ])

    # Planner should route to scoring
    plan_res = planner_node(state)
    assert plan_res["phase"] == "scoring"

    # Scoring node computes temperament scores for all 4 dimensions
    score_res = report_agent_scoring_node(state)
    assert len(score_res["temperament_scores"]["dimensions"]) == 4
