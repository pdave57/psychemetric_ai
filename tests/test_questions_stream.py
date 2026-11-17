"""SSE streaming tests for questions and answer options."""

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.repositories.assessment_repository import seed_initial_instrument


def _parse_sse_events(text: str) -> list[dict]:
    """Parse a raw SSE byte stream into a list of {event, id, data} dicts."""
    events = []
    for block in text.strip().split("\n\n"):
        if not block.strip():
            continue
        fields: dict = {}
        for line in block.splitlines():
            if not line or line.startswith(":"):
                continue
            if ":" in line:
                key, _, value = line.partition(":")
                fields[key.strip()] = value.strip()
        events.append(fields)
    return events


@pytest.fixture
def client(db):
    seed_initial_instrument(db)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_questions_stream_emits_each_question_with_options(client):
    start = client.post("/api/v1/assessments/start", json={
        "user_id": "stream-demo-user",
        "instrument_code": "psychemetre_temperament_40",
        "instrument_version": "1.0.0",
    })
    assert start.status_code == 200, start.text
    session_id = start.json()["id"]

    expected_qs = start.json()["questions"]
    assert expected_qs, "seeded instrument should contain questions"

    with client.stream("GET", f"/api/v1/questions/sessions/{session_id}/stream") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        body = "".join(line + "\n" for line in response.iter_lines())

    events = _parse_sse_events(body)
    question_events = [e for e in events if e.get("event") == "question"]
    complete_events = [e for e in events if e.get("event") == "complete"]

    # One question event per instrument item, in sort_order.
    assert len(question_events) == len(expected_qs)

    for stream_q, expected_q in zip(question_events, expected_qs):
        payload = json.loads(stream_q["data"])
        assert payload["id"] == expected_q["id"]
        assert payload["code"] == expected_q["code"]
        assert payload["text"] == expected_q["text"]
        assert payload["area"] == expected_q["area"]
        assert payload["kind"] == expected_q["kind"]
        assert payload["reverse_coded"] == expected_q["reverse_coded"]
        assert payload["sort_order"] == expected_q["sort_order"]
        # Every question streams its answer options.
        assert len(payload["options"]) == len(expected_q["options"])
        assert all("code" in option and "text" in option for option in payload["options"])

    # A final `complete` event closes the stream.
    assert len(complete_events) == 1
    complete = json.loads(complete_events[0]["data"])
    assert complete["session_id"] == str(session_id)
    assert complete["total_questions"] == len(expected_qs)


def test_questions_stream_unknown_session_returns_404(client):
    resp = client.get(f"/api/v1/questions/sessions/{uuid.uuid4()}/stream")
    assert resp.status_code == 404
