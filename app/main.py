"""FastAPI application entry point.

Startup hook:
  - Creates all SQLAlchemy tables (dev / test only; production uses Alembic).
  - Seeds the prototype instrument and recommendation templates idempotently.
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.database import Base, engine, SessionLocal
from app.core.logging import configure_logging
from app.repositories.assessment_repository import seed_initial_instrument
from app.services.recommendation_service import seed_recommendation_templates
from app.api.routes import (
    auth,
    consent,
    catalogue,
    assessments,
    questions,
    emotions,
    reports,
    recommendations,
    safety,
    history,
    agent_execution,
    knowledge,
    privacy,
)

configure_logging()

app = FastAPI(
    title="Agent Bleu — Personal Assessment API",
    version="0.5.0",
    description=(
        "Reflective temperament assessment, emotional self-reports, "
        "personalized recommendations, safety monitoring, LangGraph orchestration, "
        "RAG knowledge retrieval, and NDPR/GDPR privacy controls. Backend for Agent Bleu."
    ),
)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_initial_instrument(db)
        seed_recommendation_templates(db)
    finally:
        db.close()


for route, prefix, tag in [
    (auth.router,            "/api/v1/auth",            "Authentication"),
    (consent.router,         "/api/v1/consent",         "Consent"),
    (catalogue.router,       "/api/v1/catalogue",       "Assessment Catalogue"),
    (assessments.router,     "/api/v1/assessments",     "Assessments"),
    (questions.router,       "/api/v1/questions",       "Questions"),
    (emotions.router,        "/api/v1/emotions",        "Emotional self-reports"),
    (reports.router,         "/api/v1/reports",         "Reports"),
    (recommendations.router, "/api/v1/recommendations", "Recommendations"),
    (safety.router,          "/api/v1/safety",          "Safety Monitoring"),
    (history.router,         "/api/v1/history",         "Assessment History"),
    (agent_execution.router, "/api/v1/agents",          "Agent Orchestration"),
    (knowledge.router,       "/api/v1/knowledge",       "Knowledge Base / RAG"),
    (privacy.router,         "/api/v1/privacy",         "Data Privacy & NDPR"),
]:
    app.include_router(route, prefix=prefix, tags=[tag])

# Serve static dashboard if directory exists
static_path = Path(__file__).resolve().parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=static_path), name="static")

    @app.get("/")
    def serve_dashboard():
        return FileResponse(static_path / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}
