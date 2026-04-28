"""Base scraper class for polling data collection."""

import json
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

from pollingapi.core import settings
from pollingapi.logging_config import get_logger
from pollingapi.models import RawPoll
from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.context import RunContext
from pollingapi.scraper.schemas import filter_poll_payloads
from pollingapi.scraper.snapshots import (
    save_html_snapshot,
)


class BaseScraper(ABC):
    """Abstract base class for poll scrapers."""

    # Rate limiting delay between requests (seconds)
    REQUEST_DELAY = 1.0

    def __init__(
        self,
        config: ScraperConfig,
        db: Session,
        context: RunContext | None = None,
        dry_run: bool = False,
    ):
        """Initialize scraper with config and database session."""
        self.config = config
        self.db = db
        self.context = context or RunContext.for_project()
        self.dry_run = dry_run
        self.logger = get_logger(config.worker_name)

        # HTTP session
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/91.0.4472.124 Safari/537.36"
                )
            }
        )

        # Data directory
        self.data_dir = settings.data_dir / config.worker_name
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _is_historic_url(self, url: str) -> bool:
        """Check if URL is historic (contains year pattern like 2002.htm, 2017.htm).

        Historic URLs have a 4-digit year before .htm extension.
        Current URLs don't have a year in the filename.
        """
        # Extract filename from URL
        filename = url.split("/")[-1] if "/" in url else url
        # Check if filename matches year pattern (e.g., 2002.htm, 2017.htm)
        return bool(re.search(r"/\d{4}\.htm", url) or re.match(r"\d{4}\.htm", filename))

    def select_urls(self) -> List[Dict[str, Any]]:
        """Select URLs to process.

        Strategy:
        - Historic URLs (with year): Process only once (tracked via marker file)
        - Current URLs (no year): Process on every run
        """
        if not self.config.urls:
            return []

        # Check which historic URLs have been processed
        processed_historic_marker = self.data_dir / ".historic_urls_processed"
        historic_processed = processed_historic_marker.exists()

        selected = []

        for url_config in self.config.urls:
            if isinstance(url_config, dict):
                url = url_config.get("url", "")
            else:
                url = url_config
                url_config = {"url": url}

            if not url:
                continue

            is_historic = self._is_historic_url(url)

            if is_historic:
                # Historic URLs: process only if not already processed
                if not historic_processed:
                    selected.append(url_config)
                    self.logger.debug(f"Including historic URL: {url}")
                else:
                    self.logger.debug(f"Skipping already processed historic URL: {url}")
            else:
                # Current URLs: always process
                selected.append(url_config)
                self.logger.debug(f"Including current URL: {url}")

        return selected

    def _mark_historic_processed(self):
        """Mark historic URLs as processed."""
        marker = self.data_dir / ".historic_urls_processed"
        marker.touch()

    def _fetch_html(self, url: str) -> str:
        """Fetch HTML from URL with rate limiting."""
        time.sleep(self.REQUEST_DELAY)
        response = self.session.get(url, timeout=settings.scraper_timeout)
        response.raise_for_status()
        response.encoding = "utf-8"
        return response.text

    def _apply_metadata(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply metadata columns to DataFrame."""
        df["scope"] = self.config.scope
        df["election_id"] = self.config.election_id
        df["method_id"] = self.config.method_id
        df["provider"] = self.config.provider
        df["source"] = self.config.source
        df["institute_id"] = self.config.institute_id
        df["date_downloaded"] = datetime.now().isoformat()
        return df

    def _check_duplicate(self, payload: Dict[str, Any]) -> bool:
        """Check if a poll already exists in the database.

        Uses a composite key of key identifying fields.
        """
        publish_date = payload.get("publish_date")
        survey_date_start = payload.get("survey_date_start")
        survey_date_end = payload.get("survey_date_end")
        source = payload.get("source")
        scope = payload.get("scope")
        institute_id = payload.get("institute_id")
        parties = payload.get("parties")

        # Build parties JSON for comparison
        parties_json = json.dumps(parties, sort_keys=True) if parties else None

        query = """
            SELECT id FROM polls_raw
            WHERE publish_date IS NOT DISTINCT FROM :publish_date
              AND survey_date_start IS NOT DISTINCT FROM :survey_date_start
              AND survey_date_end IS NOT DISTINCT FROM :survey_date_end
              AND source IS NOT DISTINCT FROM :source
              AND scope IS NOT DISTINCT FROM :scope
              AND institute_id IS NOT DISTINCT FROM :institute_id
              AND parties IS NOT DISTINCT FROM :parties
            LIMIT 1
        """

        result = self.db.execute(
            text(query),
            {
                "publish_date": publish_date,
                "survey_date_start": survey_date_start,
                "survey_date_end": survey_date_end,
                "source": source,
                "scope": scope,
                "institute_id": institute_id,
                "parties": parties_json,
            },
        )

        return result.scalar_one_or_none() is not None

    def post_polls(self, payloads: List[Dict[str, Any]]) -> int:
        """Insert polls into database with deduplication."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would insert {len(payloads)} polls")
            for payload in payloads[:3]:  # Show first 3
                self.logger.info(f"  {payload}")
            if len(payloads) > 3:
                self.logger.info(f"  ... and {len(payloads) - 3} more")
            return len(payloads)

        inserted_count = 0
        skipped_count = 0

        for payload in payloads:
            try:
                # Extract fields
                publish_date = payload.get("publish_date")
                survey_date_start = payload.get("survey_date_start")
                survey_date_end = payload.get("survey_date_end")
                respondents = payload.get("respondents") or payload.get("Befragte")
                zeitraum = payload.get("zeitraum") or payload.get("Zeitraum")
                parties = payload.get("parties")
                institute_id = payload.get("institute_id")
                provider = payload.get("provider")
                tasker = payload.get("tasker")
                source = payload.get("source")
                scope = payload.get("scope")
                election_id = payload.get("election_id")
                method_id = payload.get("method_id")
                date_downloaded = payload.get("date_downloaded")

                # Check for duplicates
                if self._check_duplicate(payload):
                    skipped_count += 1
                    continue

                # Create new raw poll
                raw_poll = RawPoll(
                    publish_date=publish_date,
                    survey_date_start=survey_date_start,
                    survey_date_end=survey_date_end,
                    respondents=respondents,
                    zeitraum=zeitraum,
                    parties=json.dumps(parties, sort_keys=True) if parties else None,
                    institute_id=institute_id,
                    provider=provider,
                    tasker=tasker,
                    source=source,
                    scope=scope,
                    election_id=election_id,
                    method_id=method_id,
                    date_downloaded=date_downloaded,
                    pipeline_run_id=self.context.run_id,
                )

                self.db.add(raw_poll)
                inserted_count += 1

            except Exception as e:
                self.logger.error(f"Error inserting poll: {e}")
                continue

        # Commit all successful inserts
        if inserted_count > 0:
            try:
                self.db.commit()
                self.logger.info(
                    f"Inserted {inserted_count} polls, skipped {skipped_count} duplicates"
                )
            except Exception as e:
                self.db.rollback()
                self.logger.error(f"Error committing transactions: {e}")
                return 0
        else:
            self.logger.info(f"No new polls to insert (skipped {skipped_count} duplicates)")

        return inserted_count

    def _mark_initial_run_complete(self):
        """Mark initial run as complete."""
        marker = self.data_dir / ".initial_run_complete"
        marker.touch()

    @abstractmethod
    def parse_url(self, url: str, url_config: Dict[str, Any]) -> pd.DataFrame:
        """Parse poll data from URL. Must be implemented by subclasses."""
        pass

    def run(self) -> int:
        """Run the scraper."""
        urls = self.select_urls()
        if not urls:
            self.logger.info(f"No URLs to process for {self.config.worker_name}")
            return 0

        total_inserted = 0
        has_historic_urls = False

        self.logger.info(f"Processing {len(urls)} URLs for {self.config.worker_name}")

        for url_config in urls:
            if isinstance(url_config, dict):
                url = url_config.get("url")
            else:
                url = url_config
                url_config = {"url": url}

            if not url:
                continue

            # Track if we processed any historic URLs
            if self._is_historic_url(url):
                has_historic_urls = True

            try:
                self.logger.info(f"Processing: {url}")

                # Fetch and save HTML
                html = self._fetch_html(url)
                save_html_snapshot(
                    self.config.worker_name,
                    url,
                    html,
                    self.context.today_str,
                )

                # Parse data
                df = self.parse_url(url, url_config)
                if df.empty:
                    self.logger.warning(f"No data found at {url}")
                    continue

                # Apply metadata
                df = self._apply_metadata(df)

                # # Save normalized snapshot
                # save_normalized_snapshot(
                #     self.config.worker_name,
                #     df,
                #     "normalized",
                #     self.context.today_str,
                # )

                # Filter and validate
                records = df.to_dict("records")
                payloads = filter_poll_payloads(records)

                # Insert into database
                inserted = self.post_polls(payloads)
                total_inserted += inserted
                self.logger.info(f"Inserted {inserted} polls from {url}")

            except Exception as e:
                self.logger.error(f"Error processing {url}: {e}")
                if self.context.debug:
                    raise
                continue

        # Mark historic URLs as processed if we processed any
        if has_historic_urls:
            self._mark_historic_processed()
            self.logger.info("Historic URLs marked as processed")

        # Mark initial run complete
        self._mark_initial_run_complete()

        self.logger.info(f"Total inserted: {total_inserted}")
        return total_inserted
