"""INSA scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtBundScraper


class InsaScraper(WahlrechtBundScraper):
    """Scraper for INSA polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for INSA scraper."""
        return ScraperConfig(
            worker_name="insa",
            institute_id="insa",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="federal",
            election_id="Bundestagswahl",
            method_id="99",
            urls=[
                {
                    "url": "https://www.wahlrecht.de/umfragen/insa/2013.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/insa/2017.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/insa/2021.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/insa.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
            ],
            type="wahlrecht_bund",
        )


def get_config():
    """Return config for discovery."""
    return InsaScraper.get_config()
