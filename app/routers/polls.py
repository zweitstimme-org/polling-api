import datetime
import json
import os
from datetime import date
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from sqlalchemy.orm import Session, joinedload

from ..database import SessionLocal, get_db
from ..models import Poll, PollResult, RawPolls
from ..schemas import Poll as PollSchema, PollResult as PollResultSchema
from ..schemas import RawPoll as RawPollSchema

router = APIRouter(prefix="/polls", tags=["polls"])
raw_router = APIRouter(prefix="/raw", tags=["raw polls"])
DATA_EXPORT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "export"
POLLS_EXPORT_PATH = DATA_EXPORT_DIR / "polls.json"
RAW_POLLS_EXPORT_PATH = DATA_EXPORT_DIR / "polls_raw.json"
POLL_RESULTS_EXPORT_PATH = DATA_EXPORT_DIR / "poll_results.json"


@router.get("/", response_class=JSONResponse)
def get_all_polls():
    """Get all polls from cached JSON file."""
    if not POLLS_EXPORT_PATH.exists():
        raise HTTPException(status_code=404, detail="Polls export not found")

    with open(POLLS_EXPORT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    return JSONResponse(content=data)


@router.get("/results", response_class=JSONResponse)
def get_poll_results():
    """Get all poll results from cached JSON file."""
    if not POLL_RESULTS_EXPORT_PATH.exists():
        raise HTTPException(status_code=404, detail="Poll results export not found")

    with open(POLL_RESULTS_EXPORT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    return JSONResponse(content=data)


@router.get("/range")
def get_polls_by_date_range(
    start_date: date = Query(..., description="Start date (inclusive) in YYYY-MM-DD format"),
    end_date: date = Query(..., description="End date (inclusive) in YYYY-MM-DD format"),
    db: Session = Depends(get_db),
):
    """Get polls and their results within a date range based on publish_date."""
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before or equal to end_date"
        )

    polls = (
        db.query(Poll)
        .options(joinedload(Poll.results))
        .filter(Poll.publish_date >= start_date)
        .filter(Poll.publish_date <= end_date)
        .order_by(Poll.publish_date.desc())
        .all()
    )

    def serialize_date(d):
        return d.isoformat() if d else None

    result = []
    for poll in polls:
        poll_data = {
            "id": poll.id,
            "raw_id": poll.raw_id,
            "publish_date": serialize_date(poll.publish_date),
            "survey_date_start": serialize_date(poll.survey_date_start),
            "survey_date_end": serialize_date(poll.survey_date_end),
            "respondents": poll.respondents,
            "scope": poll.scope,
            "institute_id": poll.institute_id,
            "provider_id": poll.provider_id,
            "election_id": poll.election_id,
            "method_id": poll.method_id,
            "results": [
                {
                    "id": r.id,
                    "poll_id": r.poll_id,
                    "raw_id": r.raw_id,
                    "party_id": r.party_id,
                    "percentage": r.percentage,
                }
                for r in poll.results
            ],
        }
        result.append(poll_data)

    return JSONResponse(content=result)


@router.get("/election/{election_id}")
def get_polls_by_election(
    election_id: int,
    start_date: Optional[date] = Query(None, description="Start date (inclusive) in YYYY-MM-DD format"),
    end_date: Optional[date] = Query(None, description="End date (inclusive) in YYYY-MM-DD format"),
    db: Session = Depends(get_db),
):
    """Get polls and their results filtered by election ID, with optional date range."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before or equal to end_date"
        )

    query = (
        db.query(Poll)
        .options(joinedload(Poll.results))
        .filter(Poll.election_id == election_id)
    )

    if start_date:
        query = query.filter(Poll.publish_date >= start_date)
    if end_date:
        query = query.filter(Poll.publish_date <= end_date)

    polls = query.order_by(Poll.publish_date.desc()).all()

    if not polls:
        raise HTTPException(
            status_code=404,
            detail=f"No polls found for election_id {election_id}"
        )

    def serialize_date(d):
        return d.isoformat() if d else None

    result = []
    for poll in polls:
        poll_data = {
            "id": poll.id,
            "raw_id": poll.raw_id,
            "publish_date": serialize_date(poll.publish_date),
            "survey_date_start": serialize_date(poll.survey_date_start),
            "survey_date_end": serialize_date(poll.survey_date_end),
            "respondents": poll.respondents,
            "scope": poll.scope,
            "institute_id": poll.institute_id,
            "provider_id": poll.provider_id,
            "election_id": poll.election_id,
            "method_id": poll.method_id,
            "results": [
                {
                    "id": r.id,
                    "poll_id": r.poll_id,
                    "raw_id": r.raw_id,
                    "party_id": r.party_id,
                    "percentage": r.percentage,
                }
                for r in poll.results
            ],
        }
        result.append(poll_data)

    return JSONResponse(content=result)


@router.get("/recent")
def get_recent_polls(db: Session = Depends(get_db)):
    """Get recent polls from the current week (to be implemented later)"""
    # Placeholder for future implementation
    raise HTTPException(status_code=501, detail="Not implemented yet")


@raw_router.get("/", response_class=JSONResponse)
def get_raw_polls():
    """Get all raw polls from cached JSON file."""
    if not RAW_POLLS_EXPORT_PATH.exists():
        raise HTTPException(status_code=404, detail="Raw polls export not found")

    with open(RAW_POLLS_EXPORT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    return JSONResponse(content=data)


@raw_router.get("/latest", response_model=List[RawPollSchema])
def get_latest_raw_polls(db: Session = Depends(get_db)):
    """Return the newest 100 raw polls ordered by descending id."""
    polls = (
        db.query(RawPolls)
        .order_by(RawPolls.id.desc())
        .limit(100)
        .all()
    )
    return polls


@raw_router.get("/stream", response_class=StreamingResponse)
def stream_raw_polls(batch_size: int = 1000):
    """
    Stream the full raw polls table as a JSON array without loading it all into memory.
    """

    def serialize_value(value):
        if isinstance(value, (datetime.date, datetime.datetime)):
            return value.isoformat()
        return value

    def serialize_poll(poll):
        return {
            column.name: serialize_value(getattr(poll, column.name))
            for column in poll.__table__.columns
        }

    def generate():
        session = SessionLocal()
        try:
            query = (
                session.query(RawPolls)
                .order_by(RawPolls.id)
                .yield_per(max(1, batch_size))
            )
            first = True
            yield b"["
            for poll in query:
                if not first:
                    yield b","
                first = False
                yield json.dumps(serialize_poll(poll)).encode("utf-8")
            yield b"]"
        finally:
            session.close()

    return StreamingResponse(generate(), media_type="application/json")
