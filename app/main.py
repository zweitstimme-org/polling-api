import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.auth import verify_token
from app.db_init import init_db

from .routers import (
    download,
    election,
    hook_bundestag_scraper,
    hook_db,
    hook_election_date,
    polls,
)

load_dotenv()

app = FastAPI(
    title=os.getenv("API_TITLE", "Zweitstimme Polling Api"),
    version=os.getenv("API_VERSION", "0.0.1"),
    description=os.getenv(
        "API_DESCRIPTION",
        "The one stop Api for all things german elections \n proudly presented by zweitstimme.org",
    ),
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _initialize_database() -> None:
    """Ensure the database schema is present when the service boots."""
    init_db()


# Include routers
app.include_router(polls.router, prefix="", tags=["polls"])
app.include_router(polls.raw_router, prefix="", tags=["raw polls"])
app.include_router(download.router, prefix="", tags=["export"])
# app.include_router(dates.router, prefix="", tags=["election-dates"])
app.include_router(election.router, prefix="", tags=["election"])
app.include_router(hook_bundestag_scraper.router, prefix="", tags=["webhooks"])
app.include_router(hook_election_date.router, prefix="", tags=["webhooks"])
app.include_router(hook_db.router, prefix="", tags=["webhooks"])


@app.get("/")
def root():
    """Root endpoint with API information"""
    return {
        "message": "German Election Polls API",
        "version": "1.0.0",
        "endpoints": {
            "get_all_polls": "/polls",
            "get_recent_polls": "/polls/recent",
            "download_json": "/polls/download/json",
            "download_sqlite": "/polls/download/sqlite",
            "download_sql": "/polls/download/sql",
            "download_csv": "/polls/download/csv",
        },
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
