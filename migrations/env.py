from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from app.core.config import DATABASE_URL
from app.core.database import Base
# Import every model module so all tables are registered on Base.metadata.
from app import models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Escape percent signs because ConfigParser treats them as interpolation markers.
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "column" and name == "embedding" and getattr(object, "table", None) is not None and object.table.name == "knowledge_chunks":
        # SQLite reflects VECTOR(1536) as NUMERIC(1536). Ignore this false-positive drift on SQLite.
        if DATABASE_URL.startswith("sqlite"):
            return False
    if type_ == "column" and name == "id" and getattr(object, "table", None) is not None and object.table.name == "audit_log":
        # SQLite autoincrement primary key type comparison between Integer and BigInteger
        if DATABASE_URL.startswith("sqlite"):
            return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        {"sqlalchemy.url": DATABASE_URL},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
