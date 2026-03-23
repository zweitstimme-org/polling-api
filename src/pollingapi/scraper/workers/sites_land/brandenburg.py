"""Brandenburg scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtLandScraper


class BrandenburgScraper(WahlrechtLandScraper):
    """Scraper for Brandenburg state polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for Brandenburg scraper."""
        return ScraperConfig(
            worker_name="wahlrecht_brand",
            institute_id="various",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="brandenburg",
            election_id="Landtagswahl Brandenburg",
            method_id="99",
            urls=[
                {
                    "url": "https://www.wahlrecht.de/umfragen/landtage/brandenburg.htm",
                    "table_index": 0,
                    "drop_header": 0,
                    "drop_footer": 3,
                    "table_id": "current",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/landtage/brandenburg.htm",
                    "table_index": 1,
                    "drop_header": 0,
                    "drop_footer": 3,
                    "table_id": "historical",
                },
            ],
            type="wahlrecht_land",
        )


def get_config():
    """Return config for discovery."""
    return BrandenburgScraper.get_config()
