"""FastAPI application entry point.

Startup hook:
  - Creates all SQLAlchemy tables (dev / test only; production uses Alembic).
  - Seeds the prototype instrument and recommendation templates idempotently.
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
    results,
    safety,
    history,
    agent_execution,
    knowledge,
    privacy,
    feedback,
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://agentblue.onrender.com",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    try:
        if "postgres" in str(engine.url):
            try:
                with engine.connect() as conn:
                    from sqlalchemy import text
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                    conn.commit()
            except Exception:
                pass
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            seed_initial_instrument(db)
            seed_recommendation_templates(db)
        finally:
            db.close()
    except Exception:
        # In isolated unit-test environments (e.g. TestClient with mocked/overridden get_db)
        # or offline builds, tolerate unreachable remote network database during startup.
        pass


for route, prefix, tag in [
    (auth.router,            "/api/v1/auth",            "Authentication"),
    (consent.router,         "/api/v1/consent",         "Consent"),
    (catalogue.router,       "/api/v1/catalogue",       "Assessment Catalogue"),
    (assessments.router,     "/api/v1/assessments",     "Assessments"),
    (questions.router,       "/api/v1/questions",       "Questions"),
    (emotions.router,        "/api/v1/emotions",        "Emotional self-reports"),
    (reports.router,         "/api/v1/reports",         "Reports"),
    (recommendations.router, "/api/v1/recommendations", "Recommendations"),
    (results.router,         "/api/v1/results",         "Assessment Results"),
    (safety.router,          "/api/v1/safety",          "Safety Monitoring"),
    (history.router,         "/api/v1/history",         "Assessment History"),
    (agent_execution.router, "/api/v1/agents",          "Agent Orchestration"),
    (knowledge.router,       "/api/v1/knowledge",       "Knowledge Base / RAG"),
    (privacy.router,         "/api/v1/privacy",         "Data Privacy & NDPR"),
    (feedback.router,        "/api/v1/feedback",        "User Feedback"),
]:
    app.include_router(route, prefix=prefix, tags=[tag])

# Serve static frontend / SPA
static_path = Path(__file__).resolve().parent / "static"
dist_path = Path(__file__).resolve().parent.parent / "agentbleu" / "dist"
frontend_dir = dist_path if (dist_path / "index.html").exists() else static_path

if frontend_dir.exists():
    if (frontend_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=frontend_dir / "assets"), name="assets")
    if (frontend_dir / "static").exists():
        app.mount("/static", StaticFiles(directory=frontend_dir / "static"), name="static")

    @app.get("/")
    def serve_dashboard():
        return FileResponse(frontend_dir / "index.html")

    @app.get("/{full_path:path}")
    def serve_spa_fallback(full_path: str):
        if full_path.startswith(("api/", "health", "docs", "redoc", "openapi.json")):
            raise HTTPException(404, detail="Not Found")
        target_file = frontend_dir / full_path
        if target_file.is_file():
            return FileResponse(target_file)
        return FileResponse(frontend_dir / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}
