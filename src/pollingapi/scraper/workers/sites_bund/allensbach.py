"""Allensbach scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtBundScraper


class AllensbachScraper(WahlrechtBundScraper):
    """Scraper for Allensbach polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for Allensbach scraper."""
        return ScraperConfig(
            worker_name="allensbach",
            institute_id="allensbach",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="federal",
            election_id="Bundestagswahl",
            method_id="99",
            urls=[
                {"url": "https://www.wahlrecht.de/umfragen/allensbach/2002.htm", "drop_footer": 4},
                {"url": "https://www.wahlrecht.de/umfragen/allensbach/2005.htm", "drop_footer": 4},
                {"url": "https://www.wahlrecht.de/umfragen/allensbach/2009.htm", "drop_footer": 4},
                {"url": "https://www.wahlrecht.de/umfragen/allensbach/2013.htm", "drop_footer": 4},
                {"url": "https://www.wahlrecht.de/umfragen/allensbach/2017.htm", "drop_footer": 4},
                {"url": "https://www.wahlrecht.de/umfragen/allensbach.htm", "drop_footer": 4},
            ],
            type="wahlrecht_bund",
        )


def get_config():
    """Return config for discovery."""
    return AllensbachScraper.get_config()
