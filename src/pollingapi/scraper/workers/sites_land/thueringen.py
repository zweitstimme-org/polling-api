"""Thüringen scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtLandScraper


class ThueringenScraper(WahlrechtLandScraper):
    """Scraper for Thüringen state polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for Thüringen scraper."""
        return ScraperConfig(
            worker_name="thueringen",
            institute_id="various",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="thueringen",
            election_id="Landtagswahl",
            method_id="99",
            urls=[
                {
                    "url": "https://www.wahlrecht.de/umfragen/landtage/thueringen.htm",
                    "table_index": 0,
                    "drop_header": 0,
                    "drop_footer": 3,
                },
            ],
            type="wahlrecht_land",
        )


def get_config():
    """Return config for discovery."""
    return ThueringenScraper.get_config()
