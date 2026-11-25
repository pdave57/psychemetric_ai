"""Tests for user feedback submission, validation, analytics, and strict access control."""


def _register_user(client, email: str, password: str = "StrongPass123!") -> str:
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "is_adult_confirmed": True,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _sample_feedback_payload(**overrides):
    payload = {
        "session_id": "demo-session-123",
        "experience_rating": 9,
        "ease_of_use": 5,
        "insightfulness": 4,
        "most_valuable_aspect": "reflective_insights",
        "would_recommend": True,
        "improvement_comment": "Loved the reflective summary, would like a dark/light toggle.",
    }
    payload.update(overrides)
    return payload


def test_get_feedback_questions_returns_five_modern_questions(client):
    resp = client.get("/api/v1/feedback/questions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["questions"]) == 5
    q1 = data["questions"][0]
    assert q1["id"] == "experience_rating"
    assert q1["min_value"] == 1
    assert q1["max_value"] == 10


def test_submit_feedback_anonymous_and_authenticated(client):
    # Anonymous / guest submission
    anon_resp = client.post("/api/v1/feedback", json=_sample_feedback_payload(experience_rating=8))
    assert anon_resp.status_code == 201
    assert anon_resp.json()["experience_rating"] == 8

    # Authenticated regular user submission
    token = _register_user(client, "regular.user@example.com")
    auth_resp = client.post(
        "/api/v1/feedback",
        json=_sample_feedback_payload(experience_rating=10, most_valuable_aspect="ui_design"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert auth_resp.status_code == 201
    assert auth_resp.json()["experience_rating"] == 10


def test_submit_feedback_validates_experience_range_1_to_10(client):
    low = client.post("/api/v1/feedback", json=_sample_feedback_payload(experience_rating=0))
    assert low.status_code == 422

    high = client.post("/api/v1/feedback", json=_sample_feedback_payload(experience_rating=11))
    assert high.status_code == 422

    bad_ease = client.post("/api/v1/feedback", json=_sample_feedback_payload(ease_of_use=6))
    assert bad_ease.status_code == 422


def test_feedback_access_denied_for_unauthenticated_and_other_users(client):
    create_resp = client.post("/api/v1/feedback", json=_sample_feedback_payload())
    assert create_resp.status_code == 201
    feedback_id = create_resp.json()["id"]

    # Unauthenticated -> 401
    assert client.get("/api/v1/feedback").status_code == 401
    assert client.get("/api/v1/feedback/summary").status_code == 401
    assert client.get(f"/api/v1/feedback/{feedback_id}").status_code == 401
    assert client.delete(f"/api/v1/feedback/{feedback_id}").status_code == 401

    # Authenticated as another user -> 403
    other_token = _register_user(client, "someone.else@example.com")
    headers = {"Authorization": f"Bearer {other_token}"}
    assert client.get("/api/v1/feedback", headers=headers).status_code == 403
    assert client.get("/api/v1/feedback/summary", headers=headers).status_code == 403
    assert client.get(f"/api/v1/feedback/{feedback_id}", headers=headers).status_code == 403
    assert client.delete(f"/api/v1/feedback/{feedback_id}", headers=headers).status_code == 403


def test_feedback_access_granted_only_to_pdave57(client):
    # Submit two entries
    r1 = client.post(
        "/api/v1/feedback",
        json=_sample_feedback_payload(experience_rating=8, ease_of_use=4, insightfulness=4, would_recommend=True),
    )
    r2 = client.post(
        "/api/v1/feedback",
        json=_sample_feedback_payload(
            experience_rating=10,
            ease_of_use=5,
            insightfulness=5,
            most_valuable_aspect="assessment_flow",
            would_recommend=False,
            improvement_comment=None,
        ),
    )
    assert r1.status_code == 201 and r2.status_code == 201
    id1 = r1.json()["id"]

    # Register and authenticate as pdave57@gmail.com (also verify case-insensitive email match)
    owner_token = _register_user(client, "PDave57@gmail.com")
    headers = {"Authorization": f"Bearer {owner_token}"}

    # List feedback
    list_resp = client.get("/api/v1/feedback", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 2

    # Summary analytics
    summary_resp = client.get("/api/v1/feedback/summary", headers=headers)
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_responses"] == 2
    assert summary["average_experience_rating"] == 9.0
    assert summary["average_ease_of_use"] == 4.5
    assert summary["average_insightfulness"] == 4.5
    assert summary["recommendation_rate_pct"] == 50.0
    assert summary["rating_distribution"]["8"] == 1
    assert summary["rating_distribution"]["10"] == 1

    # Single detail
    detail_resp = client.get(f"/api/v1/feedback/{id1}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == id1

    # Delete
    del_resp = client.delete(f"/api/v1/feedback/{id1}", headers=headers)
    assert del_resp.status_code == 204
    assert client.get(f"/api/v1/feedback/{id1}", headers=headers).status_code == 404
