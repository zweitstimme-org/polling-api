"""Verian (formerly Emnid) scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtBundScraper


class VerianScraper(WahlrechtBundScraper):
    """Scraper for Verian (Emnid) polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for Verian scraper."""
        return ScraperConfig(
            worker_name="verian",
            institute_id="verian",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="federal",
            election_id="Bundestagswahl",
            method_id="99",
            urls=[
                {"url": "https://www.wahlrecht.de/umfragen/emnid/1998.htm", "drop_footer": 4},
                {"url": "https://www.wahlrecht.de/umfragen/emnid/2002.htm", "drop_footer": 4},
                {"url": "https://www.wahlrecht.de/umfragen/emnid/2005.htm", "drop_footer": 4},
                {"url": "https://www.wahlrecht.de/umfragen/emnid/2009.htm", "drop_footer": 4},
                {"url": "https://www.wahlrecht.de/umfragen/emnid/2013.htm", "drop_footer": 4},
                {"url": "https://www.wahlrecht.de/umfragen/emnid/2017.htm", "drop_footer": 4},
                {"url": "https://www.wahlrecht.de/umfragen/emnid/2021.htm", "drop_footer": 4},
                {"url": "https://www.wahlrecht.de/umfragen/emnid.htm", "drop_footer": 4},
            ],
            type="wahlrecht_bund",
        )


def get_config():
    """Return config for discovery."""
    return VerianScraper.get_config()
