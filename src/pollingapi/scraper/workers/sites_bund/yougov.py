"""YouGov scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtBundScraper


class YougovScraper(WahlrechtBundScraper):
    """Scraper for YouGov polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for YouGov scraper."""
        return ScraperConfig(
            worker_name="yougov",
            institute_id="yougov",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="federal",
            election_id="Bundestagswahl",
            method_id="99",
            urls=[
                {"url": "https://www.wahlrecht.de/umfragen/yougov.htm", "drop_footer": 4},
            ],
            type="wahlrecht_bund",
        )


def get_config():
    """Return config for discovery."""
    return YougovScraper.get_config()
