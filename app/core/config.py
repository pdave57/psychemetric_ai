"""Environment-backed application configuration."""
import os
from dotenv import load_dotenv

load_dotenv()

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()

_raw_database_url = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://psychemetre:letmein@123@localhost:5432/psychemetredb",
).strip()

# Convert legacy postgres:// or standard postgresql:// schemes to SQLAlchemy 2.0 psycopg3 dialect
if _raw_database_url.startswith("postgres://"):
    _raw_database_url = "postgresql+psycopg://" + _raw_database_url.removeprefix("postgres://")
elif _raw_database_url.startswith("postgresql://"):
    _raw_database_url = "postgresql+psycopg://" + _raw_database_url.removeprefix("postgresql://")

DATABASE_URL = _raw_database_url


def is_production() -> bool:
    return APP_ENV == "production"