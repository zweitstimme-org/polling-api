"""Infratest dimap scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtBundScraper


class InfratestScraper(WahlrechtBundScraper):
    """Scraper for Infratest dimap polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for Infratest dimap scraper."""
        return ScraperConfig(
            worker_name="infratest",
            institute_id="infratest",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="federal",
            election_id="Bundestagswahl",
            method_id="99",
            urls=[
                {"url": "https://www.wahlrecht.de/umfragen/dimap/2001.htm", "drop_footer": 4},
                {"url": "https://www.wahlrecht.de/umfragen/dimap/2002.htm", "drop_footer": 4},
                {"url": "https://www.wahlrecht.de/umfragen/dimap/2005.htm", "drop_footer": 4},
                {"url": "https://www.wahlrecht.de/umfragen/dimap/2009.htm", "drop_footer": 4},
                {"url": "https://www.wahlrecht.de/umfragen/dimap/2013.htm", "drop_footer": 4},
                {"url": "https://www.wahlrecht.de/umfragen/dimap/2017.htm", "drop_footer": 4},
                {"url": "https://www.wahlrecht.de/umfragen/dimap/2021.htm", "drop_footer": 4},
                {"url": "https://www.wahlrecht.de/umfragen/dimap.htm", "drop_footer": 4},
            ],
            type="wahlrecht_bund",
        )


def get_config():
    """Return config for discovery."""
    return InfratestScraper.get_config()
