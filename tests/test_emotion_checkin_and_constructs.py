"""Tests for Emotional Self-Assessment (15 items), Emotion Check-in, Contextual Follow-up,
and the Tripartite Construct Distinction (Temperament vs Skills vs Current Emotions).
"""

import uuid
import pytest
from app.repositories.assessment_repository import (
    seed_initial_instrument,
    verify_eq_15_migration,
    EQ_15_CODE,
    EQ_15_VERSION,
)
from app.services.assessment_service import (
    start_assessment,
    submit_answer,
    complete_assessment,
)
from app.services.emotion_service import (
    get_construct_framework_info,
    generate_contextual_follow_up,
)


def test_construct_framework_definitions():
    """Verify that the tripartite construct distinction is clearly and formally articulated."""
    info = get_construct_framework_info()
    constructs = info["constructs"]

    # 1. Temperament tendencies (Trait)
    assert "temperament_tendencies" in constructs
    assert constructs["temperament_tendencies"]["nature"] == "Trait / Dispositional"
    assert "20 Likert items" in constructs["temperament_tendencies"]["assessment_structure"]

    # 2. Emotional skills (Competency / EQ)
    assert "emotional_skills" in constructs
    assert constructs["emotional_skills"]["nature"] == "Competency / Capability"
    assert "15 Likert items" in constructs["emotional_skills"]["assessment_structure"]

    # 3. Current emotional experiences (State)
    assert "current_emotional_experiences" in constructs
    assert constructs["current_emotional_experiences"]["nature"] == "State / Momentary Affect"
    assert "Emotion check-in" in constructs["current_emotional_experiences"]["assessment_structure"]


def test_eq_15_instrument_seeded_and_verified(db):
    """Verify that the 15-question Emotional Self-Assessment is correctly seeded."""
    seed_initial_instrument(db)
    stats = verify_eq_15_migration(db)

    assert stats["migrated"] is True
    assert stats["instrument_code"] == EQ_15_CODE
    assert stats["version"] == EQ_15_VERSION
    assert stats["total_questions"] == 15
    assert stats["total_options"] == 75  # 15 questions * 5 options each

    expected_dims = {"self_awareness", "self_regulation", "intrinsic_motivation", "empathy", "social_skills"}
    assert set(stats["dimension_counts"].keys()) == expected_dims
    for dim, count in stats["dimension_counts"].items():
        assert count == 3, f"Expected 3 items for {dim}, found {count}"


def test_eq_15_assessment_service_flow(db):
    """Test full cycle for 15-item emotional self-assessment."""
    seed_initial_instrument(db)
    user_id = str(uuid.uuid4())

    session, questions = start_assessment(db, user_id, EQ_15_CODE, EQ_15_VERSION)
    assert len(questions) == 15

    for q in questions:
        submit_answer(db, session.id, q.id, 4)

    result = complete_assessment(db, session.id)
    assert result["status"] == "completed"
    assert result["instrument"] == EQ_15_CODE
    assert result["eq_scores"] is not None
    assert len(result["eq_scores"]) == 5

    for s in result["eq_scores"]:
        assert s["n_items"] == 3
        assert s["normalized_score"] == 75.0


def test_contextual_follow_up_generation():
    """Verify that contextual follow-up questions are generated dynamically and marked optional."""
    selected = ["anxiety", "anger"]
    questions = generate_contextual_follow_up(selected)

    assert len(questions) > 0
    # Every question must be optional
    for q in questions:
        assert q["is_optional"] is True
        assert q["emotion"] in selected

    q_types = {q["kind"] for q in questions}
    assert "scale_10" in q_types
    assert "choice" in q_types


def test_api_framework_constructs_endpoint(client):
    """Test HTTP API endpoint returning the tripartite construct model."""
    resp = client.get("/api/v1/emotions/framework/constructs")
    assert resp.status_code == 200
    data = resp.json()
    assert "constructs" in data
    assert "temperament_tendencies" in data["constructs"]
    assert "emotional_skills" in data["constructs"]
    assert "current_emotional_experiences" in data["constructs"]


def test_api_emotion_check_in_and_contextual_follow_up(client, db):
    """Test full HTTP API cycle for Emotion Check-in and optional Contextual Follow-up."""
    seed_initial_instrument(db)
    user_id = f"user_{uuid.uuid4()}"

    # 1. Get check-in options
    options_resp = client.get("/api/v1/emotions/check-in/options")
    assert options_resp.status_code == 200
    catalog = options_resp.json()
    assert len(catalog["emotions"]) == 9

    # 2. Perform Emotion Check-in selecting current emotions
    check_in_resp = client.post(
        "/api/v1/emotions/check-in",
        json={
            "user_id": user_id,
            "selected_emotions": ["anxiety", "stress"],
            "notes": "Feeling tension about project timeline",
        },
    )
    assert check_in_resp.status_code == 200, check_in_resp.text
    check_in_data = check_in_resp.json()

    assert check_in_data["construct_type"] == "current_emotional_experiences"
    assert check_in_data["selected_emotions"] == ["anxiety", "stress"]
    follow_up_qs = check_in_data["contextual_follow_up_questions"]
    assert len(follow_up_qs) >= 4

    # Verify questions are optional
    assert all(q["is_optional"] is True for q in follow_up_qs)

    # 3. Submit responses to the optional contextual follow-up questions
    follow_up_resp = client.post(
        "/api/v1/emotions/check-in/follow-up",
        json={
            "user_id": user_id,
            "answers": [
                {
                    "emotion": "anxiety",
                    "intensity": 6,
                    "frequency": "sometimes",
                    "duration": "hours",
                    "trigger": "upcoming_deadlines",
                    "impact": "slight concentration loss",
                },
                {
                    "emotion": "stress",
                    "intensity": 7,
                    "frequency": "often",
                    "duration": "days",
                    "trigger": "workload_compression",
                    "coping_strategy": "box_breathing",
                },
            ],
        },
    )
    assert follow_up_resp.status_code == 200, follow_up_resp.text
    fu_data = follow_up_resp.json()
    assert fu_data["status"] == "completed"
    assert len(fu_data["processed_emotions"]) == 2

    # Check that burden index and adaptive coping strategies were computed
    for p in fu_data["processed_emotions"]:
        assert "burden_index" in p
        assert "recommended_coping" in p
        assert len(p["recommended_coping"]) > 0
