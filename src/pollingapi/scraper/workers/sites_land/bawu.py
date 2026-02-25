"""Baden-Württemberg scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtLandScraper


class BawuScraper(WahlrechtLandScraper):
    """Scraper for Baden-Württemberg state polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for Baden-Württemberg scraper."""
        return ScraperConfig(
            worker_name="wahlrecht_bawu",
            institute_id="various",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="baden-wuerttemberg",
            election_id="Landtagswahl Baden-Württemberg",
            method_id="99",
            urls=[
                {
                    "url": "https://www.wahlrecht.de/umfragen/landtage/baden-wuerttemberg.htm",
                    "table_index": 0,
                    "drop_footer": 3,
                    "table_id": "current",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/landtage/baden-wuerttemberg.htm",
                    "table_index": 1,
                    "drop_footer": 3,
                    "table_id": "historical",
                },
            ],
            type="wahlrecht_land",
        )


def get_config():
    """Return config for discovery."""
    return BawuScraper.get_config()
