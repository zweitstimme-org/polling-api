import json
import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import Forecast as ForecastSchema

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
