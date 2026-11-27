"""Async/await tests for FastAPI endpoints using httpx.AsyncClient and asyncio."""

import asyncio
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.llm import NullLLM
from app.models import *  # noqa: F401, F403
from app.main import app


def test_async_endpoints_and_concurrent_requests():
    """Verify async FastAPI routes handle concurrent requests via httpx.AsyncClient."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            health_resp, auth_resp, safety_resp, fb_q_resp, scales_resp = await asyncio.gather(
                ac.get("/health"),
                ac.get("/api/v1/auth/status"),
                ac.get("/api/v1/safety/resources"),
                ac.get("/api/v1/feedback/questions"),
                ac.get("/api/v1/catalogue/knowledge-pack/scales"),
            )
            assert health_resp.status_code == 200
            assert health_resp.json() == {"status": "ok"}
            assert auth_resp.status_code == 200
            assert safety_resp.status_code == 200
            assert len(fb_q_resp.json()["questions"]) == 5
            assert scales_resp.status_code == 200

            # Test async feedback submission + auth-gated read
            reg_resp = await ac.post(
                "/api/v1/auth/register",
                json={
                    "email": "pdave57@gmail.com",
                    "password": "AsyncPassword123!",
                    "is_adult_confirmed": True,
                },
            )
            assert reg_resp.status_code == 201
            token = reg_resp.json()["access_token"]

            fb_post, fb_post_2 = await asyncio.gather(
                ac.post(
                    "/api/v1/feedback",
                    json={
                        "experience_rating": 9,
                        "ease_of_use": 5,
                        "insightfulness": 4,
                        "most_valuable_aspect": "ui_design",
                        "would_recommend": True,
                    },
                ),
                ac.post(
                    "/api/v1/feedback",
                    json={
                        "experience_rating": 7,
                        "ease_of_use": 4,
                        "insightfulness": 4,
                        "most_valuable_aspect": "assessment_flow",
                        "would_recommend": True,
                    },
                ),
            )
            assert fb_post.status_code == 201
            assert fb_post_2.status_code == 201

            summary_resp = await ac.get(
                "/api/v1/feedback/summary",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert summary_resp.status_code == 200
            assert summary_resp.json()["total_responses"] == 2
            assert summary_resp.json()["average_experience_rating"] == 8.0

    try:
        asyncio.run(_run())
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_llm_agenerate_fallback():
    """Verify BaseLLM/NullLLM agenerate works asynchronously."""
    llm = NullLLM()
    text = asyncio.run(llm.agenerate("Test prompt"))
    assert "reflective temperament pattern" in text.lower()
