"""Utility script to initialize the database schema."""

from pathlib import Path
import sys

from sqlalchemy.exc import SQLAlchemyError

# Ensure repository root is importable when running the script directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db_init import init_db  # noqa: E402


if __name__ == "__main__":
    try:
        init_db()
    except SQLAlchemyError as exc:
        raise SystemExit(f"Failed to initialize database: {exc}") from exc
