"""Election-focused API routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from pollingapi.database import get_db
from pollingapi.models import Election, Poll

router = APIRouter(prefix="/elections", tags=["elections"])


class ElectionSummaryItem(BaseModel):
    election_id: int
    election_type: str
    scope: str | None
    year: int | None
    poll_count: int
    latest_publish_date: str | None


@router.get("", response_model=list[ElectionSummaryItem])
def list_election_summaries(db: Session = Depends(get_db)):
    """List elections with poll counts and latest publish date."""
    rows = (
        db.query(
            Election.id.label("election_id"),
            Election.election_type,
            Election.scope,
            Election.year,
            func.count(Poll.id).label("poll_count"),
            func.max(Poll.publish_date).label("latest_publish_date"),
        )
        .outerjoin(Poll, Poll.election_id == Election.id)
        .group_by(Election.id, Election.election_type, Election.scope, Election.year)
        .order_by(Election.id.asc())
        .all()
    )

    return [
        ElectionSummaryItem(
            election_id=row.election_id,
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


@router.get("/{election_id}", response_model=ElectionSummaryItem)
def get_election_summary(election_id: int, db: Session = Depends(get_db)):
    """Get one election summary by ID."""
    row = (
        db.query(
            Election.id.label("election_id"),
            Election.election_type,
            Election.scope,
            Election.year,
            func.count(Poll.id).label("poll_count"),
            func.max(Poll.publish_date).label("latest_publish_date"),
        )
        .outerjoin(Poll, Poll.election_id == Election.id)
        .filter(Election.id == election_id)
        .group_by(Election.id, Election.election_type, Election.scope, Election.year)
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail=f"Election {election_id} not found")

    return ElectionSummaryItem(
        election_id=row.election_id,
        election_type=row.election_type,
        scope=row.scope,
        year=row.year,
        poll_count=row.poll_count,
        latest_publish_date=row.latest_publish_date.isoformat()
        if row.latest_publish_date
        else None,
    )
