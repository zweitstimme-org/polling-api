"""Scraper schemas and data models."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PollPayload(BaseModel):
    """Schema for poll data payload from scrapers."""

    model_config = ConfigDict(extra="ignore")

    publish_date: str | None = None
    respondents: str | None = None
    Befragte: str | None = Field(None, alias="Befragte")
    zeitraum: str | None = Field(None, alias="Zeitraum")
    survey_date_start: str | None = None
    survey_date_end: str | None = None
    parties: dict[str, float] | None = None
    institute_id: str | None = None
    provider: str | None = None
    tasker: str | None = None
    source: str | None = None
    scope: str | None = None
    election_id: str | None = None
    method_id: str | None = None
    date_downloaded: str | None = None

    @field_validator("respondents", "Befragte", mode="before")
    @classmethod
    def limit_respondents_length(cls, v):
        """Limit respondents field to 40 characters."""
        if v and len(str(v)) > 40:
            return None
        return v


# Allowed columns derived from PollPayload model
ALLOWED_POLL_COLUMNS = tuple(PollPayload.model_fields.keys())


def filter_poll_payloads(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter and validate poll payload records.

    Args:
        records: List of record dictionaries

    Returns:
        List of validated records with None values excluded
    """
    validated = []
    for record in records:
        try:
            payload = PollPayload(**record)
            # Convert to dict and remove None values
            record_dict = payload.model_dump(exclude_none=True)
            validated.append(record_dict)
        except Exception:
            # Skip invalid records
            continue
    return validated
