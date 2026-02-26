"""Download/export API router.

Serves pre-generated files from export_dir when present (e.g. after `pollingapi export:all`).
When files are missing (e.g. on Render after fresh deploy), generates content on-the-fly
from the database so download endpoints always return 200 with current data (possibly empty).
"""

import io
import json
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session, joinedload

from pollingapi.core import settings
from pollingapi.database import get_db
from pollingapi.models import Poll, RawPoll

router = APIRouter(prefix="/download")

# Export paths (single source of truth from settings)
EXPORT_DIR = settings.export_dir
DATA_DIR = settings.data_dir

FILENAME_JSON = "german_election_polls.json"
FILENAME_CSV = "german_election_polls.csv"
FILENAME_PARQUET = "german_election_polls.parquet"
FILENAME_RAW = "german_election_polls_raw.json"
FILENAME_RESULTS = "german_election_poll_results.json"


def _polls_export_data(db: Session) -> list[dict]:
    """Build polls export payload from DB (same shape as CLI export:all)."""
    polls = db.query(Poll).options(joinedload(Poll.results)).order_by(Poll.publish_date.desc()).all()
    out = []
    for poll in polls:
        out.append({
            "id": poll.id,
            "raw_id": poll.raw_id,
            "publish_date": poll.publish_date.isoformat() if poll.publish_date else None,
            "survey_date_start": poll.survey_date_start.isoformat() if poll.survey_date_start else None,
            "survey_date_end": poll.survey_date_end.isoformat() if poll.survey_date_end else None,
            "respondents": poll.respondents,
            "institute_id": poll.institute_id,
            "provider_id": poll.provider_id,
            "method_id": poll.method_id,
            "election_id": poll.election_id,
            "scope": poll.scope,
            "results": [{"party_id": r.party_id, "percentage": r.percentage} for r in poll.results],
        })
    return out


def _raw_export_data(db: Session) -> list[dict]:
    """Build raw polls export payload from DB."""
    rows = db.query(RawPoll).order_by(RawPoll.id).all()
    return [
        {
            "id": r.id,
            "publish_date": r.publish_date,
            "survey_date_start": r.survey_date_start,
            "survey_date_end": r.survey_date_end,
            "respondents": r.respondents,
            "zeitraum": r.zeitraum,
            "parties": r.parties,
            "institute_id": r.institute_id,
            "provider": r.provider,
            "tasker": r.tasker,
            "source": r.source,
            "scope": r.scope,
            "election_id": r.election_id,
            "method_id": r.method_id,
            "date_downloaded": r.date_downloaded,
        }
        for r in rows
    ]


def _poll_results_export_data(polls_data: list[dict]) -> list[dict]:
    """Flatten poll results from polls_data (same as CLI)."""
    out = []
    for poll in polls_data:
        for result in poll.get("results", []):
            out.append({
                "poll_id": poll["id"],
                "raw_id": poll.get("raw_id"),
                "publish_date": poll.get("publish_date"),
                "scope": poll.get("scope"),
                "party_id": result.get("party_id"),
                "percentage": result.get("percentage"),
            })
    return out


def _stream_json(filename: str, data: list[dict], media_type: str = "application/json") -> Response:
    """Return JSON response with Content-Disposition for download."""
    body = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/json")
def download_json(db: Session = Depends(get_db)):
    """Download polls as JSON. Serves file if present, else generates from DB."""
    file_path = EXPORT_DIR / "polls.json"
    if file_path.exists():
        return FileResponse(
            path=file_path,
            filename=FILENAME_JSON,
            media_type="application/json",
        )
    data = _polls_export_data(db)
    return _stream_json(FILENAME_JSON, data)


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
def download_csv(db: Session = Depends(get_db)):
    """Download polls as CSV. Serves file if present, else generates from DB."""
    file_path = EXPORT_DIR / "polls.csv"
    if file_path.exists():
        return FileResponse(
            path=file_path,
            filename=FILENAME_CSV,
            media_type="text/csv",
        )
    polls_data = _polls_export_data(db)
    if not polls_data:
        csv_content = "id,raw_id,publish_date,survey_date_start,survey_date_end,respondents,institute_id,provider_id,method_id,election_id,scope\n"
    else:
        df = pd.DataFrame(polls_data)
        if "results" in df.columns:
            df = df.drop(columns=["results"])
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        csv_content = buf.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{FILENAME_CSV}"'},
    )


@router.get("/parquet")
def download_parquet(db: Session = Depends(get_db)):
    """Download polls as Parquet. Serves file if present, else generates from DB."""
    file_path = EXPORT_DIR / "polls.parquet"
    if file_path.exists():
        return FileResponse(
            path=file_path,
            filename=FILENAME_PARQUET,
            media_type="application/octet-stream",
        )
    polls_data = _polls_export_data(db)
    if not polls_data:
        df = pd.DataFrame(columns=["id", "raw_id", "publish_date", "scope"])
    else:
        df = pd.DataFrame(polls_data)
        if "results" in df.columns:
            df = df.drop(columns=["results"])
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    return Response(
        content=buf.getvalue(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{FILENAME_PARQUET}"'},
    )


@router.get("/raw")
def download_raw(db: Session = Depends(get_db)):
    """Download raw polls as JSON. Serves file if present, else generates from DB."""
    file_path = EXPORT_DIR / "polls_raw.json"
    if file_path.exists():
        return FileResponse(
            path=file_path,
            filename=FILENAME_RAW,
            media_type="application/json",
        )
    data = _raw_export_data(db)
    return _stream_json(FILENAME_RAW, data)


@router.get("/results")
def download_results(db: Session = Depends(get_db)):
    """Download flattened poll results as JSON. Serves file if present, else generates from DB."""
    file_path = EXPORT_DIR / "poll_results.json"
    if file_path.exists():
        return FileResponse(
            path=file_path,
            filename=FILENAME_RESULTS,
            media_type="application/json",
        )
    polls_data = _polls_export_data(db)
    data = _poll_results_export_data(polls_data)
    return _stream_json(FILENAME_RESULTS, data)


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
