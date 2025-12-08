from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class RawPollBase(BaseModel):
    publish_date: Optional[str] = None
    respondents: Optional[str] = None
    Zeitraum: Optional[str] = None
    survey_date_start: Optional[str] = None
    survey_date_end: Optional[str] = None
    parties: Optional[str] = None
    institute_id: Optional[str] = None
    provider: Optional[str] = None
    tasker: Optional[str] = None
    source: Optional[str] = None
    scope: Optional[str] = None
    election_id: Optional[str] = None
    method_id: Optional[str] = None
    date_downloaded: Optional[str] = None


class RawPoll(RawPollBase):
    id: int
    inserted_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class RawPollIn(RawPollBase):
    source: str


class RawPollBatchIn(BaseModel):
    polls: List[RawPollIn]


class PollResultBase(BaseModel):
    poll_id: int
    party_id: int
    percentage: float
    raw_id: Optional[int] = None


class PollResult(PollResultBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class PollBase(BaseModel):
    raw_id: Optional[int] = None
    publish_date: Optional[date] = None
    survey_date_start: Optional[date] = None
    survey_date_end: Optional[date] = None
    respondents: Optional[int] = None
    scope: Optional[str] = None
    institute_id: Optional[int] = None
    provider_id: Optional[int] = None
    election_id: Optional[int] = None
    method_id: Optional[int] = None


class Poll(PollBase):
    id: int
    date_cleaned: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class InstituteBase(BaseModel):
    name: str
    abbreviation: Optional[str] = None


class Institute(InstituteBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class PartyBase(BaseModel):
    name: str
    abbreviation: str
    color: Optional[str] = None


class Party(PartyBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ProviderBase(BaseModel):
    name: str
    url: Optional[str] = None


class Provider(ProviderBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class TaskerBase(BaseModel):
    name: str


class Tasker(TaskerBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class ElectionBase(BaseModel):
    type: str
    year: int
    state: Optional[str] = None


class Election(ElectionBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class MethodBase(BaseModel):
    name: str
    description: Optional[str] = None


class Method(MethodBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class DatabaseDumpResponse(BaseModel):
    filename: str
    size_bytes: int
    record_count: int
    generated_at: datetime
    description: str


class IngestResult(BaseModel):
    inserted: int
    record_ids: List[int]
