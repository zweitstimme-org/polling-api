"""Bayern (Bavaria) scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtLandScraper


class BayernScraper(WahlrechtLandScraper):
    """Scraper for Bayern state polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for Bayern scraper."""
        return ScraperConfig(
            worker_name="bayern",
            institute_id="various",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="BY",
            election_id="Landtagswahl",
            method_id="99",
            urls=[
                {
                    "url": "https://www.wahlrecht.de/umfragen/landtage/bayern.htm",
                    "table_index": 0,
                    "drop_header": 1,
                    "drop_footer": 3,
                },
            ],
            type="wahlrecht_land",
        )


def get_config():
    """Return config for discovery."""
    return BayernScraper.get_config()
