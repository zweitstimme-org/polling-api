"""Nordrhein-Westfalen scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtLandScraper


class NrwScraper(WahlrechtLandScraper):
    """Scraper for Nordrhein-Westfalen state polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for NRW scraper."""
        return ScraperConfig(
            worker_name="nrw",
            institute_id="various",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="nrw",
            election_id="Landtagswahl",
            method_id="99",
            urls=[
                {
                    "url": "https://www.wahlrecht.de/umfragen/landtage/nrw.htm",
                    "table_index": 0,
                    "drop_header": 0,
                    "drop_footer": 3,
                },
            ],
            type="wahlrecht_land",
        )


def get_config():
    """Return config for discovery."""
    return NrwScraper.get_config()
