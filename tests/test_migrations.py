"""Migration tests: verify Alembic upgrade/downgrade and schema drift."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_alembic(database_url: str, *args: str):
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )


def test_alembic_upgrade_downgrade_and_schema_match(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'migration_test.db'}"

    run_alembic(database_url, "upgrade", "head")
    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())

    # Core v2 tables that must exist after upgrade head.
    expected = {
        "alembic_version",
        "users",
        "consent_records",
        "assessment_versions",
        "assessment_domains",
        "questions",
        "question_options",
        "consistency_pairs",
        "assessment_sessions",
        "user_responses",
        "temperament_scores",
        "emotion_assessments",
        "emotional_triggers",
        "assessment_reports",
        "recommendation_templates",
        "recommendations",
        "recommendation_history",
        "safety_events",
        "audit_log",
        "knowledge_documents",
        "knowledge_chunks",
    }
    assert expected.issubset(tables), f"Missing tables: {expected - tables}"
    engine.dispose()

    # Downgrade to base must remove the application schema cleanly.
    run_alembic(database_url, "downgrade", "base")
    engine = create_engine(database_url)
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    engine.dispose()

    # Upgrade again and verify metadata has no drift.
    run_alembic(database_url, "upgrade", "head")
    run_alembic(database_url, "check")
