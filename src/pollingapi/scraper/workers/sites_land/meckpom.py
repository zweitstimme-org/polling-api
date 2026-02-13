"""Mecklenburg-Vorpommern scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtLandScraper


class MeckpomScraper(WahlrechtLandScraper):
    """Scraper for Mecklenburg-Vorpommern state polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for Mecklenburg-Vorpommern scraper."""
        return ScraperConfig(
            worker_name="wahlrecht_meckpom",
            institute_id="various",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="mecklenburg-vorpommern",
            election_id="Landtagswahl Mecklenburg-Vorpommern",
            method_id="99",
            urls=[
                {
                    "url": "https://www.wahlrecht.de/umfragen/landtage/mecklenburg-vorpommern.htm",
                    "table_index": 0,
                    "drop_header": 1,
                    "drop_footer": 3,
                    "table_id": "current",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/landtage/mecklenburg-vorpommern.htm",
                    "table_index": 1,
                    "drop_header": 1,
                    "drop_footer": 3,
                    "table_id": "historical",
                },
            ],
            type="wahlrecht_land",
        )


def get_config():
    """Return config for discovery."""
    return MeckpomScraper.get_config()
