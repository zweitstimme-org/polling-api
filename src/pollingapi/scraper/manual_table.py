"""Manual table scraper for specific HTML files."""

from typing import Any

import pandas as pd

from pollingapi.scraper.base import BaseScraper
from pollingapi.scraper.config import ScraperRegistry
from pollingapi.scraper.schemas import filter_poll_payloads


@ScraperRegistry.register("manual_table")
class ManualTableScraper(BaseScraper):
    """Scraper for manually specified HTML tables."""

    def parse_url(self, url: str, url_config: dict[str, Any]) -> pd.DataFrame:
        """Parse is not used - build_table is called directly."""
        # This method is required by BaseScraper but not used
        # ManualTableScraper uses build_table instead
        return pd.DataFrame()

    def build_table(self) -> pd.DataFrame:
        """Build table from manual data - override in subclasses."""
        raise NotImplementedError("Subclasses must implement build_table()")

    def build_parties(self, row: pd.Series, party_columns: list[str]) -> dict[str, Any]:
        """Build parties dict from row data."""
        parties = {}
        for col in party_columns:
            if col in row.index and pd.notna(row[col]):
                try:
                    val = str(row[col]).replace("%", "").replace(",", ".").strip()
                    parties[col] = float(val)
                except (ValueError, TypeError):
                    continue
        return parties

    def run(self) -> int:
        """Run the manual table scraper."""
        try:
            df = self.build_table()
            if df.empty:
                self.logger.warning(f"No data from {self.config.worker_name}")
                return 0

            # Apply metadata
            df["scope"] = self.config.scope
            df["election_id"] = self.config.election_id
            df["method_id"] = self.config.method_id
            df["provider"] = self.config.provider
            df["source"] = self.config.source
            df["institute_id"] = self.config.institute_id
            df["date_downloaded"] = __import__("datetime").datetime.now().isoformat()

            # Filter and validate
            records = df.to_dict("records")
            payloads = filter_poll_payloads(records)

            # Insert into database
            inserted = self.post_polls(payloads)
            self.logger.info(f"Inserted {inserted} polls from {self.config.worker_name}")
            return inserted

        except Exception as e:
            self.logger.error(f"Error in {self.config.worker_name}: {e}")
            if self.context.debug:
                raise
            return 0
