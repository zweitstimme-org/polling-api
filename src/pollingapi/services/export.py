"""Export service for self-contained polling datasets."""

from __future__ import annotations

import json
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from pollingapi.core import settings
from pollingapi.logging_config import get_logger
from pollingapi.models import (
    Election,
    Institute,
    Method,
    Party,
    Poll,
    PollResult,
    Provider,
    RawPoll,
    Tasker,
)

logger = get_logger(__name__)


def _dt_to_str(value: date | datetime | None) -> str | None:
    """Serialize date/datetime values to ISO strings."""
    return value.isoformat() if value else None


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def _write_table(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


class ExportService:
    """Service for exporting public polling datasets and lookup dictionaries."""

    def __init__(self, db: Session):
        """Initialize export service with database session."""
        self.db = db
        self.export_dir = settings.export_dir
        self.dictionary_dir = self.export_dir / "dictionaries"

    def export_all(self) -> dict[str, int]:
        """Run all exports.

        Returns:
            Dictionary with counts of exported records per dataset.
        """
        polls_count = self.export_polls()
        observations_count = self.export_observations()
        wide_count = self.export_polls_wide()
        raw_count = self.export_raw()
        dictionary_counts = self.export_dictionaries()
        self.export_metadata(dictionary_counts=dictionary_counts)

        return {
            "polls": polls_count,
            "results": observations_count,
            "observations": observations_count,
            "wide": wide_count,
            "raw": raw_count,
            "dictionaries": sum(dictionary_counts.values()),
        }

    def _poll_query(self) -> list[Poll]:
        return (
            self.db.query(Poll)
            .options(
                joinedload(Poll.raw_poll),
                joinedload(Poll.institute),
                joinedload(Poll.provider),
                joinedload(Poll.election),
                joinedload(Poll.method),
                joinedload(Poll.matching_poll),
                joinedload(Poll.results).joinedload(PollResult.party),
            )
            .order_by(Poll.publish_date.desc(), Poll.id.desc())
            .all()
        )

    def _result_query(self) -> list[PollResult]:
        return (
            self.db.query(PollResult)
            .options(
                joinedload(PollResult.party),
                joinedload(PollResult.poll).joinedload(Poll.raw_poll),
                joinedload(PollResult.poll).joinedload(Poll.institute),
                joinedload(PollResult.poll).joinedload(Poll.provider),
                joinedload(PollResult.poll).joinedload(Poll.election),
                joinedload(PollResult.poll).joinedload(Poll.method),
                joinedload(PollResult.poll).joinedload(Poll.matching_poll),
            )
            .join(Poll)
            .order_by(Poll.publish_date.desc(), Poll.id.desc(), PollResult.party_key.asc())
            .all()
        )

    @staticmethod
    def _poll_base_row(poll: Poll) -> dict[str, Any]:
        return {
            "poll_public_id": poll.public_id,
            "raw_public_id": poll.raw_poll.public_id if poll.raw_poll else None,
            "publish_date": _dt_to_str(poll.publish_date),
            "survey_date_start": _dt_to_str(poll.survey_date_start),
            "survey_date_end": _dt_to_str(poll.survey_date_end),
            "respondents": poll.respondents,
            "scope": poll.scope,
            "source": poll.source,
            "institute_key": poll.institute_key,
            "institute_name": poll.institute.name if poll.institute else None,
            "provider_name": poll.provider.name if poll.provider else None,
            "election_key": poll.election_key,
            "election_type": poll.election.election_type if poll.election else None,
            "method_key": poll.method_key,
            "method_name": poll.method.name if poll.method else None,
            "matching_status": poll.matching_status,
            "matching_poll_public_id": poll.matching_poll.public_id if poll.matching_poll else None,
            "fingerprint": poll.fingerprint,
        }

    @staticmethod
    def _poll_json_row(poll: Poll) -> dict[str, Any]:
        return {
            **ExportService._poll_base_row(poll),
            "provider": {
                "id": poll.provider_id,
                "name": poll.provider.name if poll.provider else None,
            },
            "institute": {
                "key": poll.institute_key,
                "name": poll.institute.name if poll.institute else None,
            },
            "method": {
                "key": poll.method_key,
                "name": poll.method.name if poll.method else None,
            },
            "election": {
                "key": poll.election_key,
                "type": poll.election.election_type if poll.election else None,
                "scope": poll.election.scope if poll.election else None,
                "year": poll.election.year if poll.election else None,
                "date": _dt_to_str(poll.election.date) if poll.election else None,
            },
            "matching": {
                "status": poll.matching_status,
                "matching_poll_public_id": poll.matching_poll.public_id
                if poll.matching_poll
                else None,
            },
            "results": [
                {
                    "party_key": result.party_key,
                    "party_short_name": result.party.short_name if result.party else None,
                    "party_name": result.party.name if result.party else None,
                    "percentage": result.percentage,
                }
                for result in sorted(poll.results, key=lambda item: item.party_key)
            ],
        }

    def export_polls(self) -> int:
        """Export cleaned polls as nested JSON plus flat CSV/Parquet."""
        polls = self._poll_query()
        nested_rows = [self._poll_json_row(poll) for poll in polls]
        flat_rows = [self._poll_base_row(poll) for poll in polls]

        _write_json(self.export_dir / "polls.json", nested_rows)
        _write_table(self.export_dir / "polls.csv", flat_rows)
        _write_parquet(self.export_dir / "polls.parquet", flat_rows)

        logger.info(f"Exported {len(nested_rows)} cleaned polls")
        return len(nested_rows)

    def _observation_row(self, result: PollResult) -> dict[str, Any]:
        poll = result.poll
        party = result.party
        return {
            **self._poll_base_row(poll),
            "party_key": result.party_key,
            "party_short_name": party.short_name if party else None,
            "party_name": party.name if party else None,
            "percentage": result.percentage,
        }

    def export_observations(self) -> int:
        """Export long-format observations, one row per poll-party result."""
        rows = [self._observation_row(result) for result in self._result_query()]

        _write_json(self.export_dir / "observations.json", rows)
        _write_table(self.export_dir / "observations.csv", rows)
        _write_parquet(self.export_dir / "observations.parquet", rows)

        # Backward-compatible aliases for older consumers.
        for suffix in ("json", "csv", "parquet"):
            source = self.export_dir / f"observations.{suffix}"
            target = self.export_dir / f"poll_results.{suffix}"
            shutil.copyfile(source, target)

        logger.info(f"Exported {len(rows)} observations")
        return len(rows)

    def export_results(self) -> int:
        """Backward-compatible alias for the long-format observations export."""
        return self.export_observations()

    def export_polls_wide(self) -> int:
        """Export wide poll rows with party keys as columns."""
        rows = []
        for poll in self._poll_query():
            row = self._poll_base_row(poll)
            for result in sorted(poll.results, key=lambda item: item.party_key):
                row[result.party_key] = result.percentage
            rows.append(row)

        _write_json(self.export_dir / "polls_wide.json", rows)
        _write_table(self.export_dir / "polls_wide.csv", rows)
        _write_parquet(self.export_dir / "polls_wide.parquet", rows)

        logger.info(f"Exported {len(rows)} wide poll rows")
        return len(rows)

    def export_raw(self) -> int:
        """Export immutable raw polls for traceability."""
        raw_polls = self.db.query(RawPoll).order_by(RawPoll.id).all()
        raw_data = [
            {
                "raw_public_id": r.public_id,
                "publish_date": r.publish_date,
                "survey_date_start": r.survey_date_start,
                "survey_date_end": r.survey_date_end,
                "respondents": r.respondents,
                "zeitraum": r.zeitraum,
                "parties": r.parties,
                "institute_id": r.institute_id,
                "provider": r.provider,
                "tasker": r.tasker,
                "source": r.source,
                "scope": r.scope,
                "election_id": r.election_id,
                "method_id": r.method_id,
                "worker": r.worker,
                "survey_type": r.survey_type,
                "duplicate_of_poll_id": r.duplicate_of_poll_id,
                "pipeline_run_id": r.pipeline_run_id,
                "date_downloaded": r.date_downloaded,
            }
            for r in raw_polls
        ]

        _write_json(self.export_dir / "polls_raw.json", raw_data)
        _write_table(self.export_dir / "polls_raw.csv", raw_data)
        _write_parquet(self.export_dir / "polls_raw.parquet", raw_data)

        logger.info(f"Exported {len(raw_data)} raw polls")
        return len(raw_data)

    def export_dictionaries(self) -> dict[str, int]:
        """Export lookup dictionaries from the database."""
        dictionaries = {
            "parties": [
                {
                    "key": party.key,
                    "name": party.name,
                    "short_name": party.short_name,
                    "color": party.color,
                }
                for party in self.db.query(Party).order_by(Party.key).all()
            ],
            "institutes": [
                {
                    "key": institute.key,
                    "name": institute.name,
                    "description": institute.description,
                }
                for institute in self.db.query(Institute).order_by(Institute.key).all()
            ],
            "providers": [
                {
                    "id": provider.id,
                    "name": provider.name,
                    "description": provider.description,
                }
                for provider in self.db.query(Provider).order_by(Provider.name).all()
            ],
            "methods": [
                {
                    "key": method.key,
                    "name": method.name,
                    "description": method.description,
                }
                for method in self.db.query(Method).order_by(Method.key).all()
            ],
            "elections": [
                {
                    "key": election.key,
                    "election_type": election.election_type,
                    "year": election.year,
                    "scope": election.scope,
                    "date": _dt_to_str(election.date),
                }
                for election in self.db.query(Election).order_by(Election.key).all()
            ],
            "taskers": [
                {
                    "id": tasker.id,
                    "name": tasker.name,
                    "description": tasker.description,
                }
                for tasker in self.db.query(Tasker).order_by(Tasker.name).all()
            ],
        }

        counts = {}
        for name, rows in dictionaries.items():
            _write_json(self.dictionary_dir / f"{name}.json", rows)
            counts[name] = len(rows)

        logger.info(f"Exported {len(dictionaries)} dictionaries")
        return counts

    def export_metadata(self, dictionary_counts: dict[str, int] | None = None) -> dict:
        """Export a machine-readable manifest for the export bundle."""
        poll_count = self.db.query(func.count(Poll.id)).scalar() or 0
        raw_count = self.db.query(func.count(RawPoll.id)).scalar() or 0
        observation_count = self.db.query(func.count(PollResult.id)).scalar() or 0
        dictionary_counts = dictionary_counts or self.export_dictionaries()

        metadata = {
            "generated_at": datetime.now().isoformat(),
            "api_version": settings.api_version,
            "counts": {
                "polls": poll_count,
                "observations": observation_count,
                "raw_polls": raw_count,
                "dictionaries": dictionary_counts,
            },
            "datasets": {
                "polls": {
                    "description": "One row per cleaned poll; JSON includes nested party results.",
                    "files": ["polls.json", "polls.csv", "polls.parquet"],
                },
                "observations": {
                    "description": "Long format, one row per poll-party result.",
                    "files": [
                        "observations.json",
                        "observations.csv",
                        "observations.parquet",
                    ],
                    "aliases": [
                        "poll_results.json",
                        "poll_results.csv",
                        "poll_results.parquet",
                    ],
                },
                "polls_wide": {
                    "description": "One row per cleaned poll with party keys as columns.",
                    "files": ["polls_wide.json", "polls_wide.csv", "polls_wide.parquet"],
                },
                "raw_polls": {
                    "description": "Immutable raw scraper/API rows for traceability.",
                    "files": ["polls_raw.json", "polls_raw.csv", "polls_raw.parquet"],
                },
                "dictionaries": {
                    "description": "Lookup tables exported from the database.",
                    "files": [f"dictionaries/{name}.json" for name in sorted(dictionary_counts)],
                },
            },
            "identifier_policy": {
                "primary_poll_id": "poll_public_id",
                "primary_raw_id": "raw_public_id",
                "stable_lookup_keys": [
                    "party_key",
                    "institute_key",
                    "method_key",
                    "election_key",
                ],
            },
        }

        _write_json(self.export_dir / "metadata.json", metadata)
        logger.info("Exported metadata")
        return metadata
