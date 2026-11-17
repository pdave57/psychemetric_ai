"""Integration tests for Milestones 1, 2, and 3 capabilities."""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.assessment_repository import seed_initial_instrument
from app.services.recommendation_service import seed_recommendation_templates
from app.core.safety_protocol import screen_text_for_safety
from app.services.narrative_service import generate_narrative_report, validate_numeric_consistency
from app.agents.graph import build_assessment_graph


@pytest.fixture
def client(db):
    seed_initial_instrument(db)
    seed_recommendation_templates(db)
    from app.core.database import get_db
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --- Milestone 1 Tests ---

def test_auth_register_preflight_options_allowed(client):
    resp = client.options(
        "/api/v1/auth/register",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert resp.status_code == 200
    assert "access-control-allow-origin" in resp.headers
    assert resp.headers["access-control-allow-origin"] in {"*", "http://localhost:3000"}


def test_assessment_start_returns_session_id(client):
    resp = client.post(
        "/api/v1/assessments/start",
        json={
            "user_id": "user-session-id-check",
            "instrument_code": "innermap_temperament",
            "instrument_version": "0.1.0",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["session_id"] == str(data["id"])


def test_auth_registration_login_and_consent(client):
    # 1. Reject under 18
    resp = client.post("/api/v1/auth/register", json={
        "email": "teen@example.com",
        "password": "strongPassword123",
        "is_adult_confirmed": False,
    })
    assert resp.status_code == 400

    # 2. Register valid adult
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": "adult@example.com",
        "password": "strongPassword123",
        "is_adult_confirmed": True,
    })
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    user_id = reg_resp.json()["user_id"]

    # 3. Assessment /start should be blocked without assessment_processing consent
    start_resp = client.post("/api/v1/assessments/start", json={"user_id": user_id})
    assert start_resp.status_code == 403

    # 4. Grant consent
    consent_resp = client.post(
        "/api/v1/consent/grant",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "type": "assessment_processing",
            "version": "v1.0",
            "granted": True,
        }
    )
    assert consent_resp.status_code == 201

    # 5. Assessment /start now succeeds
    start_resp2 = client.post("/api/v1/assessments/start", json={"user_id": user_id})
    assert start_resp2.status_code == 200
    assert "questions" in start_resp2.json()


# --- Milestone 2 Tests ---

def test_safety_screener_detects_crisis():
    # Critical crisis detection
    res = screen_text_for_safety("I feel so overwhelmed I want to end my life")
    assert res is not None
    assert res["level"] == "critical"
    assert len(res["resources"]) >= 2

    # High risk detection
    res_high = screen_text_for_safety("I want to physically hurt someone who wronged me")
    assert res_high is not None
    assert res_high["level"] == "high"

    # Benign text
    assert screen_text_for_safety("I enjoy reflecting on calm evenings") is None


def test_recommendation_matching_and_feedback(client, db):
    # Register & grant consent
    user_id = str(uuid.uuid4())
    sess_resp = client.post("/api/v1/assessments/start", json={"user_id": user_id})
    sess_id = sess_resp.json()["id"]

    # Record anxiety self-report
    client.post(f"/api/v1/emotions/sessions/{sess_id}", json={
        "emotion": "anxiety",
        "frequency": "often",
        "intensity": 8,
        "duration": "hours"
    })

    # Generate recommendations
    rec_resp = client.post(f"/api/v1/recommendations/sessions/{sess_id}/generate")
    assert rec_resp.status_code == 200
    recs = rec_resp.json()["recommendations"]
    assert len(recs) >= 1

    rec_id = recs[0]["id"]

    # Submit user feedback
    fb_resp = client.post(f"/api/v1/recommendations/{rec_id}/feedback", json={
        "event": "check_in",
        "status": "accepted",
        "helpfulness": 5,
        "note": "Grounding technique was very effective."
    })
    assert fb_resp.status_code == 200
    assert fb_resp.json()["event"] == "check_in"


def test_comparable_assessment_history(client, db):
    u_id = str(uuid.uuid4())
    s1 = client.post("/api/v1/assessments/start", json={"user_id": u_id}).json()
    s2 = client.post("/api/v1/assessments/start", json={"user_id": u_id}).json()

    comp_resp = client.get(f"/api/v1/history/compare/{s1['id']}/{s2['id']}")
    assert comp_resp.status_code == 200
    assert comp_resp.json()["comparable_with_previous"] is True


# --- Milestone 3 Tests ---

def test_narrative_numeric_validation():
    scores = [{"dimension": "sanguine", "score": 85.0}]
    # Text with matching score
    valid, _ = validate_numeric_consistency("You scored 85.0 on sanguine.", scores)
    assert valid is True

    # Text with hallucinated score
    invalid, errors = validate_numeric_consistency("You scored 42.5 on sanguine.", scores)
    assert invalid is False
    assert len(errors) > 0


def test_langgraph_step_and_safety_halt(client):
    # Step 1: Normal step
    thread_id = str(uuid.uuid4())
    r1 = client.post("/api/v1/agents/step", json={
        "session_id": thread_id,
        "answer_value": 4,
        "dimension": "sanguine"
    })
    assert r1.status_code == 200
    assert r1.json()["safety_flagged"] is False

    # Step 2: Step with safety-flagged crisis text
    r2 = client.post("/api/v1/agents/step", json={
        "session_id": thread_id,
        "free_text": "I can't go on, I want to kill myself",
    })
    assert r2.status_code == 200
    assert r2.json()["safety_flagged"] is True
    assert r2.json()["phase"] == "halted"
