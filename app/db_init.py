"""Database initialization utilities."""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.database import Base, engine

# Ensure models are registered so metadata knows about all tables.
import app.models  # noqa: F401


def _ensure_database_exists(target_engine: Engine) -> None:
    """Create the target database if the postgres cluster is reachable."""
    url = target_engine.url
    database_name = url.database
    if not database_name:
        return

    admin_url = url.set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    with admin_engine.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": database_name},
        ).scalar()
        if not exists:
            preparer = postgresql.dialect().identifier_preparer
            quoted_name = preparer.quote(database_name)
            # AUTOCOMMIT avoids transaction errors for CREATE DATABASE statements.
            connection.execute(text(f"CREATE DATABASE {quoted_name}"))


def init_db() -> None:
    """Provision the configured database and apply the SQLAlchemy metadata."""
    _ensure_database_exists(engine)
    Base.metadata.create_all(bind=engine)


__all__ = ["init_db"]
