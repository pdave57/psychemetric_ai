"""Environment-backed application configuration."""
import os

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
_raw_database_url = os.getenv("DATABASE_URL", "sqlite:///./psychemetre.db").strip()
# Render and some managed PostgreSQL providers still supply the legacy scheme.
if _raw_database_url.startswith("postgres://"):
    _raw_database_url = "postgresql+psycopg://" + _raw_database_url.removeprefix("postgres://")
DATABASE_URL = _raw_database_url


def is_production() -> bool:
    return APP_ENV == "production"