from unittest.mock import patch
from sqlalchemy.engine import make_url

from app.core.database import build_engine


def test_sqlite_engine_configuration():
    with patch("app.core.database.create_engine") as create:
        build_engine("sqlite://")
    args, kwargs = create.call_args
    assert make_url(args[0]).get_backend_name() == "sqlite"
    assert kwargs["connect_args"] == {"check_same_thread": False}
    assert kwargs["pool_pre_ping"] is False


def test_postgresql_engine_configuration_uses_psycopg():
    with patch("app.core.database.create_engine") as create:
        build_engine("postgresql+psycopg://user:pass@localhost:5432/innermap")
    args, kwargs = create.call_args
    assert make_url(args[0]).drivername == "postgresql+psycopg"
    assert kwargs["connect_args"] == {}
    assert kwargs["pool_pre_ping"] is True
