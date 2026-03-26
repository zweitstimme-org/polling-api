"""Poll and raw-poll API routes."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from pollingapi.database import get_db
from pollingapi.models import Poll, PollResult, RawPoll

router = APIRouter(prefix="/polls", tags=["polls"])
raw_router = APIRouter(prefix="/raw-polls", tags=["raw-polls"])
results_router = APIRouter(prefix="/results", tags=["results"])


class PaginationMeta(BaseModel):
    total: int
    limit: int | None = None
    offset: int


class PollResultItem(BaseModel):
    party_id: int
    party_short_name: str | None = None
    party_name: str | None = None
    percentage: float


class PollItem(BaseModel):
    id: int
    raw_id: int | None = None
    publish_date: date | None = None
    survey_date_start: date | None = None
    survey_date_end: date | None = None
    respondents: int | None = None
    scope: str | None = None
    source: str | None = None
    institute_id: int | None = None
    institute_name: str | None = None
    provider_id: int | None = None
    provider_name: str | None = None
    election_id: int | None = None
    election_type: str | None = None
    method_id: int | None = None
    method_name: str | None = None
    date_downloaded: str | None = None
    results: list[PollResultItem] = Field(default_factory=list)


class PollListResponse(BaseModel):
    items: list[PollItem]
    meta: PaginationMeta


class RawPollItem(BaseModel):
    id: int
    publish_date: str | None = None
    survey_date_start: str | None = None
    survey_date_end: str | None = None
    respondents: str | None = None
    zeitraum: str | None = None
    parties: str | None = None
    institute_id: str | None = None
    provider: str | None = None
    tasker: str | None = None
    source: str | None = None
    scope: str | None = None
    election_id: str | None = None
    method_id: str | None = None
    date_downloaded: str | None = None


class RawPollListResponse(BaseModel):
    items: list[RawPollItem]
    meta: PaginationMeta


def _serialize_poll_result(result: PollResult) -> PollResultItem:
    party = result.party
    return PollResultItem(
        party_id=result.party_id,
        party_short_name=party.short_name if party else None,
        party_name=party.name if party else None,
        percentage=result.percentage,
    )


def _serialize_poll(poll: Poll, include_results: bool) -> PollItem:
    return PollItem(
        id=poll.id,
        raw_id=poll.raw_id,
        publish_date=poll.publish_date,
        survey_date_start=poll.survey_date_start,
        survey_date_end=poll.survey_date_end,
        respondents=poll.respondents,
        scope=poll.scope,
        source=poll.source,
        institute_id=poll.institute_id,
        institute_name=poll.institute.name if poll.institute else None,
        provider_id=poll.provider_id,
        provider_name=poll.provider.name if poll.provider else None,
        election_id=poll.election_id,
        election_type=poll.election.election_type if poll.election else None,
        method_id=poll.method_id,
        method_name=poll.method.name if poll.method else None,
        date_downloaded=poll.date_downloaded.isoformat() if poll.date_downloaded else None,
        results=[_serialize_poll_result(r) for r in poll.results] if include_results else [],
    )


@router.get("", response_model=PollListResponse)
def list_polls(
    db: Session = Depends(get_db),
    limit: int = Query(1000, ge=1, description="Max rows to return"),
    offset: int = Query(0, ge=0, description="Rows to skip"),
    scope: str | None = Query(None, description="Filter by scope (e.g. federal, bayern)"),
    institute_id: int | None = Query(None, description="Filter by institute ID"),
    provider_id: int | None = Query(None, description="Filter by provider ID"),
    election_id: int | None = Query(None, description="Filter by election ID"),
    method_id: int | None = Query(None, description="Filter by method ID"),
    date_from: date | None = Query(None, description="Publish date >= this date"),
    date_to: date | None = Query(None, description="Publish date <= this date"),
    include_results: bool = Query(True, description="Include party result rows"),
):
    """List cleaned polls with pagination and filters."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must be before or equal to date_to")

    query = db.query(Poll).options(
        joinedload(Poll.institute),
        joinedload(Poll.provider),
        joinedload(Poll.election),
        joinedload(Poll.method),
        joinedload(Poll.results).joinedload(PollResult.party),
    )

    if scope:
        query = query.filter(Poll.scope == scope)
    if institute_id is not None:
        query = query.filter(Poll.institute_id == institute_id)
    if provider_id is not None:
        query = query.filter(Poll.provider_id == provider_id)
    if election_id is not None:
        query = query.filter(Poll.election_id == election_id)
    if method_id is not None:
        query = query.filter(Poll.method_id == method_id)
    if date_from is not None:
        query = query.filter(Poll.publish_date >= date_from)
    if date_to is not None:
        query = query.filter(Poll.publish_date <= date_to)

    total = query.count()
    rows = (
        query.order_by(Poll.publish_date.desc(), Poll.id.desc()).offset(offset).limit(limit).all()
    )

    return PollListResponse(
        items=[_serialize_poll(row, include_results=include_results) for row in rows],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get("/latest/", response_model=PollListResponse)
def list_latest_polls(
    db: Session = Depends(get_db),
    scope: str | None = Query(None, description="Filter by scope (e.g. federal, bayern)"),
    provider_id: int | None = Query(None, description="Filter by provider ID"),
    election_id: int | None = Query(None, description="Filter by election ID"),
    institute_id: int | None = Query(None, description="Filter by institute ID"),
    include_results: bool = Query(True, description="Include party result rows"),
):
    """List latest 100 cleaned polls with optional filters."""
    query = db.query(Poll).options(
        joinedload(Poll.institute),
        joinedload(Poll.provider),
        joinedload(Poll.election),
        joinedload(Poll.method),
        joinedload(Poll.results).joinedload(PollResult.party),
    )

    if scope:
        query = query.filter(Poll.scope == scope)
    if provider_id is not None:
        query = query.filter(Poll.provider_id == provider_id)
    if election_id is not None:
        query = query.filter(Poll.election_id == election_id)
    if institute_id is not None:
        query = query.filter(Poll.institute_id == institute_id)

    total = query.count()
    rows = query.order_by(Poll.publish_date.desc(), Poll.id.desc()).limit(100).all()

    return PollListResponse(
        items=[_serialize_poll(row, include_results=include_results) for row in rows],
        meta=PaginationMeta(total=total, limit=100, offset=0),
    )


@router.get("/{poll_id}", response_model=PollItem)
def get_poll(poll_id: int, db: Session = Depends(get_db), include_results: bool = True):
    """Get one cleaned poll by ID."""
    poll = (
        db.query(Poll)
        .options(
            joinedload(Poll.institute),
            joinedload(Poll.provider),
            joinedload(Poll.election),
            joinedload(Poll.method),
            joinedload(Poll.results).joinedload(PollResult.party),
        )
        .filter(Poll.id == poll_id)
        .first()
    )

    if not poll:
        raise HTTPException(status_code=404, detail=f"Poll {poll_id} not found")

    return _serialize_poll(poll, include_results=include_results)


@router.get("/{poll_id}/results", response_model=list[PollResultItem])
def get_poll_results(poll_id: int, db: Session = Depends(get_db)):
    """Get party results for a single poll."""
    poll = (
        db.query(Poll)
        .options(joinedload(Poll.results).joinedload(PollResult.party))
        .filter(Poll.id == poll_id)
        .first()
    )
    if not poll:
        raise HTTPException(status_code=404, detail=f"Poll {poll_id} not found")

    return [_serialize_poll_result(r) for r in poll.results]


@raw_router.get("", response_model=RawPollListResponse)
def list_raw_polls(
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=1000, description="Max rows to return"),
    offset: int = Query(0, ge=0, description="Rows to skip"),
    source: str | None = Query(None, description="Filter by source"),
    scope: str | None = Query(None, description="Filter by scope"),
    provider: str | None = Query(None, description="Filter by provider name"),
):
    """List raw (unmodified) polls with pagination and filters."""
    query = db.query(RawPoll)

    if source:
        query = query.filter(RawPoll.source == source)
    if scope:
        query = query.filter(RawPoll.scope == scope)
    if provider:
        query = query.filter(RawPoll.provider == provider)

    total = query.count()
    rows = query.order_by(RawPoll.id.desc()).offset(offset).limit(limit).all()

    items = [RawPollItem.model_validate(row, from_attributes=True) for row in rows]
    return RawPollListResponse(
        items=items, meta=PaginationMeta(total=total, limit=limit, offset=offset)
    )


