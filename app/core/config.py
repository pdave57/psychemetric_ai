"""Environment-backed application configuration."""
import os
from dotenv import load_dotenv

load_dotenv()

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()

_raw_database_url = os.getenv(
    "DATABASE_URL",
    "",
).strip()


def _get_postgres_dialect() -> str:
    """Return the available PostgreSQL driver dialect for SQLAlchemy."""
    try:
        import psycopg  # psycopg v3
        return "postgresql+psycopg"
    except ImportError:
        pass
    try:
        import psycopg2  # psycopg v2 fallback
        return "postgresql+psycopg2"
    except ImportError:
        pass
    return "postgresql+psycopg"


_driver = _get_postgres_dialect()

# Normalize scheme to the active driver dialect
if _raw_database_url.startswith("postgres://"):
    _raw_database_url = f"{_driver}://" + _raw_database_url.removeprefix("postgres://")
elif _raw_database_url.startswith("postgresql://"):
    _raw_database_url = f"{_driver}://" + _raw_database_url.removeprefix("postgresql://")
elif _raw_database_url.startswith("postgresql+psycopg://") and _driver != "postgresql+psycopg":
    _raw_database_url = f"{_driver}://" + _raw_database_url.removeprefix("postgresql+psycopg://")
elif _raw_database_url.startswith("postgresql+psycopg2://") and _driver != "postgresql+psycopg2":
    _raw_database_url = f"{_driver}://" + _raw_database_url.removeprefix("postgresql+psycopg2://")

DATABASE_URL = _raw_database_url


def is_production() -> bool:
    return APP_ENV == "production"