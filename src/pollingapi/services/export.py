"""Export service for polling data."""

import json
from datetime import datetime

import pandas as pd
from sqlalchemy import extract, func, or_
from sqlalchemy.orm import Session, joinedload

from pollingapi.core import settings
from pollingapi.data_validation.config import PublicDatasetConfig, get_validation_config
from pollingapi.logging_config import get_logger
from pollingapi.models import Poll, PollResult, PollValidation, Provider, RawPoll

logger = get_logger(__name__)


def _dt_to_str(value: datetime | None) -> str | None:
    """Serialize datetime to ISO string."""
    return value.isoformat() if value else None


class ExportService:
    """Service for exporting polling data to JSON, CSV, and Parquet files."""

    def __init__(self, db: Session):
        """Initialize export service with database session."""
        self.db = db

    def export_all(self) -> dict[str, int]:
        """Run all exports.

        Returns:
            Dictionary with counts of exported records per file.
        """
        polls_count = self.export_polls()
        results_count = self.export_results()
        all_cleaned_polls_count = self.export_all_cleaned_polls()
        all_cleaned_results_count = self.export_all_cleaned_results()
        raw_count = self.export_raw()
        self.export_metadata()

        return {
            "polls": polls_count,
            "results": results_count,
            "observations": results_count,
            "all_cleaned_polls": all_cleaned_polls_count,
            "all_cleaned_results": all_cleaned_results_count,
            "raw": raw_count,
        }

    def _base_poll_query(self):
        return self.db.query(Poll).options(
            joinedload(Poll.raw_poll),
            joinedload(Poll.institute),
            joinedload(Poll.provider),
            joinedload(Poll.election),
            joinedload(Poll.method),
            joinedload(Poll.matching_poll),
            joinedload(Poll.results).joinedload(PollResult.party),
        )

    def _base_result_query(self):
        return (
            self.db.query(PollResult)
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

    def _public_polls(self, query):
        return _apply_public_dataset_policy(query, get_validation_config().public_dataset)

    def _poll_rows(self, polls: list[Poll]) -> list[dict]:
        return [
            {
                "id": poll.id,
                "public_id": poll.public_id,
                "raw_id": poll.raw_id,
                "raw_public_id": poll.raw_poll.public_id if poll.raw_poll else None,
                "publish_date": _dt_to_str(poll.publish_date),
                "survey_date_start": _dt_to_str(poll.survey_date_start),
                "survey_date_end": _dt_to_str(poll.survey_date_end),
                "respondents": poll.respondents,
                "institute_key": poll.institute_key,
                "institute_name": poll.institute.name if poll.institute else None,
                "provider_id": poll.provider_id,
                "provider_name": poll.provider.name if poll.provider else None,
                "election_key": poll.election_key,
                "election_type": poll.election.election_type if poll.election else None,
                "method_key": poll.method_key,
                "method_name": poll.method.name if poll.method else None,
                "matching_poll_id": poll.matching_poll_id,
                "matching_poll_public_id": poll.matching_poll.public_id
                if poll.matching_poll
                else None,
                "matching_status": poll.matching_status,
                "is_public": poll.is_public,
                "public_exclusion_reason": poll.public_exclusion_reason,
                "scope": poll.scope,
                "source": poll.source,
                "fingerprint": poll.fingerprint,
            }
            for poll in polls
        ]

    def _result_rows(self, results: list[PollResult]) -> list[dict]:
        return [
            {
                "poll_id": r.poll_id,
                "poll_public_id": r.poll.public_id if r.poll else None,
                "poll_raw_id": r.poll.raw_id if r.poll else None,
                "poll_raw_public_id": r.poll.raw_poll.public_id
                if r.poll and r.poll.raw_poll
                else None,
                "publish_date": _dt_to_str(r.poll.publish_date) if r.poll else None,
                "survey_date_start": _dt_to_str(r.poll.survey_date_start) if r.poll else None,
                "survey_date_end": _dt_to_str(r.poll.survey_date_end) if r.poll else None,
                "respondents": r.poll.respondents if r.poll else None,
                "institute_key": r.poll.institute_key if r.poll else None,
                "institute_name": r.poll.institute.name if r.poll and r.poll.institute else None,
                "election_key": r.poll.election_key if r.poll else None,
                "scope": r.poll.scope if r.poll else None,
                "is_public": r.poll.is_public if r.poll else None,
                "public_exclusion_reason": r.poll.public_exclusion_reason if r.poll else None,
                "party_key": r.party_key,
                "party_short_name": r.party.short_name if r.party else None,
                "party_name": r.party.name if r.party else None,
                "percentage": r.percentage,
            }
            for r in results
        ]

    def _write_dataset(self, rows: list[dict], filename_base: str, label: str) -> int:
        file_path = settings.export_dir / f"{filename_base}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)
        logger.info(f"Exported {len(rows)} {label} to JSON")

        df = pd.DataFrame(rows)
        file_path = settings.export_dir / f"{filename_base}.csv"
        df.to_csv(file_path, index=False)
        logger.info(f"Exported {len(rows)} {label} to CSV")

        file_path = settings.export_dir / f"{filename_base}.parquet"
        df.to_parquet(file_path, index=False)
        logger.info(f"Exported {len(rows)} {label} to Parquet")

        return len(rows)

    def export_polls(self) -> int:
        """Export cleaned polls to JSON, CSV, and Parquet.

        Returns:
            Number of polls exported.
        """
        polls = self._public_polls(self._base_poll_query()).all()
        return self._write_dataset(self._poll_rows(polls), "polls", "public polls")

    def export_results(self) -> int:
        """Export poll-party results to JSON, CSV, and Parquet.

        Returns:
            Number of poll results exported.
        """
        results = self._public_polls(self._base_result_query()).all()
        return self._write_dataset(
            self._result_rows(results), "poll_results", "public poll results"
        )

    def export_all_cleaned_polls(self) -> int:
        """Export all cleaned polls before public dataset subsetting."""
        polls = self._base_poll_query().all()
        return self._write_dataset(self._poll_rows(polls), "all_cleaned_polls", "all cleaned polls")

    def export_all_cleaned_results(self) -> int:
        """Export all cleaned poll-party results before public dataset subsetting."""
        results = self._base_result_query().all()
        return self._write_dataset(
            self._result_rows(results),
            "all_cleaned_poll_results",
            "all cleaned poll results",
        )

    def export_observations(self) -> int:
        """Return the public long-format poll result export count."""
        return self.export_results()

    def export_raw(self) -> int:
        """Export raw polls to JSON, CSV, and Parquet.

        Returns:
            Number of raw polls exported.
        """
        raw_polls = self.db.query(RawPoll).order_by(RawPoll.id).all()

        raw_data = [
            {
                "id": r.id,
                "public_id": r.public_id,
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

        # JSON
        file_path = settings.export_dir / "polls_raw.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"Exported {len(raw_data)} raw polls to JSON")

        # CSV
        df = pd.DataFrame(raw_data)
        file_path = settings.export_dir / "polls_raw.csv"
        df.to_csv(file_path, index=False)
        logger.info(f"Exported {len(raw_data)} raw polls to CSV")

        # Parquet
        file_path = settings.export_dir / "polls_raw.parquet"
        df.to_parquet(file_path, index=False)
        logger.info(f"Exported {len(raw_data)} raw polls to Parquet")

        return len(raw_data)

    def export_metadata(self) -> dict:
        """Export metadata file with export timestamp and record counts.

        Returns:
            Metadata dictionary.
        """
        poll_count = self._public_polls(self.db.query(func.count(Poll.id))).scalar() or 0
        all_cleaned_poll_count = self.db.query(func.count(Poll.id)).scalar() or 0
        raw_count = self.db.query(func.count(RawPoll.id)).scalar() or 0
        result_count = (
            self._public_polls(self.db.query(func.count(PollResult.id)).join(Poll)).scalar() or 0
        )
        all_cleaned_result_count = self.db.query(func.count(PollResult.id)).scalar() or 0

        metadata = {
            "exported_at": datetime.now().isoformat(),
            "default_dataset": "public",
            "counts": {
                "polls": poll_count,
                "poll_results": result_count,
                "all_cleaned_polls": all_cleaned_poll_count,
                "all_cleaned_poll_results": all_cleaned_result_count,
                "raw_polls": raw_count,
            },
            "formats": [
                "json",
                "csv",
                "parquet",
            ],
            "files": {
                "polls": {
                    "json": "polls.json",
                    "csv": "polls.csv",
                    "parquet": "polls.parquet",
                },
                "poll_results": {
                    "json": "poll_results.json",
                    "csv": "poll_results.csv",
                    "parquet": "poll_results.parquet",
                },
                "all_cleaned_polls": {
                    "json": "all_cleaned_polls.json",
                    "csv": "all_cleaned_polls.csv",
                    "parquet": "all_cleaned_polls.parquet",
                },
                "all_cleaned_poll_results": {
                    "json": "all_cleaned_poll_results.json",
                    "csv": "all_cleaned_poll_results.csv",
                    "parquet": "all_cleaned_poll_results.parquet",
                },
                "raw_polls": {
                    "json": "polls_raw.json",
                    "csv": "polls_raw.csv",
                    "parquet": "polls_raw.parquet",
                },
            },
        }

        file_path = settings.export_dir / "metadata.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info("Exported metadata")
        return metadata


def _apply_public_dataset_policy(query, policy: PublicDatasetConfig):
    query = query.filter(Poll.is_public.is_(True))
    prevalidated = Poll.provider.has(
        func.lower(Provider.name) == policy.selection.pre_cutoff_provider.lower()
    ) & (extract("year", Poll.publish_date) < policy.selection.cutoff_year)

    if policy.require_persisted_validation:
        query = query.outerjoin(Poll.validation)
    else:
        query = query.outerjoin(Poll.validation)

    if policy.include_valid:
        query = query.filter(or_(prevalidated, PollValidation.valid.is_(True)))
    else:
        query = query.filter(PollValidation.valid.is_(False))

    if not policy.include_warnings:
        query = query.filter(or_(prevalidated, PollValidation.warning_count == 0))

    for check_name in policy.exclude_failed_checks:
        column = getattr(PollValidation, check_name, None)
        if column is None:
            raise ValueError(f"Unknown public dataset validation check: {check_name}")
        query = query.filter(or_(prevalidated, column.is_(True)))

    return query
