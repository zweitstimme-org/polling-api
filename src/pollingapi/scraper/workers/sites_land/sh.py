"""Schleswig-Holstein scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtLandScraper


class ShScraper(WahlrechtLandScraper):
    """Scraper for Schleswig-Holstein state polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for Schleswig-Holstein scraper."""
        return ScraperConfig(
            worker_name="schleswig-holstein",
            institute_id="various",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="schleswig-holstein",
            election_id="Landtagswahl",
            method_id="99",
            urls=[
                {
                    "url": "https://www.wahlrecht.de/umfragen/landtage/schleswig-holstein.htm",
                    "table_index": 0,
                    "drop_header": 1,
                    "drop_footer": 3,
                },
            ],
            type="wahlrecht_land",
        )


def get_config():
    """Return config for discovery."""
    return ShScraper.get_config()
