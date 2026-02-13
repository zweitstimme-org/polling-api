"""Download/export API router."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from pollingapi.core import settings

router = APIRouter(prefix="/download")

# Export paths (single source of truth from settings)
EXPORT_DIR = settings.export_dir
DATA_DIR = settings.data_dir


@router.get("/json")
def download_json():
    """Download polls as JSON."""
    file_path = EXPORT_DIR / "polls.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Export file not found")
    return FileResponse(
        path=file_path,
        filename="german_election_polls.json",
        media_type="application/json",
    )


@router.get("/sqlite")
def download_sqlite():
    """Download SQLite database."""
    file_path = DATA_DIR / "polling.db"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Database file not found")
    return FileResponse(
        path=file_path,
        filename="german_election_polls.db",
        media_type="application/x-sqlite3",
    )


@router.get("/csv")
def download_csv():
    """Download polls as CSV."""
    file_path = EXPORT_DIR / "polls.csv"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Export file not found")
    return FileResponse(
        path=file_path,
        filename="german_election_polls.csv",
        media_type="text/csv",
    )


@router.get("/parquet")
def download_parquet():
    """Download polls as Parquet."""
    file_path = EXPORT_DIR / "polls.parquet"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Export file not found")
    return FileResponse(
        path=file_path,
        filename="german_election_polls.parquet",
        media_type="application/octet-stream",
    )


@router.get("/raw")
def download_raw():
    """Download raw polls as JSON."""
    file_path = EXPORT_DIR / "polls_raw.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Export file not found")
    return FileResponse(
        path=file_path,
        filename="german_election_polls_raw.json",
        media_type="application/json",
    )


@router.get("/results")
def download_results():
    """Download flattened poll results as JSON."""
    file_path = EXPORT_DIR / "poll_results.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Export file not found")
    return FileResponse(
        path=file_path,
        filename="german_election_poll_results.json",
        media_type="application/json",
    )


@router.get("")
def list_download_assets():
    """List available downloadable assets."""
    return {
        "assets": {
            "json": "/v1/download/json",
            "results_json": "/v1/download/results",
            "raw_json": "/v1/download/raw",
            "csv": "/v1/download/csv",
            "parquet": "/v1/download/parquet",
            "sqlite": "/v1/download/sqlite",
        }
    }
