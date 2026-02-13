"""Forsa 2001 scraper worker using the manual table template."""

import pandas as pd

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.manual_table import ManualTableScraper


class Forsa2001Scraper(ManualTableScraper):
    """Scraper for Forsa 2001 polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for Forsa 2001 scraper."""
        return ScraperConfig(
            worker_name="forsa_2001",
            institute_id="forsa",
            provider="Wahlrecht.de",
            source="manual_html",
            scope="federal",
            election_id="Bundestagswahl",
            method_id="99",
            type="manual_table",
        )

    def build_table(self) -> pd.DataFrame:
        """Load the 2001 table and map columns by hand."""
        html_files = list(self.data_dir.glob("html/*2001*.htm.html"))
        if not html_files:
            self.logger.warning(f"No 2001 HTML file found in {self.data_dir / 'html'}")
            return pd.DataFrame()

        path = html_files[0]
        tables = pd.read_html(path)
        df = tables[1].copy()

        df = df.iloc[:-1]
        df = df.rename(columns={df.columns[0]: "publish_date"})
        df = df[df["publish_date"].notna()]

        party_columns = ["CDU/CSU", "SPD", "GR\u00dcNE", "FDP", "PDS", "Sonstige"]
        df["parties"] = df.apply(
            lambda row: self.build_parties(row, party_columns),
            axis=1,
        )

        return df[["publish_date", "parties"]]


def get_config():
    """Return config for discovery."""
    return Forsa2001Scraper.get_config()
