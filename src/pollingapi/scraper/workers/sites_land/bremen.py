"""Bremen scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtLandScraper


class BremenScraper(WahlrechtLandScraper):
    """Scraper for Bremen state polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for Bremen scraper."""
        return ScraperConfig(
            worker_name="wahlrecht_bremen",
            institute_id="various",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="bremen",
            election_id="Landtagswahl Bremen",
            method_id="99",
            urls=[
                {
                    "url": "https://www.wahlrecht.de/umfragen/landtage/bremen.htm",
                    "table_index": 0,
                    "drop_header": 1,
                    "drop_footer": 3,
                    "table_id": "current",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/landtage/bremen.htm",
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
    return BremenScraper.get_config()
