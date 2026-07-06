"""Research-oriented poll data API routes."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from pollingapi.cleaner.transforms.references import normalized_scope
from pollingapi.database import get_db
from pollingapi.models import Poll, PollResult, Provider, RawPoll

DBSession = Annotated[Session, Depends(get_db)]

Limit = Annotated[int, Query(ge=1, le=10000, description="Maximum rows to return")]
SmallLimit = Annotated[int, Query(ge=1, le=1000, description="Maximum rows to return")]
Offset = Annotated[int, Query(ge=0, description="Rows to skip")]
DateFrom = Annotated[date | None, Query(description="Publish date on or after this date")]
DateTo = Annotated[date | None, Query(description="Publish date on or before this date")]
Order = Annotated[
    Literal["publish_date_desc", "publish_date_asc", "id_desc", "id_asc"],
    Query(description="Sort order"),
]

polls_router = APIRouter(prefix="/polls", tags=["polls"])
raw_router = APIRouter(prefix="/raw-polls", tags=["raw-polls"])
observations_router = APIRouter(prefix="/observations", tags=["observations"])
results_router = APIRouter(prefix="/results", tags=["observations"])

# Backward-compatible name used by main.py.
router = polls_router


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    total: int
    limit: int
    offset: int


class PollResultItem(BaseModel):
    """One party result inside a cleaned poll."""

    party_key: str
    party_short_name: str | None = None
    party_name: str | None = None
    percentage: float


class PollItem(BaseModel):
    """Cleaned poll with nested party results."""

    id: int
    public_id: str | None = None
    raw_id: int | None = None
    raw_public_id: str | None = None
    publish_date: date | None = None
    survey_date_start: date | None = None
    survey_date_end: date | None = None
    respondents: int | None = None
    scope: str | None = None
    source: str | None = None
    institute_key: str | None = None
    institute_name: str | None = None
    provider_id: int | None = None
    provider_name: str | None = None
    election_key: str | None = None
    election_type: str | None = None
    method_key: str | None = None
    method_name: str | None = None
    fingerprint: str | None = None
    date_downloaded: str | None = None
    results: list[PollResultItem] = Field(default_factory=list)


class PollListResponse(BaseModel):
    """Paginated cleaned poll response."""

    items: list[PollItem]
    meta: PaginationMeta


class ObservationItem(BaseModel):
    """Flat long-format row: one poll, one party, one percentage."""

    poll_id: int
    poll_public_id: str | None = None
    raw_id: int | None = None
    raw_public_id: str | None = None
    publish_date: date | None = None
    survey_date_start: date | None = None
    survey_date_end: date | None = None
    respondents: int | None = None
    scope: str | None = None
    source: str | None = None
    institute_key: str | None = None
    institute_name: str | None = None
    provider_id: int | None = None
    provider_name: str | None = None
    election_key: str | None = None
    election_type: str | None = None
    method_key: str | None = None
    method_name: str | None = None
    party_key: str
    party_short_name: str | None = None
    party_name: str | None = None
    percentage: float


class ObservationListResponse(BaseModel):
    """Paginated flat observation response."""

    items: list[ObservationItem]
    meta: PaginationMeta


class WidePollItem(BaseModel):
    """Cleaned poll with party percentages as a dictionary keyed by party_key."""

    id: int
    public_id: str | None = None
    raw_public_id: str | None = None
    publish_date: date | None = None
    survey_date_start: date | None = None
    survey_date_end: date | None = None
    respondents: int | None = None
    scope: str | None = None
    source: str | None = None
    institute_key: str | None = None
    institute_name: str | None = None
    provider_name: str | None = None
    election_key: str | None = None
    election_type: str | None = None
    method_key: str | None = None
    method_name: str | None = None
    results: dict[str, float] = Field(default_factory=dict)


class WidePollListResponse(BaseModel):
    """Paginated wide poll response."""

    items: list[WidePollItem]
    meta: PaginationMeta


class RawPollItem(BaseModel):
    """Immutable raw scraper/API row."""

    id: int
    public_id: str | None = None
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
    worker: str | None = None
    survey_type: str | None = None
    duplicate_of_poll_id: int | None = None
    pipeline_run_id: str | None = None
    date_downloaded: str | None = None


class RawPollListResponse(BaseModel):
    """Paginated raw poll response."""

    items: list[RawPollItem]
    meta: PaginationMeta


def _validate_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must be before or equal to date_to")


def _normalize_keys(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    return [value.strip().upper() for value in values if value.strip()]


def _base_poll_query(db: Session):
    return db.query(Poll).options(
        joinedload(Poll.raw_poll),
        joinedload(Poll.institute),
        joinedload(Poll.provider),
        joinedload(Poll.election),
        joinedload(Poll.method),
        joinedload(Poll.results).joinedload(PollResult.party),
    )


def _apply_poll_filters(
    query,
    *,
    scope: str | None = None,
    institute_key: list[str] | None = None,
    provider_id: int | None = None,
    provider_name: str | None = None,
    election_key: list[str] | None = None,
    method_key: list[str] | None = None,
    source: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    if scope:
        query = query.filter(Poll.scope == normalized_scope(scope))
    if institute_key:
        query = query.filter(Poll.institute_key.in_(_normalize_keys(institute_key)))
    if provider_id is not None:
        query = query.filter(Poll.provider_id == provider_id)
    if provider_name:
        query = query.filter(Poll.provider.has(func.lower(Provider.name) == provider_name.lower()))
    if election_key:
        query = query.filter(Poll.election_key.in_(_normalize_keys(election_key)))
    if method_key:
        query = query.filter(Poll.method_key.in_(_normalize_keys(method_key)))
    if source:
        query = query.filter(Poll.source == source)
    if date_from:
        query = query.filter(Poll.publish_date >= date_from)
    if date_to:
        query = query.filter(Poll.publish_date <= date_to)
    return query


def _apply_order(query, order: str):
    if order == "publish_date_asc":
        return query.order_by(Poll.publish_date.asc(), Poll.id.asc())
    if order == "id_asc":
        return query.order_by(Poll.id.asc())
    if order == "id_desc":
        return query.order_by(Poll.id.desc())
    return query.order_by(Poll.publish_date.desc(), Poll.id.desc())


def _serialize_poll_result(result: PollResult) -> PollResultItem:
    party = result.party
    return PollResultItem(
        party_key=result.party_key,
        party_short_name=party.short_name if party else None,
        party_name=party.name if party else None,
        percentage=result.percentage,
    )


def _serialize_poll(poll: Poll, include_results: bool) -> PollItem:
    return PollItem(
        id=poll.id,
        public_id=poll.public_id,
        raw_id=poll.raw_id,
        raw_public_id=poll.raw_poll.public_id if poll.raw_poll else None,
        publish_date=poll.publish_date,
        survey_date_start=poll.survey_date_start,
        survey_date_end=poll.survey_date_end,
        respondents=poll.respondents,
        scope=poll.scope,
        source=poll.source,
        institute_key=poll.institute_key,
        institute_name=poll.institute.name if poll.institute else None,
        provider_id=poll.provider_id,
        provider_name=poll.provider.name if poll.provider else None,
        election_key=poll.election_key,
        election_type=poll.election.election_type if poll.election else None,
        method_key=poll.method_key,
        method_name=poll.method.name if poll.method else None,
        date_downloaded=poll.date_downloaded.isoformat() if poll.date_downloaded else None,
        results=[_serialize_poll_result(r) for r in poll.results] if include_results else [],
    )


def _serialize_observation(result: PollResult) -> ObservationItem:
    poll = result.poll
    party = result.party
    return ObservationItem(
        poll_id=poll.id,
        poll_public_id=poll.public_id,
        raw_id=poll.raw_id,
        raw_public_id=poll.raw_poll.public_id if poll.raw_poll else None,
        publish_date=poll.publish_date,
        survey_date_start=poll.survey_date_start,
        survey_date_end=poll.survey_date_end,
        respondents=poll.respondents,
        scope=poll.scope,
        source=poll.source,
        institute_key=poll.institute_key,
        institute_name=poll.institute.name if poll.institute else None,
        provider_id=poll.provider_id,
        provider_name=poll.provider.name if poll.provider else None,
        election_key=poll.election_key,
        election_type=poll.election.election_type if poll.election else None,
        method_key=poll.method_key,
        method_name=poll.method.name if poll.method else None,
        party_key=result.party_key,
        party_short_name=party.short_name if party else None,
        party_name=party.name if party else None,
        percentage=result.percentage,
    )


def _serialize_wide_poll(poll: Poll) -> WidePollItem:
    return WidePollItem(
        id=poll.id,
        public_id=poll.public_id,
        raw_public_id=poll.raw_poll.public_id if poll.raw_poll else None,
        publish_date=poll.publish_date,
        survey_date_start=poll.survey_date_start,
        survey_date_end=poll.survey_date_end,
        respondents=poll.respondents,
        scope=poll.scope,
        source=poll.source,
        institute_key=poll.institute_key,
        institute_name=poll.institute.name if poll.institute else None,
        provider_name=poll.provider.name if poll.provider else None,
        election_key=poll.election_key,
        election_type=poll.election.election_type if poll.election else None,
        method_key=poll.method_key,
        method_name=poll.method.name if poll.method else None,
        results={result.party_key: result.percentage for result in poll.results},
    )


@polls_router.get("", response_model=PollListResponse)
def list_polls(
    db: DBSession,
    limit: Limit = 1000,
    offset: Offset = 0,
    scope: Annotated[str | None, Query(description="Scope code, e.g. federal, by, ost")] = None,
    institute_key: Annotated[list[str] | None, Query(description="Institute key(s)")] = None,
    provider_id: Annotated[int | None, Query(description="Provider numeric id")] = None,
    provider_name: Annotated[str | None, Query(description="Provider name")] = None,
    election_key: Annotated[list[str] | None, Query(description="Election key(s)")] = None,
    method_key: Annotated[list[str] | None, Query(description="Survey method key(s)")] = None,
    source: Annotated[str | None, Query(description="Source type, e.g. api/html_scraper")] = None,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    include_results: Annotated[bool, Query(description="Include nested party results")] = True,
    order: Order = "publish_date_desc",
):
    """List cleaned polls with normalized metadata and optional nested results."""
    _validate_date_range(date_from, date_to)
    query = _apply_poll_filters(
        _base_poll_query(db),
        scope=scope,
        institute_key=institute_key,
        provider_id=provider_id,
        provider_name=provider_name,
        election_key=election_key,
        method_key=method_key,
        source=source,
        date_from=date_from,
        date_to=date_to,
    )
    total = query.count()
    rows = _apply_order(query, order).offset(offset).limit(limit).all()
    return PollListResponse(
        items=[_serialize_poll(row, include_results=include_results) for row in rows],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@polls_router.get("/wide", response_model=WidePollListResponse)
def list_polls_wide(
    db: DBSession,
    limit: Limit = 1000,
    offset: Offset = 0,
    scope: Annotated[str | None, Query(description="Scope code, e.g. federal, by, ost")] = None,
    institute_key: Annotated[list[str] | None, Query(description="Institute key(s)")] = None,
    election_key: Annotated[list[str] | None, Query(description="Election key(s)")] = None,
    method_key: Annotated[list[str] | None, Query(description="Survey method key(s)")] = None,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    order: Order = "publish_date_desc",
):
    """List cleaned polls in wide format, with party percentages in a results dictionary."""
    _validate_date_range(date_from, date_to)
    query = _apply_poll_filters(
        _base_poll_query(db),
        scope=scope,
        institute_key=institute_key,
        election_key=election_key,
        method_key=method_key,
        date_from=date_from,
        date_to=date_to,
    )
    total = query.count()
    rows = _apply_order(query, order).offset(offset).limit(limit).all()
    return WidePollListResponse(
        items=[_serialize_wide_poll(row) for row in rows],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@polls_router.get("/latest", response_model=PollListResponse)
def list_latest_polls(
    db: DBSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    scope: Annotated[str | None, Query(description="Scope code, e.g. federal, by, ost")] = None,
    include_results: Annotated[bool, Query(description="Include nested party results")] = True,
):
    """List latest cleaned polls, optimized for app/backend use."""
    query = _apply_poll_filters(_base_poll_query(db), scope=scope)
    total = query.count()
    rows = query.order_by(Poll.publish_date.desc(), Poll.id.desc()).limit(limit).all()
    return PollListResponse(
        items=[_serialize_poll(row, include_results=include_results) for row in rows],
        meta=PaginationMeta(total=total, limit=limit, offset=0),
    )


@polls_router.get("/{poll_identifier}", response_model=PollItem)
def get_poll(
    poll_identifier: str,
    db: DBSession,
    include_results: Annotated[bool, Query(description="Include nested party results")] = True,
):
    """Get one cleaned poll by integer id or public id such as C00004887."""
    query = _base_poll_query(db)
    if poll_identifier.upper().startswith("C"):
        query = query.filter(Poll.public_id == poll_identifier.upper())
    elif poll_identifier.isdigit():
        query = query.filter(Poll.id == int(poll_identifier))
    else:
        raise HTTPException(status_code=400, detail="poll_identifier must be an integer id or C id")

    poll = query.first()
    if not poll:
        raise HTTPException(status_code=404, detail=f"Poll {poll_identifier} not found")
    return _serialize_poll(poll, include_results=include_results)


@polls_router.get("/{poll_identifier}/results", response_model=list[PollResultItem])
def get_poll_results(poll_identifier: str, db: DBSession):
    """Get party results for a single cleaned poll."""
    return get_poll(poll_identifier, db).results


@observations_router.get("", response_model=ObservationListResponse)
def list_observations(
    db: DBSession,
    limit: Limit = 1000,
    offset: Offset = 0,
    scope: Annotated[str | None, Query(description="Scope code, e.g. federal, by, ost")] = None,
    party_key: Annotated[list[str] | None, Query(description="Party key(s)")] = None,
    institute_key: Annotated[list[str] | None, Query(description="Institute key(s)")] = None,
    election_key: Annotated[list[str] | None, Query(description="Election key(s)")] = None,
    method_key: Annotated[list[str] | None, Query(description="Survey method key(s)")] = None,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    order: Order = "publish_date_desc",
):
    """List long-format observations for statistical analysis.

    Each row is one party result in one poll. This is usually the most convenient
    endpoint for R, Python/pandas, Stata, and similar workflows.
    """
    _validate_date_range(date_from, date_to)
    query = (
        db.query(PollResult)
        .join(Poll)
        .options(
            joinedload(PollResult.party),
            joinedload(PollResult.poll).joinedload(Poll.raw_poll),
            joinedload(PollResult.poll).joinedload(Poll.institute),
            joinedload(PollResult.poll).joinedload(Poll.provider),
            joinedload(PollResult.poll).joinedload(Poll.election),
            joinedload(PollResult.poll).joinedload(Poll.method),
        )
    )
    query = _apply_poll_filters(
        query,
        scope=scope,
        institute_key=institute_key,
        election_key=election_key,
        method_key=method_key,
        date_from=date_from,
        date_to=date_to,
    )
    if party_key:
        query = query.filter(PollResult.party_key.in_(_normalize_keys(party_key)))

    total = query.count()
    query = _apply_order(query, order).order_by(PollResult.party_key.asc())
    rows = query.offset(offset).limit(limit).all()
    return ObservationListResponse(
        items=[_serialize_observation(row) for row in rows],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@results_router.get("", response_model=ObservationListResponse)
def list_results(
    db: DBSession,
    limit: Limit = 1000,
    offset: Offset = 0,
    scope: Annotated[str | None, Query(description="Scope code, e.g. federal, by, ost")] = None,
    party_key: Annotated[list[str] | None, Query(description="Party key(s)")] = None,
    date_from: DateFrom = None,
    date_to: DateTo = None,
):
    """Backward-compatible alias for long-format observations."""
    return list_observations(
        db=db,
        limit=limit,
        offset=offset,
        scope=scope,
        party_key=party_key,
        date_from=date_from,
        date_to=date_to,
    )


@raw_router.get("", response_model=RawPollListResponse)
def list_raw_polls(
    db: DBSession,
    limit: SmallLimit = 100,
    offset: Offset = 0,
    source: Annotated[str | None, Query(description="Source type")] = None,
    scope: Annotated[str | None, Query(description="Raw source scope")] = None,
    provider: Annotated[str | None, Query(description="Raw provider name")] = None,
    worker: Annotated[str | None, Query(description="Scraper worker name")] = None,
):
    """List immutable raw source rows for audit and traceability."""
    query = db.query(RawPoll)
    if source:
        query = query.filter(RawPoll.source == source)
    if scope:
        query = query.filter(RawPoll.scope == scope)
    if provider:
        query = query.filter(RawPoll.provider == provider)
    if worker:
        query = query.filter(RawPoll.worker == worker)

    total = query.count()
    rows = query.order_by(RawPoll.id.desc()).offset(offset).limit(limit).all()
    return RawPollListResponse(
        items=[RawPollItem.model_validate(row, from_attributes=True) for row in rows],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@raw_router.get("/latest/100", response_model=list[RawPollItem], include_in_schema=False)
def get_latest_raw_polls(db: DBSession):
    """Backward-compatible latest raw rows endpoint."""
    rows = db.query(RawPoll).order_by(RawPoll.id.desc()).limit(100).all()
    return [RawPollItem.model_validate(row, from_attributes=True) for row in rows]


@raw_router.get("/{raw_identifier}", response_model=RawPollItem)
def get_raw_poll(raw_identifier: str, db: DBSession):
    """Get one raw row by integer id or public id such as R00004891."""
    query = db.query(RawPoll)
    if raw_identifier.upper().startswith("R"):
        query = query.filter(RawPoll.public_id == raw_identifier.upper())
    elif raw_identifier.isdigit():
        query = query.filter(RawPoll.id == int(raw_identifier))
    else:
        raise HTTPException(status_code=400, detail="raw_identifier must be an integer id or R id")
    row = query.first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Raw poll {raw_identifier} not found")
    return RawPollItem.model_validate(row, from_attributes=True)
