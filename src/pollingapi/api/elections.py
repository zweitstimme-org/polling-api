"""Election-focused API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from pollingapi.database import get_db
from pollingapi.models import Election, Poll

router = APIRouter(prefix="/elections", tags=["elections"])
DBSession = Annotated[Session, Depends(get_db)]


class ElectionSummaryItem(BaseModel):
    election_key: str
    election_type: str
    scope: str | None
    year: int | None
    poll_count: int
    latest_publish_date: str | None


@router.get("", response_model=list[ElectionSummaryItem])
def list_election_summaries(db: DBSession):
    """List elections with poll counts and latest publish date."""
    rows = (
        db.query(
            Election.key.label("election_key"),
            Election.election_type,
            Election.scope,
            Election.year,
            func.count(Poll.id).label("poll_count"),
            func.max(Poll.publish_date).label("latest_publish_date"),
        )
        .outerjoin(Poll, Poll.election_key == Election.key)
        .group_by(Election.key, Election.election_type, Election.scope, Election.year)
        .order_by(Election.key.asc())
        .all()
    )

    return [
        ElectionSummaryItem(
            election_key=row.election_key,
            election_type=row.election_type,
            scope=row.scope,
            year=row.year,
            poll_count=row.poll_count,
            latest_publish_date=row.latest_publish_date.isoformat()
            if row.latest_publish_date
            else None,
        )
        for row in rows
    ]


@router.get("/{election_key}", response_model=ElectionSummaryItem)
def get_election_summary(election_key: str, db: DBSession):
    """Get one election summary by ID."""
    row = (
        db.query(
            Election.key.label("election_key"),
            Election.election_type,
            Election.scope,
            Election.year,
            func.count(Poll.id).label("poll_count"),
            func.max(Poll.publish_date).label("latest_publish_date"),
        )
        .outerjoin(Poll, Poll.election_key == Election.key)
        .filter(Election.key == election_key)
        .group_by(Election.key, Election.election_type, Election.scope, Election.year)
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail=f"Election {election_key} not found")

    return ElectionSummaryItem(
        election_key=row.election_key,
        election_type=row.election_type,
        scope=row.scope,
        year=row.year,
        poll_count=row.poll_count,
        latest_publish_date=row.latest_publish_date.isoformat()
        if row.latest_publish_date
        else None,
    )
