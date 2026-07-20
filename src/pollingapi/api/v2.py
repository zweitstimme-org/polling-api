"""Version 2 API routes with production-facing resource names."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from pollingapi.api import dictionaries, elections
from pollingapi.api.polls import (
    DateFrom,
    DateTo,
    Limit,
    Offset,
    PollItem,
    PollResultItem,
    RawPollItem,
    SmallLimit,
    _apply_order,
    _apply_poll_filters,
    _base_poll_query,
    _normalize_keys,
    _serialize_observation,
    _serialize_poll,
    _serialize_validation,
    _serialize_wide_poll,
    _validate_date_range,
)
from pollingapi.cleaner.transforms.references import normalized_scope
from pollingapi.core import settings
from pollingapi.data_validation import ValidationReportService
from pollingapi.database import get_db
from pollingapi.models import (
    Election,
    Institute,
    Method,
    Party,
    Poll,
    PollResult,
    PollValidation,
    Provider,
    RawPoll,
    Tasker,
)
from pollingapi.schemas import (
    DataValidation,
    ValidationReport,
)
from pollingapi.schemas import (
    Institute as InstituteSchema,
)
from pollingapi.schemas import (
    Method as MethodSchema,
)
from pollingapi.schemas import (
    Party as PartySchema,
)
from pollingapi.schemas import (
    Provider as ProviderSchema,
)
from pollingapi.services.s3 import S3Service

DBSession = Annotated[Session, Depends(get_db)]

router = APIRouter(prefix="/v2")

EXPORT_DIR = settings.export_dir
DATA_DIR = settings.data_dir

DatasetKey = Literal["default", "all-cleaned"]
PollFormat = Literal["nested", "wide"]
SortOrder = Literal[
    "-published_date",
    "published_date",
    "-id",
    "id",
]


class Pagination(BaseModel):
    """Pagination metadata for v2 list responses."""

    limit: int
    offset: int
    total: int
    has_next: bool


class Links(BaseModel):
    """Navigation links for paginated responses."""

    self: str
    next: str | None = None


class ListResponse(BaseModel):
    """Generic v2 list response envelope."""

    data: list[Any]
    pagination: Pagination
    links: Links


class DatasetItem(BaseModel):
    """Named dataset exposed by the API."""

    key: DatasetKey
    name: str
    description: str
    is_default: bool = False
    quality_controlled: bool = False
    status: str


class DownloadAsset(BaseModel):
    """Downloadable exported asset."""

    filename: str
    dataset: str
    format: str
    url: str
    available: bool


class ArchiveItem(BaseModel):
    """Archive metadata."""

    filename: str
    size: int | float
    size_formatted: str
    created_at: str
    download_url: str


class ScopeItem(BaseModel):
    """Canonical polling scope."""

    key: str
    election_key: str
    election_type: str


class CommissionerItem(BaseModel):
    """Poll commissioner/client reference row."""

    id: int
    name: str
    description: str | None = None


DATASETS = [
    DatasetItem(
        key="default",
        name="Default polling dataset",
        description=(
            "Default public polling dataset. Quality-control filtering will be applied here "
            "once the official inclusion rules are finalized."
        ),
        is_default=True,
        quality_controlled=False,
        status="planned_quality_filter",
    ),
    DatasetItem(
        key="all-cleaned",
        name="All cleaned polls",
        description="All normalized polls before future quality-control subsetting.",
        quality_controlled=False,
        status="available",
    ),
]

DOWNLOAD_FILES = {
    "polls.json": ("polls", "json", EXPORT_DIR / "polls.json"),
    "polls.csv": ("polls", "csv", EXPORT_DIR / "polls.csv"),
    "polls.parquet": ("polls", "parquet", EXPORT_DIR / "polls.parquet"),
    "poll-results.json": ("poll-results", "json", EXPORT_DIR / "poll_results.json"),
    "poll-results.csv": ("poll-results", "csv", EXPORT_DIR / "poll_results.csv"),
    "poll-results.parquet": ("poll-results", "parquet", EXPORT_DIR / "poll_results.parquet"),
    "raw-polls.json": ("raw-polls", "json", EXPORT_DIR / "polls_raw.json"),
    "raw-polls.csv": ("raw-polls", "csv", EXPORT_DIR / "polls_raw.csv"),
    "raw-polls.parquet": ("raw-polls", "parquet", EXPORT_DIR / "polls_raw.parquet"),
    "database.sqlite": ("database", "sqlite", DATA_DIR / "polling.db"),
    "metadata.json": ("metadata", "json", EXPORT_DIR / "metadata.json"),
}


def _dataset_or_404(dataset_key: str) -> DatasetKey:
    if dataset_key not in {"default", "all-cleaned"}:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_key} not found")
    return dataset_key  # type: ignore[return-value]


def _order_from_sort(sort: SortOrder):
    return {
        "-published_date": "publish_date_desc",
        "published_date": "publish_date_asc",
        "-id": "id_desc",
        "id": "id_asc",
    }[sort]


def _page_links(request: Request, limit: int, offset: int, total: int) -> Links:
    next_url = None
    if offset + limit < total:
        params = dict(request.query_params)
        params["limit"] = str(limit)
        params["offset"] = str(offset + limit)
        next_url = str(request.url.include_query_params(**params))
    return Links(self=str(request.url), next=next_url)


def _list_response(
    *,
    request: Request,
    data: list[Any],
    total: int,
    limit: int,
    offset: int,
) -> ListResponse:
    return ListResponse(
        data=data,
        pagination=Pagination(
            limit=limit,
            offset=offset,
            total=total,
            has_next=offset + limit < total,
        ),
        links=_page_links(request, limit, offset, total),
    )


def _filtered_poll_query(
    db: Session,
    *,
    scope: list[str] | None,
    institute_key: list[str] | None,
    provider_id: int | None,
    provider_name: str | None,
    election_key: list[str] | None,
    survey_method_key: list[str] | None,
    source: str | None,
    published_from: date | None,
    published_to: date | None,
):
    query = _base_poll_query(db)
    if scope:
        query = query.filter(Poll.scope.in_([normalized_scope(item) for item in scope]))
    return _apply_poll_filters(
        query,
        institute_key=institute_key,
        provider_id=provider_id,
        provider_name=provider_name,
        election_key=election_key,
        method_key=survey_method_key,
        source=source,
        date_from=published_from,
        date_to=published_to,
    )


def _polls_for_dataset(
    db: Session,
    *,
    dataset_key: str,
    scope: list[str] | None,
    institute_key: list[str] | None,
    provider_id: int | None,
    provider_name: str | None,
    election_key: list[str] | None,
    survey_method_key: list[str] | None,
    source: str | None,
    published_from: date | None,
    published_to: date | None,
):
    _dataset_or_404(dataset_key)
    # Future quality-control filtering belongs here for dataset_key == "default".
    return _filtered_poll_query(
        db,
        scope=scope,
        institute_key=institute_key,
        provider_id=provider_id,
        provider_name=provider_name,
        election_key=election_key,
        survey_method_key=survey_method_key,
        source=source,
        published_from=published_from,
        published_to=published_to,
    )


@router.get("/polls", response_model=ListResponse, tags=["polls"])
def list_polls(
    request: Request,
    db: DBSession,
    limit: Limit = 1000,
    offset: Offset = 0,
    scope: Annotated[list[str] | None, Query(description="Scope code(s)")] = None,
    institute_key: Annotated[list[str] | None, Query(description="Institute key(s)")] = None,
    provider_id: Annotated[int | None, Query(description="Provider numeric id")] = None,
    provider_name: Annotated[str | None, Query(description="Provider name")] = None,
    election_key: Annotated[list[str] | None, Query(description="Election key(s)")] = None,
    survey_method_key: Annotated[
        list[str] | None, Query(description="Survey method key(s)")
    ] = None,
    source: Annotated[str | None, Query(description="Source type")] = None,
    published_from: DateFrom = None,
    published_to: DateTo = None,
    include_results: Annotated[bool, Query(description="Include nested party results")] = True,
    sort: SortOrder = "-published_date",
):
    """List default public polls.

    The v2 default dataset is currently all cleaned polls. Future quality-control
    filtering will be applied here once the inclusion rules are finalized.
    """
    return list_dataset_polls(
        dataset_key="default",
        request=request,
        db=db,
        limit=limit,
        offset=offset,
        scope=scope,
        institute_key=institute_key,
        provider_id=provider_id,
        provider_name=provider_name,
        election_key=election_key,
        survey_method_key=survey_method_key,
        source=source,
        published_from=published_from,
        published_to=published_to,
        include_results=include_results,
        format="nested",
        sort=sort,
    )


@router.get("/polls/{poll_id}", response_model=PollItem, tags=["polls"])
def get_poll(
    poll_id: str,
    db: DBSession,
    include_results: Annotated[bool, Query(description="Include nested party results")] = True,
):
    """Get one poll by public id such as C00014337 or by numeric database id."""
    query = _base_poll_query(db)
    if poll_id.upper().startswith("C"):
        query = query.filter(Poll.public_id == poll_id.upper())
    elif poll_id.isdigit():
        query = query.filter(Poll.id == int(poll_id))
    else:
        raise HTTPException(status_code=400, detail="poll_id must be an integer id or C id")

    poll = query.first()
    if not poll:
        raise HTTPException(status_code=404, detail=f"Poll {poll_id} not found")
    return _serialize_poll(poll, include_results=include_results)


@router.get("/polls/{poll_id}/results", response_model=list[PollResultItem], tags=["polls"])
def get_poll_results(poll_id: str, db: DBSession):
    """Get party results for one poll."""
    return get_poll(poll_id, db).results


@router.get(
    "/polls/{poll_id}/validation-report",
    response_model=DataValidation,
    tags=["validation-reports"],
)
def get_poll_validation_report(poll_id: str, db: DBSession):
    """Get persisted validation report for one poll."""
    query = db.query(Poll).options(joinedload(Poll.validation))
    if poll_id.upper().startswith("C"):
        query = query.filter(Poll.public_id == poll_id.upper())
    elif poll_id.isdigit():
        query = query.filter(Poll.id == int(poll_id))
    else:
        raise HTTPException(status_code=400, detail="poll_id must be an integer id or C id")

    poll = query.first()
    if not poll:
        raise HTTPException(status_code=404, detail=f"Poll {poll_id} not found")
    if not poll.validation:
        raise HTTPException(status_code=404, detail="Validation report not found")
    return _serialize_validation(poll.validation)


@router.get("/poll-results", response_model=ListResponse, tags=["poll-results"])
def list_poll_results(
    request: Request,
    db: DBSession,
    limit: Limit = 1000,
    offset: Offset = 0,
    scope: Annotated[list[str] | None, Query(description="Scope code(s)")] = None,
    party_key: Annotated[list[str] | None, Query(description="Party key(s)")] = None,
    institute_key: Annotated[list[str] | None, Query(description="Institute key(s)")] = None,
    election_key: Annotated[list[str] | None, Query(description="Election key(s)")] = None,
    survey_method_key: Annotated[
        list[str] | None, Query(description="Survey method key(s)")
    ] = None,
    published_from: DateFrom = None,
    published_to: DateTo = None,
    sort: SortOrder = "-published_date",
):
    """List default public poll-party result rows in long format."""
    return list_dataset_poll_results(
        dataset_key="default",
        request=request,
        db=db,
        limit=limit,
        offset=offset,
        scope=scope,
        party_key=party_key,
        institute_key=institute_key,
        election_key=election_key,
        survey_method_key=survey_method_key,
        published_from=published_from,
        published_to=published_to,
        sort=sort,
    )


@router.get("/datasets", response_model=list[DatasetItem], tags=["datasets"])
def list_datasets():
    """List named datasets available through v2."""
    return DATASETS


@router.get("/datasets/{dataset_key}", response_model=DatasetItem, tags=["datasets"])
def get_dataset(dataset_key: str):
    """Get metadata for one named dataset."""
    _dataset_or_404(dataset_key)
    return next(item for item in DATASETS if item.key == dataset_key)


@router.get("/datasets/{dataset_key}/polls", response_model=ListResponse, tags=["datasets"])
def list_dataset_polls(
    dataset_key: str,
    request: Request,
    db: DBSession,
    limit: Limit = 1000,
    offset: Offset = 0,
    scope: Annotated[list[str] | None, Query(description="Scope code(s)")] = None,
    institute_key: Annotated[list[str] | None, Query(description="Institute key(s)")] = None,
    provider_id: Annotated[int | None, Query(description="Provider numeric id")] = None,
    provider_name: Annotated[str | None, Query(description="Provider name")] = None,
    election_key: Annotated[list[str] | None, Query(description="Election key(s)")] = None,
    survey_method_key: Annotated[
        list[str] | None, Query(description="Survey method key(s)")
    ] = None,
    source: Annotated[str | None, Query(description="Source type")] = None,
    published_from: DateFrom = None,
    published_to: DateTo = None,
    include_results: Annotated[bool, Query(description="Include nested party results")] = True,
    format: PollFormat = "nested",
    sort: SortOrder = "-published_date",
):
    """List poll records from an explicit dataset."""
    _validate_date_range(published_from, published_to)
    query = _polls_for_dataset(
        db,
        dataset_key=dataset_key,
        scope=scope,
        institute_key=institute_key,
        provider_id=provider_id,
        provider_name=provider_name,
        election_key=election_key,
        survey_method_key=survey_method_key,
        source=source,
        published_from=published_from,
        published_to=published_to,
    )
    total = query.count()
    rows = _apply_order(query, _order_from_sort(sort)).offset(offset).limit(limit).all()
    if format == "wide":
        data = [_serialize_wide_poll(row).model_dump(mode="json") for row in rows]
    else:
        data = [
            _serialize_poll(row, include_results=include_results).model_dump(mode="json")
            for row in rows
        ]
    return _list_response(request=request, data=data, total=total, limit=limit, offset=offset)


@router.get(
    "/datasets/{dataset_key}/poll-results",
    response_model=ListResponse,
    tags=["datasets"],
)
def list_dataset_poll_results(
    dataset_key: str,
    request: Request,
    db: DBSession,
    limit: Limit = 1000,
    offset: Offset = 0,
    scope: Annotated[list[str] | None, Query(description="Scope code(s)")] = None,
    party_key: Annotated[list[str] | None, Query(description="Party key(s)")] = None,
    institute_key: Annotated[list[str] | None, Query(description="Institute key(s)")] = None,
    election_key: Annotated[list[str] | None, Query(description="Election key(s)")] = None,
    survey_method_key: Annotated[
        list[str] | None, Query(description="Survey method key(s)")
    ] = None,
    published_from: DateFrom = None,
    published_to: DateTo = None,
    sort: SortOrder = "-published_date",
):
    """List long-format poll results from an explicit dataset."""
    _validate_date_range(published_from, published_to)
    _dataset_or_404(dataset_key)
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
            joinedload(PollResult.poll).joinedload(Poll.matching_poll),
        )
    )
    if scope:
        query = query.filter(Poll.scope.in_([normalized_scope(item) for item in scope]))
    query = _apply_poll_filters(
        query,
        institute_key=institute_key,
        election_key=election_key,
        method_key=survey_method_key,
        date_from=published_from,
        date_to=published_to,
    )
    if party_key:
        query = query.filter(PollResult.party_key.in_(_normalize_keys(party_key)))

    total = query.count()
    rows = (
        _apply_order(query, _order_from_sort(sort))
        .order_by(PollResult.party_key.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    data = [_serialize_observation(row).model_dump(mode="json") for row in rows]
    return _list_response(request=request, data=data, total=total, limit=limit, offset=offset)


@router.get("/raw-polls", response_model=ListResponse, tags=["raw-polls"])
def list_raw_polls(
    request: Request,
    db: DBSession,
    limit: SmallLimit = 100,
    offset: Offset = 0,
    source: Annotated[str | None, Query(description="Source type")] = None,
    scope: Annotated[str | None, Query(description="Raw source scope")] = None,
    provider: Annotated[str | None, Query(description="Raw provider name")] = None,
    worker: Annotated[str | None, Query(description="Scraper worker name")] = None,
    sort: Literal["-id", "id"] = "-id",
):
    """List raw scraper/import rows for audit and traceability."""
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
    order = RawPoll.id.asc() if sort == "id" else RawPoll.id.desc()
    rows = query.order_by(order).offset(offset).limit(limit).all()
    data = [
        RawPollItem.model_validate(row, from_attributes=True).model_dump(mode="json")
        for row in rows
    ]
    return _list_response(request=request, data=data, total=total, limit=limit, offset=offset)


@router.get("/raw-polls/{raw_poll_id}", response_model=RawPollItem, tags=["raw-polls"])
def get_raw_poll(raw_poll_id: str, db: DBSession):
    """Get one raw row by public id such as R00014382 or by numeric database id."""
    query = db.query(RawPoll)
    if raw_poll_id.upper().startswith("R"):
        query = query.filter(RawPoll.public_id == raw_poll_id.upper())
    elif raw_poll_id.isdigit():
        query = query.filter(RawPoll.id == int(raw_poll_id))
    else:
        raise HTTPException(status_code=400, detail="raw_poll_id must be an integer id or R id")
    row = query.first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Raw poll {raw_poll_id} not found")
    return RawPollItem.model_validate(row, from_attributes=True)


@router.get("/parties", response_model=list[PartySchema], tags=["reference-data"])
def list_parties(db: DBSession):
    """List all parties."""
    return db.query(Party).order_by(Party.key.asc()).all()


@router.get("/institutes", response_model=list[InstituteSchema], tags=["reference-data"])
def list_institutes(db: DBSession):
    """List all institutes."""
    return db.query(Institute).order_by(Institute.key.asc()).all()


@router.get("/providers", response_model=list[ProviderSchema], tags=["reference-data"])
def list_providers(db: DBSession):
    """List all providers."""
    return db.query(Provider).order_by(Provider.id.asc()).all()


@router.get("/survey-methods", response_model=list[MethodSchema], tags=["reference-data"])
def list_survey_methods(db: DBSession):
    """List all survey methods."""
    return db.query(Method).order_by(Method.key.asc()).all()


@router.get("/elections", tags=["elections"])
def list_elections(db: DBSession):
    """List elections with poll counts and latest publish date."""
    return elections.list_election_summaries(db)


@router.get("/elections/{election_key}", tags=["elections"])
def get_election(election_key: str, db: DBSession):
    """Get one election summary by key."""
    return elections.get_election_summary(election_key, db)


@router.get("/scopes", response_model=list[ScopeItem], tags=["reference-data"])
def list_scopes(db: DBSession):
    """List canonical scope codes."""
    rows = db.query(Election).order_by(Election.key.asc()).all()
    return [
        ScopeItem(
            key=row.scope or row.key.lower(),
            election_key=row.key,
            election_type=row.election_type,
        )
        for row in rows
    ]


@router.get("/commissioners", response_model=list[CommissionerItem], tags=["reference-data"])
def list_commissioners(db: DBSession):
    """List poll commissioners/clients."""
    rows = db.query(Tasker).order_by(Tasker.id.asc()).all()
    return [CommissionerItem(id=row.id, name=row.name, description=row.description) for row in rows]


@router.get("/reference-data", tags=["reference-data"])
def list_reference_data(db: DBSession):
    """Get all reference data in one response."""
    return dictionaries.list_all_reference(db)


@router.get(
    "/validation-reports/summary",
    response_model=ValidationReport,
    tags=["validation-reports"],
)
def get_validation_report_summary(
    db: DBSession,
    top: Annotated[int, Query(ge=1, le=20, description="Number of top failures")] = 5,
):
    """Return aggregate validation quality report."""
    return ValidationReportService(db).build_report(top_n=top)


@router.get("/validation-reports", response_model=ListResponse, tags=["validation-reports"])
def list_validation_reports(
    request: Request,
    db: DBSession,
    limit: Limit = 1000,
    offset: Offset = 0,
    valid: Annotated[bool | None, Query(description="Filter by overall validity")] = None,
):
    """List persisted per-poll validation reports."""
    query = db.query(PollValidation).order_by(PollValidation.poll_id.asc())
    if valid is not None:
        query = query.filter(PollValidation.valid == valid)
    total = query.count()
    rows = query.offset(offset).limit(limit).all()
    data = [_serialize_validation(row).model_dump(mode="json") for row in rows]
    return _list_response(request=request, data=data, total=total, limit=limit, offset=offset)


@router.get("/downloads", response_model=list[DownloadAsset], tags=["downloads"])
def list_downloads():
    """List downloadable export assets."""
    return [
        DownloadAsset(
            filename=filename,
            dataset=dataset,
            format=format_name,
            url=f"/v2/downloads/{filename}",
            available=path.exists(),
        )
        for filename, (dataset, format_name, path) in DOWNLOAD_FILES.items()
    ]


@router.get("/downloads/{filename}", tags=["downloads"])
def download_file(filename: str):
    """Download an exported file by filename."""
    asset = DOWNLOAD_FILES.get(filename)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Download {filename} not found")
    _, _, path = asset
    if not path.exists():
        raise HTTPException(
            status_code=404, detail="Export file not found. Run: pollingapi export:all"
        )
    media_type = {
        "json": "application/json",
        "csv": "text/csv",
        "parquet": "application/octet-stream",
        "sqlite": "application/x-sqlite3",
    }.get(asset[1], "application/octet-stream")
    return FileResponse(path=path, filename=filename, media_type=media_type)


def _format_size(size_bytes: int | float) -> str:
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _archive_item(archive) -> ArchiveItem:
    return ArchiveItem(
        filename=archive.filename,
        size=archive.size,
        size_formatted=_format_size(archive.size),
        created_at=archive.created_at.isoformat(),
        download_url=archive.public_url,
    )


@router.get("/archives", response_model=list[ArchiveItem], tags=["archives"])
def list_archives():
    """List available archive snapshots."""
    service = S3Service()
    if not service.is_configured():
        raise HTTPException(status_code=503, detail="Archive service not configured")
    return [_archive_item(archive) for archive in service.list_archives()]


@router.get("/archives/latest", response_model=ArchiveItem, tags=["archives"])
def get_latest_archive():
    """Get latest archive snapshot metadata."""
    service = S3Service()
    if not service.is_configured():
        raise HTTPException(status_code=503, detail="Archive service not configured")
    archives = service.list_archives()
    if not archives:
        raise HTTPException(status_code=404, detail="No archives available")
    return _archive_item(archives[0])


@router.get("/archives/{filename}", response_model=ArchiveItem, tags=["archives"])
def get_archive(filename: str):
    """Get metadata for one archive snapshot."""
    service = S3Service()
    if not service.is_configured():
        raise HTTPException(status_code=503, detail="Archive service not configured")
    archive = service.get_archive(filename)
    if not archive:
        raise HTTPException(status_code=404, detail="Archive not found")
    return _archive_item(archive)


@router.get("/archives/{filename}/download", tags=["archives"])
def download_archive(filename: str):
    """Redirect to one archive snapshot download URL."""
    from fastapi.responses import RedirectResponse

    service = S3Service()
    if not service.is_configured():
        raise HTTPException(status_code=503, detail="Archive service not configured")
    archive = service.get_archive(filename)
    if not archive:
        raise HTTPException(status_code=404, detail="Archive not found")
    return RedirectResponse(url=archive.public_url)
