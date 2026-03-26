"""Berlin scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtLandScraper


class BerlinScraper(WahlrechtLandScraper):
    """Scraper for Berlin state polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for Berlin scraper."""
        return ScraperConfig(
            worker_name="berlin",
            institute_id="various",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="BE",
            election_id="Landtagswahl",
            method_id="99",
            urls=[
                {
                    "url": "https://www.wahlrecht.de/umfragen/landtage/berlin.htm",
                    "table_index": 0,
                    "drop_header": 1,
                    "drop_footer": 3,
                },
            ],
            type="wahlrecht_land",
        )


def get_config():
    """Return config for discovery."""
    return BerlinScraper.get_config()
