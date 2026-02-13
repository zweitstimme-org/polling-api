"""Sachsen-Anhalt scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtLandScraper


class SachsenAnhaltScraper(WahlrechtLandScraper):
    """Scraper for Sachsen-Anhalt state polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for Sachsen-Anhalt scraper."""
        return ScraperConfig(
            worker_name="sachsenanhalt",
            institute_id="various",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="sachsenanhalt",
            election_id="Landtagswahl",
            method_id="99",
            urls=[
                {
                    "url": "https://www.wahlrecht.de/umfragen/landtage/sachsenanhalt.htm",
                    "table_index": 0,
                    "drop_header": 1,
                    "drop_footer": 3,
                },
            ],
            type="wahlrecht_land",
        )


def get_config():
    """Return config for discovery."""
    return SachsenAnhaltScraper.get_config()
