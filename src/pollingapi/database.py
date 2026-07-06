"""Database configuration and connection management."""

from contextlib import suppress

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from pollingapi.core import settings

# Create base class for models
Base = declarative_base()

# Synchronous engine and session
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Async engine and session
async_engine = create_async_engine(
    settings.async_database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.async_database_url else {},
    echo=False,
)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)


def _apply_schema_migrations():
    """Apply incremental schema changes that cannot be expressed via create_all.

    Safe to run on every startup: each migration is guarded by a presence check
    so it is a no-op when the column/index already exists.  Only touches tables
    that actually exist — new databases are fully covered by create_all.
    """
    with engine.connect() as conn:
        # --- polls_raw incremental columns -----------------------------------
        if "sqlite" in settings.database_url:
            # Check whether the table exists at all before inspecting columns
            tables = {
                row[0]
                for row in conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                ).fetchall()
            }
            if "polls_raw" in tables:
                rows = conn.execute(text("PRAGMA table_info(polls_raw)")).fetchall()
                existing_columns = {row[1] for row in rows}

                if "pipeline_run_id" not in existing_columns:
                    conn.execute(text("ALTER TABLE polls_raw ADD COLUMN pipeline_run_id TEXT"))
                    conn.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS ix_polls_raw_pipeline_run_id"
                            " ON polls_raw (pipeline_run_id)"
                        )
                    )

                if "worker" not in existing_columns:
                    conn.execute(text("ALTER TABLE polls_raw ADD COLUMN worker TEXT"))

                if "survey_type" not in existing_columns:
                    conn.execute(text("ALTER TABLE polls_raw ADD COLUMN survey_type TEXT"))

                if "duplicate_of_poll_id" not in existing_columns:
                    conn.execute(
                        text("ALTER TABLE polls_raw ADD COLUMN duplicate_of_poll_id INTEGER")
                    )
                    conn.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS ix_polls_raw_duplicate_of_poll_id"
                            " ON polls_raw (duplicate_of_poll_id)"
                        )
                    )

            if "polls" in tables:
                rows = conn.execute(text("PRAGMA table_info(polls)")).fetchall()
                existing_columns = {row[1] for row in rows}

                if "fingerprint" not in existing_columns:
                    conn.execute(text("ALTER TABLE polls ADD COLUMN fingerprint TEXT"))
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ix_polls_fingerprint"
                        " ON polls (fingerprint)"
                    )
                )

            conn.commit()
        else:
            # PostgreSQL / other dialects
            raw_table_exists = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables WHERE table_name = 'polls_raw' LIMIT 1"
                )
            ).fetchone()
            if raw_table_exists:
                result = conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns"
                        " WHERE table_name = 'polls_raw' AND column_name = 'pipeline_run_id'"
                    )
                )
                if result.fetchone() is None:
                    conn.execute(
                        text("ALTER TABLE polls_raw ADD COLUMN pipeline_run_id VARCHAR(36)")
                    )
                    conn.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS ix_polls_raw_pipeline_run_id"
                            " ON polls_raw (pipeline_run_id)"
                        )
                    )

                worker_result = conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns"
                        " WHERE table_name = 'polls_raw' AND column_name = 'worker'"
                    )
                )
                if worker_result.fetchone() is None:
                    conn.execute(text("ALTER TABLE polls_raw ADD COLUMN worker VARCHAR(100)"))

                survey_type_result = conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns"
                        " WHERE table_name = 'polls_raw' AND column_name = 'survey_type'"
                    )
                )
                if survey_type_result.fetchone() is None:
                    conn.execute(text("ALTER TABLE polls_raw ADD COLUMN survey_type VARCHAR(100)"))

                duplicate_result = conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns"
                        " WHERE table_name = 'polls_raw' AND column_name = 'duplicate_of_poll_id'"
                    )
                )
                if duplicate_result.fetchone() is None:
                    conn.execute(
                        text("ALTER TABLE polls_raw ADD COLUMN duplicate_of_poll_id INTEGER")
                    )
                    conn.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS ix_polls_raw_duplicate_of_poll_id"
                            " ON polls_raw (duplicate_of_poll_id)"
                        )
                    )

            polls_table_exists = conn.execute(
                text("SELECT 1 FROM information_schema.tables WHERE table_name = 'polls' LIMIT 1")
            ).fetchone()
            if polls_table_exists:
                fingerprint_result = conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns"
                        " WHERE table_name = 'polls' AND column_name = 'fingerprint'"
                    )
                )
                if fingerprint_result.fetchone() is None:
                    conn.execute(text("ALTER TABLE polls ADD COLUMN fingerprint VARCHAR(64)"))
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ix_polls_fingerprint"
                        " ON polls (fingerprint)"
                    )
                )

            conn.commit()


# Run schema migrations eagerly so any process that imports this module
# (including test clients that mock init_db_async) always works with an
# up-to-date schema on existing databases.
with suppress(Exception):
    _apply_schema_migrations()


def get_db():
    """Get synchronous database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db():
    """Get asynchronous database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def init_db(drop_all: bool = False):
    """Initialize database tables.

    Args:
        drop_all: If True, drop all tables before creating them.
    """
    if drop_all:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _apply_schema_migrations()


async def init_db_async():
    """Initialize database tables asynchronously."""
    # Import models to ensure they're registered

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Schema migrations run synchronously (rare, fast, idempotent)
    _apply_schema_migrations()


# --- Reference data seeding -------------------------------------------------


def seed_all_from_json(db: Session) -> dict:
    """Seed all reference tables from JSON files.

    Uses the JSON files in the json/ directory to seed reference tables
    with the exact primary keys defined in those files.
    """
    from pollingapi.database_seed import seed_all_from_json as _seed_from_json

    return _seed_from_json(db)
