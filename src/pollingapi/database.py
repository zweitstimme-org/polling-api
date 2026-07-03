"""Database configuration and connection management."""

from contextlib import suppress

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from pollingapi.core import settings
from pollingapi.scraper.fingerprint import build_content_hash

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


def _backfill_raw_content_hashes(conn) -> None:
    """Populate missing raw poll content hashes without collapsing existing rows."""
    rows = conn.execute(
        text(
            "SELECT id, publish_date, survey_date_start, survey_date_end, respondents,"
            ' "Zeitraum" AS zeitraum, parties, institute_id, provider, tasker, source,'
            " scope, election_id, method_id, worker, survey_type, content_hash"
            " FROM polls_raw"
        )
    ).fetchall()
    existing_hashes = {row._mapping["content_hash"] for row in rows if row._mapping["content_hash"]}

    for row in rows:
        raw = dict(row._mapping)
        if raw.get("content_hash"):
            continue
        content_hash = build_content_hash(raw)
        if content_hash in existing_hashes:
            continue
        conn.execute(
            text("UPDATE polls_raw SET content_hash = :content_hash WHERE id = :id"),
            {"content_hash": content_hash, "id": raw["id"]},
        )
        existing_hashes.add(content_hash)


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
            if "polls_raw" not in tables:
                return
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

            if "content_hash" not in existing_columns:
                conn.execute(text("ALTER TABLE polls_raw ADD COLUMN content_hash TEXT"))
            _backfill_raw_content_hashes(conn)
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_polls_raw_content_hash"
                    " ON polls_raw (content_hash)"
                )
            )

            conn.commit()
        else:
            # PostgreSQL / other dialects
            table_exists = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables WHERE table_name = 'polls_raw' LIMIT 1"
                )
            ).fetchone()
            if not table_exists:
                return
            result = conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns"
                    " WHERE table_name = 'polls_raw' AND column_name = 'pipeline_run_id'"
                )
            )
            if result.fetchone() is None:
                conn.execute(text("ALTER TABLE polls_raw ADD COLUMN pipeline_run_id VARCHAR(36)"))
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

            content_hash_result = conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns"
                    " WHERE table_name = 'polls_raw' AND column_name = 'content_hash'"
                )
            )
            if content_hash_result.fetchone() is None:
                conn.execute(text("ALTER TABLE polls_raw ADD COLUMN content_hash VARCHAR(64)"))
            _backfill_raw_content_hashes(conn)
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_polls_raw_content_hash"
                    " ON polls_raw (content_hash)"
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
