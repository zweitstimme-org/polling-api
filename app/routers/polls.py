import datetime
import json
import os
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..models import RawPolls
from ..schemas import Poll as PollSchema
from ..schemas import RawPoll as RawPollSchema

router = APIRouter(prefix="/polls", tags=["polls"])
raw_router = APIRouter(prefix="/raw", tags=["raw polls"])
RAW_POLLS_EXPORT_PATH = Path(__file__).resolve().parent.parent / "data" / "polls_raw.json"


@router.get("/", response_model=List[PollSchema])
def get_all_polls(db: Session = Depends(get_db)):
    """Get all polls (JSON dump)"""
    json_path = "./data/polls.json"

    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="JSON file not found")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return JSONResponse(content=data)


@router.get("/recent")
def get_recent_polls(db: Session = Depends(get_db)):
    """Get recent polls from the current week (to be implemented later)"""
    # Placeholder for future implementation
    raise HTTPException(status_code=501, detail="Not implemented yet")


@raw_router.get("/", response_class=FileResponse)
def get_raw_polls():
    """Stream the pre-generated raw polls export file."""
    if not RAW_POLLS_EXPORT_PATH.exists():
        raise HTTPException(status_code=404, detail="Raw polls export not found")

    return FileResponse(
        RAW_POLLS_EXPORT_PATH,
        media_type="application/json",
        filename="polls_raw.json",
    )


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
