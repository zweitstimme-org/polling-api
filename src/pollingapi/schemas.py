"""Pydantic schemas for API requests and responses."""

from __future__ import annotations

from datetime import date as DateType
from datetime import datetime as DateTimeType
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict


# Raw Poll Schemas
class RawPollBase(BaseModel):
    """Base schema for raw polls."""

    publish_date: str | None = None
    survey_date_start: str | None = None
    survey_date_end: str | None = None
    respondents: str | None = None
    zeitraum: str | None = None
    parties: str | None = None
    institute_id: str | None = None
    institute_raw: str | None = None
    provider: str | None = None
    tasker: str | None = None
    source: str | None = None
    scope: str | None = None
    election_id: str | None = None
    method_id: str | None = None
    date_downloaded: str | None = None


class RawPollCreate(RawPollBase):
    """Schema for creating raw polls."""

    pass


class RawPoll(RawPollBase):
    """Schema for raw poll responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int


# Poll Result Schemas
class PollResultBase(BaseModel):
    """Base schema for poll results."""

    party_id: int
    percentage: float


class PollResultCreate(PollResultBase):
    """Schema for creating poll results."""

    pass


class PollResult(PollResultBase):
    """Schema for poll result responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    poll_id: int
    party_name: str | None = None


# Poll Schemas
class PollBase(BaseModel):
    """Base schema for polls."""

    publish_date: DateType | None = None
    survey_date_start: DateType | None = None
    survey_date_end: DateType | None = None
    respondents: int | None = None
    source: str | None = None
    scope: str | None = None


class PollCreate(PollBase):
    """Schema for creating polls."""

    raw_id: int | None = None
    institute_id: int | None = None
    provider_id: int | None = None
    election_id: int | None = None
    method_id: int | None = None
    date_downloaded: DateTimeType | None = None
    results: List[PollResultCreate] = []


class Poll(PollBase):
    """Schema for poll responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    institute: str | None = None
    provider: str | None = None
    election: str | None = None
    method: str | None = None
    results: List[PollResult] = []


# Dictionary Schemas
class InstituteBase(BaseModel):
    """Base schema for institutes."""

    name: str
    description: str | None = None


class InstituteCreate(InstituteBase):
    """Schema for creating institutes."""

    pass


class Institute(InstituteBase):
    """Schema for institute responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int


class PartyBase(BaseModel):
    """Base schema for parties."""

    name: str
    short_name: str | None = None
    color: str | None = None


class PartyCreate(PartyBase):
    """Schema for creating parties."""

    pass


class Party(PartyBase):
    """Schema for party responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int


class ProviderBase(BaseModel):
    """Base schema for providers."""

    name: str
    description: str | None = None


class ProviderCreate(ProviderBase):
    """Schema for creating providers."""

    pass


class Provider(ProviderBase):
    """Schema for provider responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int


class ElectionBase(BaseModel):
    """Base schema for elections."""

    election_type: str
    year: int | None = None
    scope: str | None = None
    date: DateType | None = None


class ElectionCreate(ElectionBase):
    """Schema for creating elections."""

    pass


class Election(ElectionBase):
    """Schema for election responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int


class MethodBase(BaseModel):
    """Base schema for methods."""

    name: str
    description: str | None = None


class MethodCreate(MethodBase):
    """Schema for creating methods."""

    pass


class Method(MethodBase):
    """Schema for method responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int


# Export Schemas
class ExportData(BaseModel):
    """Schema for exported data."""

    polls: List[Poll]
    metadata: Dict[str, Any]


# Scraper Schemas
class ScraperPayload(BaseModel):
    """Schema for scraper payload validation."""

    model_config = ConfigDict(extra="ignore")

    publish_date: str | None = None
    respondents: str | None = None
    zeitraum: str | None = None
    survey_date_start: str | None = None
    survey_date_end: str | None = None
    parties: Dict[str, float] | None = None
    institute_id: str | None = None
    provider: str | None = None
    tasker: str | None = None
    source: str | None = None
    scope: str | None = None
    election_id: str | None = None
    method_id: str | None = None
    date_downloaded: str | None = None


# Health Check
class HealthCheck(BaseModel):
    """Health check response schema."""

    status: str
    version: str
    timestamp: DateTimeType
