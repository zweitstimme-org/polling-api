"""Generic CSV import source."""

import json
from pathlib import Path
from typing import Any

from pollingapi.importer.formats.csv import read_csv_rows
from pollingapi.importer.schemas import RawPollImport
from pollingapi.importer.sources.base import ImportSource

FIELD_ALIASES = {
    "publish_date": ("publish_date", "datum", "date", "published_at"),
    "survey_date_start": ("survey_date_start", "survey_start", "start_date"),
    "survey_date_end": ("survey_date_end", "survey_end", "end_date"),
    "respondents": ("respondents", "befragte", "sample_size"),
    "zeitraum": ("zeitraum", "timeframe", "survey_period"),
    "institute_id": ("institute_id", "institut", "institute"),
    "provider": ("provider", "data_source", "source_provider"),
    "tasker": ("tasker", "auftraggeber", "commissioner"),
    "source": ("source",),
    "scope": ("scope", "state", "land"),
    "election_id": ("election_id", "election", "election_type"),
    "method_id": ("method_id", "method", "survey_method"),
    "worker": ("worker",),
    "survey_type": ("survey_type",),
    "date_downloaded": ("date_downloaded", "scraped_at", "imported_at"),
    "pipeline_run_id": ("pipeline_run_id",),
}

PARTIES_COLUMNS = ("parties", "results")
RESERVED_COLUMNS = {alias for aliases in FIELD_ALIASES.values() for alias in aliases}
RESERVED_COLUMNS.update(PARTIES_COLUMNS)


class CsvImportSource(ImportSource):
    """Import CSV files with raw-poll-like columns and party result columns."""

    name = "csv"

    def load(self, path: Path) -> list[RawPollImport]:
        return [self._row_to_import(row) for row in read_csv_rows(path)]

    def _row_to_import(self, row: dict[str, str]) -> RawPollImport:
        normalized_row = {key.strip().lower(): value for key, value in row.items()}
        data: dict[str, Any] = {
            field: self._first_value(normalized_row, aliases)
            for field, aliases in FIELD_ALIASES.items()
        }
        data["source"] = data.get("source") or "csv_import"
        data["method_id"] = data.get("method_id") or "99"
        data["worker"] = data.get("worker") or f"import:{self.name}"
        data["parties"] = self._extract_parties(row)
        return RawPollImport.model_validate(data)

    @staticmethod
    def _first_value(row: dict[str, str], aliases: tuple[str, ...]) -> str | None:
        for alias in aliases:
            value = row.get(alias)
            if value:
                return value
        return None

    @staticmethod
    def _extract_parties(row: dict[str, str]) -> dict[str, str]:
        normalized_row = {key.strip().lower(): value for key, value in row.items()}
        for column in PARTIES_COLUMNS:
            value = normalized_row.get(column)
            if not value:
                continue
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise ValueError(f"{column} must contain a JSON object")
            return {str(key): str(result) for key, result in parsed.items()}

        parties = {
            key: value
            for key, value in row.items()
            if key.strip().lower() not in RESERVED_COLUMNS and value
        }
        if not parties:
            raise ValueError("CSV row does not contain party result columns")
        return parties
