"""Main FastAPI application."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from pollingapi.api import (
    data,
    dictionaries,
    download,
    elections,
    polls,
)
from pollingapi.core import settings
from pollingapi.database import get_db, init_db_async
from pollingapi.models import PipelineRun, Poll
from pollingapi.schemas import HealthCheck

ICON_PATH = Path(__file__).resolve().parent / "api" / "favicon.ico"
DB_SESSION_DEP = Depends(get_db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    await init_db_async()
    yield
    # Shutdown


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    lifespan=lifespan,
    openapi_tags=[
        {"name": "polls", "description": "Cleaned, normalized polling data"},
        {"name": "raw-polls", "description": "Raw scraped rows (immutable source data)"},
        {"name": "results", "description": "Flattened poll results with filters"},
        {"name": "reference", "description": "Reference/dictionary tables"},
        {"name": "elections", "description": "Election summaries and metadata"},
        {"name": "downloads", "description": "File exports (JSON/CSV/SQLite)"},
        {"name": "archive", "description": "Data archive downloads (S3)"},
        {"name": "health", "description": "Service heartbeat and dependency checks"},
    ],
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include v1 routers
app.include_router(polls.router, prefix="/v1")
app.include_router(polls.raw_router, prefix="/v1")
app.include_router(polls.results_router, prefix="/v1")
app.include_router(download.router, prefix="/v1", tags=["downloads"])
app.include_router(elections.router, prefix="/v1")
app.include_router(dictionaries.router, prefix="/v1")
app.include_router(data.router, prefix="/v1")


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Zweitstimme Polling API",
        "version": settings.api_version,
        "documentation": "/docs",
        "openapi": "/openapi.json",
        "api_base": "/v1",
        "endpoints": [
            "/v1/polls",
            "/v1/raw-polls",
            "/v1/reference/all",
            "/v1/elections",
            "/v1/download",
        ],
    }


def _isoformat_utc(dt: datetime) -> str:
    """Convert datetime to RFC3339 UTC format."""
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


@app.get("/health", response_model=HealthCheck, tags=["health"])
@app.get("/heartbeat", response_model=HealthCheck, tags=["health"])
async def health_check(db: Session = DB_SESSION_DEP):
    """Heartbeat endpoint with API and data freshness status."""
    now = datetime.now(UTC)
    poll_count = db.query(Poll).count()
    latest_run = db.query(PipelineRun).order_by(PipelineRun.finished_at.desc()).first()

    pipeline_check_status = "pass"
    last_run_time = None
    last_run_ago_seconds = None
    if latest_run and latest_run.finished_at:
        finished_at_utc = latest_run.finished_at.astimezone(UTC)
        last_run_time = _isoformat_utc(finished_at_utc)
        last_run_ago_seconds = int((now - finished_at_utc).total_seconds())
    else:
        pipeline_check_status = "warn"

    overall_status = "pass" if pipeline_check_status == "pass" else "warn"

    return {
        "status": overall_status,
        "service": "pollingapi",
        "version": settings.api_version,
        "release_id": settings.api_version,
        "time": _isoformat_utc(now),
        "total_polls": poll_count,
        "last_run_at": last_run_time,
        "time_since_last_run_seconds": last_run_ago_seconds,
        "checks": {
            "database:polls": [
                {
                    "status": "pass",
                    "component_type": "datastore",
                    "component_id": "primary",
                    "observed_value": poll_count,
                    "observed_unit": "polls",
                    "time": _isoformat_utc(now),
                }
            ],
            "pipeline:last_run": [
                {
                    "status": pipeline_check_status,
                    "component_type": "system",
                    "component_id": "pipeline",
                    "observed_value": last_run_ago_seconds,
                    "observed_unit": "s",
                    "time": last_run_time,
                }
            ],
        },
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    """Serve favicon for browser tabs."""
    return FileResponse(ICON_PATH)


def run_server():
    """Run the API server."""
    import uvicorn

    uvicorn.run(
        "pollingapi.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )


if __name__ == "__main__":
    run_server()
