import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

DATA_PATH = Path("data") / "bundestagswahl.json"
DATE_PATH = Path("data") / "election_dates.json"


@router.get("/election/results/bundestag")
async def get_bundestagswahl():
    if not DATA_PATH.exists():
        raise HTTPException(status_code=404, detail="No results available")
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@router.get("/election/dates")
async def get_election_dates():
    if not DATE_PATH.exists():
        raise HTTPException(status_code=404, detail="No dates available")
    with open(DATE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data
