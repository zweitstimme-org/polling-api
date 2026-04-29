"""Download/export API router."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from pollingapi.core import settings

router = APIRouter(prefix="/download")

EXPORT_DIR = settings.export_dir
DATA_DIR = settings.data_dir

AVAILABLE_FORMATS = {
    "polls": ["json", "csv", "parquet"],
    "poll_results": ["json", "csv", "parquet"],
    "raw_polls": ["json", "csv", "parquet"],
    "metadata": ["json"],
    "sqlite": ["db"],
}


@router.get("/json")
def download_polls_json():
    """Download cleaned polls as JSON."""
    file_path = EXPORT_DIR / "polls.json"
    if not file_path.exists():
        raise HTTPException(
            status_code=404, detail="Export file not found. Run: pollingapi export:all"
        )
    return FileResponse(
        path=file_path, filename="german_election_polls.json", media_type="application/json"
    )


@router.get("/csv")
def download_polls_csv():
    """Download cleaned polls as CSV."""
    file_path = EXPORT_DIR / "polls.csv"
    if not file_path.exists():
        raise HTTPException(
            status_code=404, detail="Export file not found. Run: pollingapi export:all"
        )
    return FileResponse(path=file_path, filename="german_election_polls.csv", media_type="text/csv")


@router.get("/parquet")
def download_polls_parquet():
    """Download cleaned polls as Parquet."""
    file_path = EXPORT_DIR / "polls.parquet"
    if not file_path.exists():
        raise HTTPException(
            status_code=404, detail="Export file not found. Run: pollingapi export:all"
        )
    return FileResponse(
        path=file_path,
        filename="german_election_polls.parquet",
        media_type="application/octet-stream",
    )


@router.get("/results")
def download_results_json():
    """Download poll-party results as JSON (long format)."""
    file_path = EXPORT_DIR / "poll_results.json"
    if not file_path.exists():
        raise HTTPException(
            status_code=404, detail="Export file not found. Run: pollingapi export:all"
        )
    return FileResponse(
        path=file_path, filename="german_election_poll_results.json", media_type="application/json"
    )


@router.get("/results/csv")
def download_results_csv():
    """Download poll-party results as CSV."""
    file_path = EXPORT_DIR / "poll_results.csv"
    if not file_path.exists():
        raise HTTPException(
            status_code=404, detail="Export file not found. Run: pollingapi export:all"
        )
    return FileResponse(
        path=file_path, filename="german_election_poll_results.csv", media_type="text/csv"
    )


@router.get("/results/parquet")
def download_results_parquet():
    """Download poll-party results as Parquet."""
    file_path = EXPORT_DIR / "poll_results.parquet"
    if not file_path.exists():
        raise HTTPException(
            status_code=404, detail="Export file not found. Run: pollingapi export:all"
        )
    return FileResponse(
        path=file_path,
        filename="german_election_poll_results.parquet",
        media_type="application/octet-stream",
    )


@router.get("/raw")
def download_raw_json():
    """Download raw polls as JSON."""
    file_path = EXPORT_DIR / "polls_raw.json"
    if not file_path.exists():
        raise HTTPException(
            status_code=404, detail="Export file not found. Run: pollingapi export:all"
        )
    return FileResponse(
        path=file_path, filename="german_election_polls_raw.json", media_type="application/json"
    )


@router.get("/raw/csv")
def download_raw_csv():
    """Download raw polls as CSV."""
    file_path = EXPORT_DIR / "polls_raw.csv"
    if not file_path.exists():
        raise HTTPException(
            status_code=404, detail="Export file not found. Run: pollingapi export:all"
        )
    return FileResponse(
        path=file_path, filename="german_election_polls_raw.csv", media_type="text/csv"
    )


@router.get("/raw/parquet")
def download_raw_parquet():
    """Download raw polls as Parquet."""
    file_path = EXPORT_DIR / "polls_raw.parquet"
    if not file_path.exists():
        raise HTTPException(
            status_code=404, detail="Export file not found. Run: pollingapi export:all"
        )
    return FileResponse(
        path=file_path,
        filename="german_election_polls_raw.parquet",
        media_type="application/octet-stream",
    )


@router.get("/sqlite")
def download_sqlite():
    """Download SQLite database."""
    file_path = DATA_DIR / "polling.db"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Database not found. Run: pollingapi db:init")
    return FileResponse(
        path=file_path, filename="german_election_polls.db", media_type="application/x-sqlite3"
    )


@router.get("/metadata")
def download_metadata():
    """Download export metadata."""
    file_path = EXPORT_DIR / "metadata.json"
    if not file_path.exists():
        raise HTTPException(
            status_code=404, detail="Export file not found. Run: pollingapi export:all"
        )
    return FileResponse(
        path=file_path,
        filename="german_election_polls_metadata.json",
        media_type="application/json",
    )


@router.get("")
def list_download_assets():
    """List available downloadable assets."""
    return {
        "polls": {
            "json": "/v1/download/json",
            "csv": "/v1/download/csv",
            "parquet": "/v1/download/parquet",
        },
        "poll_results": {
            "json": "/v1/download/results",
            "csv": "/v1/download/results/csv",
            "parquet": "/v1/download/results/parquet",
        },
        "raw_polls": {
            "json": "/v1/download/raw",
            "csv": "/v1/download/raw/csv",
            "parquet": "/v1/download/raw/parquet",
        },
        "sqlite": "/v1/download/sqlite",
        "metadata": "/v1/download/metadata",
    }
