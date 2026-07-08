"""Schemas and result types for file imports."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class RawPollImport(BaseModel):
    """Importer-facing representation of one row destined for polls_raw."""

    model_config = ConfigDict(populate_by_name=True)

    publish_date: str | None = None
    survey_date_start: str | None = None
    survey_date_end: str | None = None
    respondents: str | None = None
    zeitraum: str | None = Field(default=None, alias="Zeitraum")
    parties: dict[str, str] | str
    institute_id: str | None = None
    provider: str | None = None
    tasker: str | None = None
    source: str | None = "csv_import"
    scope: str | None = None
    election_id: str | None = None
    method_id: str | None = "99"
    worker: str | None = None
    survey_type: str | None = None
    date_downloaded: str | None = None
    pipeline_run_id: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _normalize_blank_strings(cls, value: Any) -> Any:
        return _blank_to_none(value)

    def to_raw_dict(self) -> dict[str, Any]:
        """Return a dict suitable for constructing a RawPoll."""
        data = self.model_dump(by_alias=False)
        parties = data["parties"]
        if isinstance(parties, dict):
            parties = {key: str(value) for key, value in parties.items() if str(value).strip()}
            data["parties"] = json.dumps(parties, sort_keys=True)

        if not data.get("date_downloaded"):
            data["date_downloaded"] = datetime.now().isoformat()

        return data


@dataclass
class ImportStats:
    """High-level import counters."""

    parsed: int = 0
    inserted: int = 0
    skipped: int = 0
    errors: int = 0
    error_messages: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    """Result of an import run."""

    source: str
    path: str
    stats: ImportStats
    cleaning_stats: dict[str, int] | None = None
