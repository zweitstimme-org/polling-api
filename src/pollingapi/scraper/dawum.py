"""DAWUM API scraper."""

import json
from datetime import datetime
from typing import Any

import pandas as pd
import requests
from sqlalchemy.orm import Session

from pollingapi.core import DATA_DIR
from pollingapi.logging_config import get_logger
from pollingapi.models import RawPoll
from pollingapi.scraper.context import RunContext
from pollingapi.scraper.dawum_parliaments import (
    UnknownDawumParliamentError,
    map_dawum_parliament,
)
from pollingapi.scraper.schemas import filter_poll_payloads

# Identity for DAWUM re-ingest. Scope/election_id are intentionally excluded so
# correcting a mis-scoped row updates in place instead of inserting a duplicate.
_DAWUM_IDENTITY_KEYS = (
    "publish_date",
    "survey_date_start",
    "survey_date_end",
    "respondents",
    "zeitraum",
    "parties",
    "institute_id",
    "provider",
    "tasker",
    "source",
    "method_id",
    "worker",
    "survey_type",
)


class DawumScraper:
    """Scraper for DAWUM API data."""

    DATA_SOURCE = "DAWUM"
    WORKER = "dawum"
    REQUEST_TIMEOUT = 30

    def __init__(
        self,
        db: Session,
        context: RunContext | None = None,
        dry_run: bool = False,
    ):
        """Initialize DAWUM scraper."""
        self.db = db
        self.context = context or RunContext.for_project()
        self.dry_run = dry_run
        self.logger = get_logger("dawum")
        self.session = requests.Session()

    def retrieve_data(self) -> dict[str, Any]:
        """Fetch data from DAWUM API."""
        url = "https://api.dawum.de/"
        self.logger.info(f"Fetching data from DAWUM API: {url}")
        response = self.session.get(url, timeout=self.REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()

    def wrangle_data(self, data: dict[str, Any]) -> pd.DataFrame:
        """Transform DAWUM API data to standard format."""
        # Extract entities
        parliaments = pd.DataFrame.from_dict(data.get("Parliaments", {}), orient="index")
        institutes = pd.DataFrame.from_dict(data.get("Institutes", {}), orient="index")
        taskers = pd.DataFrame.from_dict(data.get("Taskers", {}), orient="index")
        methods = pd.DataFrame.from_dict(data.get("Methods", {}), orient="index")
        parties = pd.DataFrame.from_dict(data.get("Parties", {}), orient="index")
        surveys = pd.DataFrame.from_dict(data.get("Surveys", {}), orient="index")

        if surveys.empty:
            raise ValueError("No survey data found in DAWUM API response")

        # Merge surveys with related data
        df = surveys.reset_index().rename(columns={"index": "Survey_ID"})

        # Merge with parliaments
        if not parliaments.empty:
            parliaments_reset = parliaments.reset_index().rename(columns={"index": "Parliament_ID"})
            keep = ["Parliament_ID", "Shortcut"]
            if "Election" in parliaments_reset.columns:
                keep.append("Election")
            df = df.merge(
                parliaments_reset[keep].rename(
                    columns={"Shortcut": "Parliament", "Election": "Election_Name"}
                ),
                on="Parliament_ID",
                how="left",
            )

        # Merge with institutes
        if not institutes.empty:
            institutes_reset = institutes.reset_index().rename(columns={"index": "Institute_ID"})
            df = df.merge(
                institutes_reset[["Institute_ID", "Name"]].rename(columns={"Name": "Institute"}),
                on="Institute_ID",
                how="left",
            )

        # Merge with taskers
        if not taskers.empty:
            taskers_reset = taskers.reset_index().rename(columns={"index": "Tasker_ID"})
            df = df.merge(
                taskers_reset[["Tasker_ID", "Name"]].rename(columns={"Name": "Tasker"}),
                on="Tasker_ID",
                how="left",
            )

        # Merge with methods
        if not methods.empty:
            methods_reset = methods.reset_index().rename(columns={"index": "Method_ID"})
            df = df.merge(
                methods_reset[["Method_ID", "Name"]].rename(columns={"Name": "Method"}),
                on="Method_ID",
                how="left",
            )

        # Extract party results
        party_results = []
        for _, row in df.iterrows():
            results = row.get("Results", {})
            party_dict = {}
            for party_id, percentage in results.items():
                party_name = (
                    parties.loc[party_id, "Shortcut"] if party_id in parties.index else party_id
                )
                try:
                    party_dict[party_name] = float(percentage)
                except (ValueError, TypeError):
                    continue
            party_results.append(party_dict)

        df["parties"] = party_results

        # Extract survey dates
        def extract_dates(period):
            """Extract start and end dates from Survey_Period."""
            if not period or not isinstance(period, dict):
                return None, None
            return period.get("Date_Start"), period.get("Date_End")

        dates = df["Survey_Period"].apply(extract_dates)
        df["survey_date_start"] = dates.apply(lambda x: x[0] if x else None)
        df["survey_date_end"] = dates.apply(lambda x: x[1] if x else None)

        return df

    def prepare_db_payload(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """Prepare dataframe for database insertion."""
        df_mapped = df.copy()

        # Map columns to database schema
        column_mapping = {
            "Date": "publish_date",
            "Surveyed_Persons": "respondents",
            "Institute": "institute_id",
            "Tasker": "tasker",
            "Method": "method_id",
        }
        df_mapped = df_mapped.rename(columns=column_mapping)

        scopes: list[str] = []
        election_ids: list[str] = []
        skipped_unknown = 0
        keep_mask: list[bool] = []
        for _, row in df_mapped.iterrows():
            try:
                mapping = map_dawum_parliament(
                    row.get("Parliament_ID"),
                    shortcut=row.get("Parliament"),
                    election=row.get("Election_Name"),
                )
            except UnknownDawumParliamentError as exc:
                skipped_unknown += 1
                self.logger.warning("Skipping DAWUM survey with unmapped parliament: %s", exc)
                keep_mask.append(False)
                scopes.append("")
                election_ids.append("")
                continue
            keep_mask.append(True)
            scopes.append(mapping.scope)
            election_ids.append(mapping.election_id)

        df_mapped["scope"] = scopes
        df_mapped["election_id"] = election_ids
        df_mapped = df_mapped.loc[keep_mask].copy()
        if skipped_unknown:
            self.logger.warning(
                "Skipped %d DAWUM surveys with unknown parliament mapping", skipped_unknown
            )

        # Add metadata
        df_mapped["provider"] = self.DATA_SOURCE
        df_mapped["source"] = "api"
        df_mapped["worker"] = self.WORKER
        df_mapped["zeitraum"] = None
        df_mapped["survey_type"] = None
        df_mapped["pipeline_run_id"] = self.context.run_id
        df_mapped["date_downloaded"] = datetime.now().isoformat()

        # Select only needed columns
        keep_cols = [
            "publish_date",
            "respondents",
            "parties",
            "institute_id",
            "tasker",
            "method_id",
            "provider",
            "source",
            "scope",
            "election_id",
            "worker",
            "zeitraum",
            "survey_type",
            "pipeline_run_id",
            "date_downloaded",
            "survey_date_start",
            "survey_date_end",
        ]

        available_cols = [col for col in keep_cols if col in df_mapped.columns]
        return df_mapped[available_cols].to_dict("records")

    @staticmethod
    def _parties_json(parties: Any) -> str | None:
        if not parties:
            return None
        return json.dumps(parties, sort_keys=True)

    def _raw_poll_from_payload(self, payload: dict[str, Any]) -> RawPoll:
        """Create a RawPoll row from a normalized DAWUM payload."""
        return RawPoll(
            publish_date=payload.get("publish_date"),
            survey_date_start=payload.get("survey_date_start"),
            survey_date_end=payload.get("survey_date_end"),
            respondents=payload.get("respondents"),
            zeitraum=payload.get("zeitraum"),
            parties=self._parties_json(payload.get("parties")),
            institute_id=payload.get("institute_id"),
            provider=payload.get("provider"),
            tasker=payload.get("tasker"),
            source=payload.get("source"),
            scope=payload.get("scope"),
            election_id=payload.get("election_id"),
            method_id=payload.get("method_id"),
            worker=payload.get("worker"),
            survey_type=payload.get("survey_type"),
            date_downloaded=payload.get("date_downloaded"),
            pipeline_run_id=payload.get("pipeline_run_id"),
        )

    def _find_existing_raw(self, payload: dict[str, Any]) -> RawPoll | None:
        """Find an existing DAWUM raw row by survey identity (not scope)."""
        query = self.db.query(RawPoll)
        for key in _DAWUM_IDENTITY_KEYS:
            column = getattr(RawPoll, key)
            value = payload.get(key)
            if key == "parties":
                value = self._parties_json(value) if not isinstance(value, str) else value
            query = (
                query.filter(column.is_(None)) if value is None else query.filter(column == value)
            )
        return query.first()

    def post_polls(self, payloads: list[dict[str, Any]]) -> int:
        """Insert polls into database with deduplication / scope correction."""
        if self.dry_run:
            new_or_fixable = []
            skipped = 0
            for payload in payloads:
                existing = self._find_existing_raw(payload)
                needs_write = existing is None or existing.scope != payload.get(
                    "scope"
                ) or existing.election_id != payload.get("election_id")
                if needs_write:
                    new_or_fixable.append(payload)
                else:
                    skipped += 1
            self.logger.info(
                f"[DRY RUN] Would insert/update {len(new_or_fixable)} DAWUM polls "
                f"(skipped {skipped} unchanged duplicates)"
            )
            for payload in new_or_fixable[:3]:
                self.logger.info(f"  {payload}")
            if len(new_or_fixable) > 3:
                self.logger.info(f"  ... and {len(new_or_fixable) - 3} more")
            return len(new_or_fixable)

        inserted_count = 0
        updated_count = 0
        skipped_count = 0

        for payload in payloads:
            try:
                existing = self._find_existing_raw(payload)
                if existing is not None:
                    scope = payload.get("scope")
                    election_id = payload.get("election_id")
                    if existing.scope != scope or existing.election_id != election_id:
                        existing.scope = scope
                        existing.election_id = election_id
                        updated_count += 1
                    else:
                        skipped_count += 1
                    continue

                self.db.add(self._raw_poll_from_payload(payload))
                inserted_count += 1

            except Exception as e:
                self.logger.error(f"Error inserting poll: {e}")
                continue

        # Commit all successful inserts / updates
        if inserted_count > 0 or updated_count > 0:
            try:
                self.db.commit()
                self.logger.info(
                    "DAWUM ingest: inserted=%d updated_scope=%d skipped=%d",
                    inserted_count,
                    updated_count,
                    skipped_count,
                )
            except Exception as e:
                self.db.rollback()
                self.logger.error(f"Error committing DAWUM transactions: {e}")
                return 0
        else:
            self.logger.info(f"No new DAWUM polls to insert (skipped {skipped_count} duplicates)")

        return inserted_count + updated_count

    def run(self) -> int:
        """Run the DAWUM scraper."""
        self.logger.info("Starting DAWUM scraper")

        try:
            # Retrieve data
            data = self.retrieve_data()

            # Save raw JSON
            dawum_dir = DATA_DIR / "dawum" / self.context.today_str
            dawum_dir.mkdir(parents=True, exist_ok=True)
            with open(dawum_dir / "dawum_dump.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Wrangle data
            df = self.wrangle_data(data)
            df.to_csv(dawum_dir / "dawum_wrangled.csv", index=False)
            self.logger.info(f"Processed {len(df)} surveys from DAWUM")

            # Prepare and insert
            payloads = self.prepare_db_payload(df)
            payloads = filter_poll_payloads(payloads)
            self.last_polls_found = len(payloads)
            self.logger.info(f"Prepared {len(payloads)} payloads for insertion")

            new_count = self.post_polls(payloads)
            action = "Would insert" if self.dry_run else "Successfully inserted"
            self.logger.info(f"{action} {new_count} polls from DAWUM")

            return new_count

        except Exception as e:
            self.logger.error(f"Error in DAWUM scraper: {e}")
            if self.context.debug:
                raise
            return 0
