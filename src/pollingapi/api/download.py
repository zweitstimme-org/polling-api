"""Download/export API router.

Serves pre-generated files from export_dir (created by `pollingapi export:all`).
If a file is missing, returns 404. No on-the-fly generation.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from pollingapi.core import settings

router = APIRouter(prefix="/download")

EXPORT_DIR = settings.export_dir
DATA_DIR = settings.data_dir

FILENAME_JSON = "german_election_polls.json"
FILENAME_CSV = "german_election_polls.csv"
FILENAME_PARQUET = "german_election_polls.parquet"
FILENAME_RAW = "german_election_polls_raw.json"
FILENAME_RESULTS = "german_election_poll_results.json"


def _file_or_404(file_path: Path, filename: str, media_type: str):
    """Return FileResponse or raise 404."""
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Export file not found. Run `pollingapi export:all` to generate {filename}.",
        )
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type,
    )


@router.get("/json")
def download_json():
    """Download polls as JSON. Requires pre-generated file from export:all."""
    return _file_or_404(
        EXPORT_DIR / "polls.json",
        FILENAME_JSON,
        "application/json",
    )


@router.get("/sqlite")
def download_sqlite():
    """Download SQLite database."""
    path = DATA_DIR / "polling.db"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Database file not found")
    return FileResponse(
        path=path,
        filename="german_election_polls.db",
        media_type="application/x-sqlite3",
    )


@router.get("/csv")
def download_csv():
    """Download polls as CSV. Requires pre-generated file from export:all."""
    return _file_or_404(
        EXPORT_DIR / "polls.csv",
        FILENAME_CSV,
        "text/csv",
    )


@router.get("/parquet")
def download_parquet():
    """Download polls as Parquet. Requires pre-generated file from export:all."""
    return _file_or_404(
        EXPORT_DIR / "polls.parquet",
        FILENAME_PARQUET,
        "application/octet-stream",
    )


@router.get("/raw")
def download_raw():
    """Download raw polls as JSON. Requires pre-generated file from export:all."""
    return _file_or_404(
        EXPORT_DIR / "polls_raw.json",
        FILENAME_RAW,
        "application/json",
    )


@router.get("/results")
def download_results():
    """Download flattened poll results as JSON. Requires pre-generated file from export:all."""
    return _file_or_404(
        EXPORT_DIR / "poll_results.json",
        FILENAME_RESULTS,
        "application/json",
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
