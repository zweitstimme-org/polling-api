"""Main FastAPI application."""

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from pollingapi.api import (
    data,
    dictionaries,
    download,
    elections,
    polls,
)
from pollingapi.core import settings
from pollingapi.database import init_db_async

ICON_PATH = Path(__file__).resolve().parent / "api" / "favicon.ico"


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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.api_version,
        "timestamp": datetime.utcnow(),
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
