"""SQLAlchemy engine/session setup shared by the API and Alembic."""
from collections.abc import Callable, Generator
from typing import ParamSpec, TypeVar

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from app.core.config import DATABASE_URL

P = ParamSpec("P")
T = TypeVar("T")


async def run_sync(func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    """Run a blocking DB/service function in Starlette's threadpool from async routes."""
    return await run_in_threadpool(func, *args, **kwargs)


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str = DATABASE_URL) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(
        database_url,
        connect_args=connect_args,
        pool_pre_ping=not database_url.startswith("sqlite"),
    )


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()