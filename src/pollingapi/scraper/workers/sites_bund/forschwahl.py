"""Forschungsgruppe Wahlen scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtBundScraper


class ForschwahlScraper(WahlrechtBundScraper):
    """Scraper for Forschungsgruppe Wahlen polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for Forschungsgruppe Wahlen scraper."""
        return ScraperConfig(
            worker_name="forschwahlen",
            institute_id="forschwahlen",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="federal",
            election_id="Bundestagswahl",
            method_id="99",
            urls=[
                {
                    "url": "https://www.wahlrecht.de/umfragen/politbarometer/2002.htm",
                    "drop_footer": 4,
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/politbarometer/2005.htm",
                    "drop_footer": 4,
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/politbarometer/2009.htm",
                    "drop_footer": 4,
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/politbarometer/2013.htm",
                    "drop_footer": 4,
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/politbarometer/2017.htm",
                    "drop_footer": 4,
                },
                {"url": "https://www.wahlrecht.de/umfragen/politbarometer.htm", "drop_footer": 4},
            ],
            type="wahlrecht_bund",
        )


def get_config():
    """Return config for discovery."""
    return ForschwahlScraper.get_config()
