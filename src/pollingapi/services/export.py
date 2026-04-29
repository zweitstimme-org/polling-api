"""Export service for polling data."""

import json
from dataclasses import dataclass

import pandas as pd
from sqlalchemy.orm import Session

from pollingapi.core import settings
from pollingapi.logging_config import get_logger
from pollingapi.models import Poll, RawPoll

logger = get_logger(__name__)


@dataclass
class ExportStats:
    """Statistics for export operation."""

    polls: int
    poll_results: int
    raw_polls: int


class ExportService:
    """Service for exporting polling data to various formats."""

    def __init__(self, db: Session):
        """Initialize export service with database session."""
        self.db = db

    def export_all(self) -> ExportStats:
        """Export data to JSON, CSV, and Parquet files.

        Returns:
            ExportStats with counts of exported records.
        """
        polls_data = self._export_polls_json()
        poll_results_data = self._export_poll_results_json(polls_data)
        self._export_polls_csv(polls_data)
        self._export_polls_parquet(polls_data)
        raw_data = self._export_raw_polls_json()

        return ExportStats(
            polls=len(polls_data),
            poll_results=len(poll_results_data),
            raw_polls=len(raw_data),
        )

    def _export_polls_json(self) -> list[dict]:
        """Export cleaned polls to JSON."""
        polls = self.db.query(Poll).all()
        polls_data = []
        for poll in polls:
            poll_dict = {
                "id": poll.id,
                "public_id": poll.public_id,
                "raw_id": poll.raw_id,
                "raw_public_id": poll.raw_poll.public_id if poll.raw_poll else None,
                "publish_date": poll.publish_date.isoformat() if poll.publish_date else None,
                "survey_date_start": poll.survey_date_start.isoformat()
                if poll.survey_date_start
                else None,
                "survey_date_end": poll.survey_date_end.isoformat()
                if poll.survey_date_end
                else None,
                "respondents": poll.respondents,
                "institute_key": poll.institute_key,
                "provider_id": poll.provider_id,
                "method_key": poll.method_key,
                "election_key": poll.election_key,
                "scope": poll.scope,
                "results": [
                    {
                        "party_key": r.party_key,
                        "party_short_name": r.party.short_name if r.party else None,
                        "party_name": r.party.name if r.party else None,
                        "percentage": r.percentage,
                    }
                    for r in poll.results
                ],
            }
            polls_data.append(poll_dict)

        with open(settings.export_dir / "polls.json", "w", encoding="utf-8") as f:
            json.dump(polls_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Exported {len(polls_data)} polls to JSON")
        return polls_data

    def _export_poll_results_json(self, polls_data: list[dict]) -> list[dict]:
        """Export poll results to JSON."""
        poll_results_data = []
        for poll in polls_data:
            for result in poll.get("results", []):
                poll_results_data.append(
                    {
                "poll_id": poll["id"],
                "poll_public_id": poll.get("public_id"),
                "raw_id": poll.get("raw_id"),
                "raw_public_id": poll.get("raw_public_id"),
                        "publish_date": poll.get("publish_date"),
                        "scope": poll.get("scope"),
                        "party_key": result.get("party_key"),
                        "party_short_name": result.get("party_short_name"),
                        "party_name": result.get("party_name"),
                        "percentage": result.get("percentage"),
                    }
                )

        with open(settings.export_dir / "poll_results.json", "w", encoding="utf-8") as f:
            json.dump(poll_results_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Exported {len(poll_results_data)} poll results to JSON")
        return poll_results_data

    def _export_polls_csv(self, polls_data: list[dict]) -> None:
        """Export polls to CSV."""
        polls_df = pd.DataFrame(polls_data)
        if "results" in polls_df.columns:
            polls_df = polls_df.drop(columns=["results"])
        polls_df.to_csv(settings.export_dir / "polls.csv", index=False)
        logger.info(f"Exported {len(polls_data)} polls to CSV")

    def _export_polls_parquet(self, polls_data: list[dict]) -> None:
        """Export polls to Parquet."""
        polls_df = pd.DataFrame(polls_data)
        if "results" in polls_df.columns:
            polls_df = polls_df.drop(columns=["results"])
        try:
            polls_df.to_parquet(settings.export_dir / "polls.parquet", index=False)
            logger.info(f"Exported {len(polls_data)} polls to Parquet")
        except Exception as exc:
            logger.warning(f"Could not export Parquet: {exc}")

    def _export_raw_polls_json(self) -> list[dict]:
        """Export raw polls to JSON."""
        raw_polls = self.db.query(RawPoll).all()
        raw_data = []
        for raw in raw_polls:
            raw_dict = {
                "id": raw.id,
                "public_id": raw.public_id,
                "publish_date": raw.publish_date,
                "survey_date_start": raw.survey_date_start,
                "survey_date_end": raw.survey_date_end,
                "respondents": raw.respondents,
                "zeitraum": raw.zeitraum,
                "parties": raw.parties,
                "institute_id": raw.institute_id,
                "provider": raw.provider,
                "tasker": raw.tasker,
                "source": raw.source,
                "scope": raw.scope,
                "election_id": raw.election_id,
                "method_id": raw.method_id,
                "date_downloaded": raw.date_downloaded,
            }
            raw_data.append(raw_dict)

        with open(settings.export_dir / "polls_raw.json", "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Exported {len(raw_data)} raw polls to JSON")
        return raw_data
