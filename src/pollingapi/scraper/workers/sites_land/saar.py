"""Saarland scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtLandScraper


class SaarlandScraper(WahlrechtLandScraper):
    """Scraper for Saarland state polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for Saarland scraper."""
        return ScraperConfig(
            worker_name="saarland",
            institute_id="various",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="saarland",
            election_id="Landtagswahl",
            method_id="99",
            urls=[
                {
                    "url": "https://www.wahlrecht.de/umfragen/landtage/saarland.htm",
                    "table_index": 0,
                    "drop_header": 1,
                    "drop_footer": 3,
                },
            ],
            type="wahlrecht_land",
        )


def get_config():
    """Return config for discovery."""
    return SaarlandScraper.get_config()
