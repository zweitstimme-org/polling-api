import json
import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import RawPolls
from ..schemas import Forecast as ForecastSchema
from ..schemas import RawPoll as RawPollSchema

router = APIRouter(prefix="/polls", tags=["polls"])


@router.get("/", response_model=List[ForecastSchema])
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


@router.get("/raw", response_model=List[RawPollSchema])
def get_raw_polls(db: Session = Depends(get_db)):
    """Return all rows from the raw polls table"""
    # Sort by primary key to provide stable output ordering for clients.
    polls = db.query(RawPolls).order_by(RawPolls.id).all()
    return polls
