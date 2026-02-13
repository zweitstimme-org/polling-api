"""Hessen scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtLandScraper


class HessenScraper(WahlrechtLandScraper):
    """Scraper for Hessen state polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for Hessen scraper."""
        return ScraperConfig(
            worker_name="wahlrecht_hessen",
            institute_id="various",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="hessen",
            election_id="Landtagswahl Hessen",
            method_id="99",
            urls=[
                {
                    "url": "https://www.wahlrecht.de/umfragen/landtage/hessen.htm",
                    "table_index": 0,
                    "drop_header": 1,
                    "drop_footer": 3,
                    "table_id": "current",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/landtage/hessen.htm",
                    "table_index": 1,
                    "drop_header": 1,
                    "drop_footer": 3,
                    "table_id": "historical",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/landtage/hessen.htm",
                    "table_index": 2,
                    "drop_header": 1,
                    "drop_footer": 3,
                    "table_id": "historical_2",
                },
            ],
            type="wahlrecht_land",
        )


def get_config():
    """Return config for discovery."""
    return HessenScraper.get_config()
