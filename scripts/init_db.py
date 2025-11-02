"""Utility script to initialize the development database schema."""

from pathlib import Path
import sys

from sqlalchemy.exc import SQLAlchemyError

# Ensure repository root is importable when running the script directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import Base, engine

# Import models so that SQLAlchemy registers all tables.
import app.models  # noqa: F401


def init_db() -> None:
    try:
        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError as exc:
        raise SystemExit(f"Failed to initialize database: {exc}") from exc


if __name__ == "__main__":
    init_db()
