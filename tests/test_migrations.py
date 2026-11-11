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
        [sys.executable, "-m", "alembic", *args], cwd=PROJECT_ROOT,
        env=env, text=True, capture_output=True, check=True,
    )


def test_alembic_upgrade_downgrade_and_schema_match(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'migration_test.db'}"
    run_alembic(database_url, "upgrade", "head")
    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    expected = {
        "alembic_version", "assessment_instruments", "assessment_sessions",
        "questions", "answer_options", "user_responses", "temperament_scores",
        "emotion_self_assessments", "assessment_reports",
    }
    assert expected.issubset(tables)
    engine.dispose()

    # A downgrade to base must remove the application schema cleanly.
    run_alembic(database_url, "downgrade", "base")
    engine = create_engine(database_url)
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    engine.dispose()

    # Upgrade again and verify metadata and migration history have no drift.
    run_alembic(database_url, "upgrade", "head")
    run_alembic(database_url, "check")