@raw_router.get("/{raw_id}", response_model=RawPollItem)
def get_raw_poll(raw_id: int, db: Session = Depends(get_db)):
    """Get one raw poll row by ID."""
    row = db.query(RawPoll).filter(RawPoll.id == raw_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Raw poll {raw_id} not found")
    return RawPollItem.model_validate(row, from_attributes=True)


@raw_router.get("/latest/100", response_model=list[RawPollItem])
def get_latest_raw_polls(db: Session = Depends(get_db)):
    """Get latest 100 raw rows."""
    rows = db.query(RawPoll).order_by(RawPoll.id.desc()).limit(100).all()
    return [RawPollItem.model_validate(row, from_attributes=True) for row in rows]


class PollResultsItem(BaseModel):
    poll_id: int
    raw_id: int | None = None
    publish_date: date | None = None
    scope: str | None = None
    institute_id: int | None = None
    provider_id: int | None = None
    election_id: int | None = None
    results: list[PollResultItem]


class ResultsListResponse(BaseModel):
    items: list[PollResultsItem]
    meta: PaginationMeta


@results_router.get("", response_model=ResultsListResponse)
def list_results(
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500, description="Max rows to return"),
    offset: int = Query(0, ge=0, description="Rows to skip"),
    scope: str | None = Query(None, description="Filter by scope (e.g. federal, bayern)"),
    institute_id: int | None = Query(None, description="Filter by institute ID"),
    provider_id: int | None = Query(None, description="Filter by provider ID"),
    election_id: int | None = Query(None, description="Filter by election ID"),
    party_id: int | None = Query(None, description="Filter by party ID"),
    date_from: date | None = Query(None, description="Publish date >= this date"),
    date_to: date | None = Query(None, description="Publish date <= this date"),
):
    """List all poll results grouped by poll with filters and pagination."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must be before or equal to date_to")

    # Build query on Poll
    query = db.query(Poll).options(
        joinedload(Poll.institute),
        joinedload(Poll.provider),
        joinedload(Poll.election),
        joinedload(Poll.results).joinedload(PollResult.party),
    )

    # Apply filters
    if scope is not None:
        query = query.filter(Poll.scope == scope)
    if institute_id is not None:
        query = query.filter(Poll.institute_id == institute_id)
    if provider_id is not None:
        query = query.filter(Poll.provider_id == provider_id)
    if election_id is not None:
        query = query.filter(Poll.election_id == election_id)
    if date_from is not None:
        query = query.filter(Poll.publish_date >= date_from)
    if date_to is not None:
        query = query.filter(Poll.publish_date <= date_to)

    # Get total unique polls count
    total = query.count()

    # Get paginated polls
    polls = (
        query.order_by(Poll.publish_date.desc(), Poll.id.desc()).offset(offset).limit(limit).all()
    )

    # Filter party_id in-memory if specified (since it's on PollResult)
    items = []
    for poll in polls:
        results = poll.results
        if party_id is not None:
            results = [r for r in results if r.party_id == party_id]

        # Sort results by party_id
        results = sorted(results, key=lambda r: r.party_id)

        items.append(
            PollResultsItem(
                poll_id=poll.id,
                raw_id=poll.raw_id,
                publish_date=poll.publish_date,
                scope=poll.scope,
                institute_id=poll.institute_id,
                provider_id=poll.provider_id,
                election_id=poll.election_id,
                results=[
                    PollResultItem(
                        party_id=r.party_id,
                        party_short_name=r.party.short_name if r.party else None,
                        party_name=r.party.name if r.party else None,
                        percentage=r.percentage,
                    )
                    for r in results
                ],
            )
        )

    return ResultsListResponse(
        items=items, meta=PaginationMeta(total=total, limit=limit, offset=offset)
    )
