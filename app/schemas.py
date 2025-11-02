from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel


class ForecastBase(BaseModel):
    publish_date: Optional[str] = None
    Befragte: Optional[str] = None
    Zeitraum: Optional[str] = None
    survey_date_start: Optional[str] = None
    survey_date_end: Optional[str] = None
    parties: Optional[str] = None
    institute_id: Optional[str] = None
    forecast_provider: Optional[str] = None
    source: Optional[str] = None
    scope: Optional[str] = None
    election_id: Optional[str] = None
    method_id: Optional[str] = None
    date_downloaded: Optional[str] = None
    content_hash: Optional[str] = None


class Forecast(ForecastBase):
    id: int

    class Config:
        from_attributes = True


class RawPoll(Forecast):
    inserted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DatabaseDumpResponse(BaseModel):
    filename: str
    size_bytes: int
    record_count: int
    generated_at: datetime
    description: str


class RawPollIn(BaseModel):
    publish_date: Optional[str] = None
    Befragte: Optional[str] = None
    Zeitraum: Optional[str] = None
    survey_date_start: Optional[str] = None
    survey_date_end: Optional[str] = None
    parties: Optional[Any] = None
    institute_id: Optional[str] = None
    forecast_provider: Optional[str] = None
    source: str
    scope: Optional[str] = None
    election_id: Optional[str] = None
    method_id: Optional[str] = None
    date_downloaded: Optional[str] = None


class RawPollBatchIn(BaseModel):
    polls: List[RawPollIn]


class IngestResult(BaseModel):
    inserted: int
    record_ids: List[int]
