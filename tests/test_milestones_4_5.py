"""Integration tests for Milestones 4 and 5: RAG, PDF export, and privacy erasure."""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.assessment_repository import seed_initial_instrument
from app.services.recommendation_service import seed_recommendation_templates
from app.knowledge.ingestion import ingest_document, LicenseMissingError
from app.knowledge.retrieval import search_knowledge_base
from app.services.pdf_service import generate_assessment_pdf
from app.services.privacy_service import export_user_data, purge_user_data


@pytest.fixture
def client(db):
    seed_initial_instrument(db)
    seed_recommendation_templates(db)
    from app.core.database import get_db
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --- Milestone 4: Knowledge Base / RAG Tests ---

def test_license_gate_enforcement(db):
    """Refuse document ingestion if license is missing or empty."""
    with pytest.raises(LicenseMissingError):
        ingest_document(
            db=db,
            title="Unlicensed Research Paper",
            collection="temperament",
            source_type="academic_research",
            license="",
            content="This paper discusses behavioral consistency in social contexts.",
        )


def test_idempotent_ingestion_and_hybrid_retrieval(db):
    """Idempotent ingestion by sha256 hash and keyword/vector retrieval."""
    content = "The sanguine temperament reflects spontaneous social engagement and elevated external reward sensitivity."
    doc1 = ingest_document(
        db=db,
        title="Classical Temperament Foundations",
        collection="temperament",
        source_type="book",
        license="CC-BY-4.0",
        content=content,
    )

    # Re-ingest exact same content -> must return existing record
    doc2 = ingest_document(
        db=db,
        title="Duplicate Paper",
        collection="temperament",
        source_type="book",
        license="CC-BY-4.0",
        content=content,
    )
    assert doc1.id == doc2.id

    # Retrieve via search
    results = search_knowledge_base(db, query="sanguine reward sensitivity", collection="temperament")
    assert len(results) >= 1
    assert "sanguine" in results[0]["content"].lower()
    assert results[0]["license"] == "CC-BY-4.0"


# --- Milestone 5: PDF, Privacy & Dashboard Tests ---

def test_pdf_report_generation():
    """Verify clean PDF binary output with disclaimer and dimensions."""
    sample_report = {
        "session_id": str(uuid.uuid4()),
        "temperament_scores": [
            {"dimension": "sanguine", "score": 80.0, "interpretation": "High tendency"},
            {"dimension": "melancholic", "score": 65.0, "interpretation": "Moderate tendency"},
        ],
        "narrative": "Reflective patterns show balanced engagement across social settings.",
    }
    pdf_bytes = generate_assessment_pdf(sample_report)
    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert b"PsychemetreAI" in pdf_bytes
    assert b"DISCLAIMER" in pdf_bytes


def test_privacy_export_and_cascade_purge(client, db):
    """Test full account export and complete GDPR/NDPR cascade erasure."""
    # Register user
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    reg = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "strongPassword123",
        "is_adult_confirmed": True,
    }).json()
    token = reg["access_token"]
    user_id = uuid.UUID(reg["user_id"])

    # Grant consent
    client.post("/api/v1/consent/grant", headers={"Authorization": f"Bearer {token}"}, json={
        "type": "assessment_processing",
        "version": "v1.0",
        "granted": True
    })

    # Start assessment session
    client.post("/api/v1/assessments/start", json={"user_id": str(user_id)})

    # 1. Export Data
    exp_resp = client.get("/api/v1/privacy/export", headers={"Authorization": f"Bearer {token}"})
    assert exp_resp.status_code == 200
    export_json = exp_resp.json()
    assert export_json["user"]["email"] == email
    assert len(export_json["consents"]) >= 1
    assert len(export_json["assessments"]) >= 1

    # 2. Purge Account
    del_resp = client.delete("/api/v1/privacy/delete-account", headers={"Authorization": f"Bearer {token}"})
    assert del_resp.status_code == 200

    # 3. Verify user and sessions erased
    from app.models.user import User
    from app.models.session import AssessmentSession
    assert db.get(User, user_id) is None
    assert db.query(AssessmentSession).filter_by(user_id=str(user_id)).count() == 0


def test_dashboard_ui_served(client):
    """Verify HTML frontend is mounted and served at root /."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Agent Bleu" in resp.text
    assert "Reflective Psychometric Assessment" in resp.text
