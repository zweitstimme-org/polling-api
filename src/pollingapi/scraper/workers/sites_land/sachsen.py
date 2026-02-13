"""Sachsen scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtLandScraper


class SachsenScraper(WahlrechtLandScraper):
    """Scraper for Sachsen state polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for Sachsen scraper."""
        return ScraperConfig(
            worker_name="sachsen",
            institute_id="various",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="sachsen",
            election_id="Landtagswahl",
            method_id="99",
            urls=[
                {
                    "url": "https://www.wahlrecht.de/umfragen/landtage/sachsen.htm",
                    "table_index": 0,
                    "drop_header": 1,
                    "drop_footer": 3,
                },
            ],
            type="wahlrecht_land",
        )


def get_config():
    """Return config for discovery."""
    return SachsenScraper.get_config()
