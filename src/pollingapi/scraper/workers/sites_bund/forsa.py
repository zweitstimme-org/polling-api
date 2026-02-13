"""Forsa scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtBundScraper


class ForsaScraper(WahlrechtBundScraper):
    """Scraper for Forsa polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for Forsa scraper."""
        return ScraperConfig(
            worker_name="forsa",
            institute_id="forsa",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="federal",
            election_id="Bundestagswahl",
            method_id="99",
            urls=[
                {
                    "url": "https://www.wahlrecht.de/umfragen/forsa/1999.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/forsa/2000.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/forsa/2001.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/forsa/2002.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/forsa/2003.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/forsa/2004.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/forsa/2005.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/forsa/2006.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/forsa/2007.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/forsa/2008.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/forsa/2013.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
                # {
                #     "url": "https://www.wahlrecht.de/umfragen/forsa/2017.htm",
                #     "drop_footer": 4,
                #     "party_start_after": "Unnamed: 1",
                #     "party_end_before": "Befragte",
                # },
                {
                    "url": "https://www.wahlrecht.de/umfragen/forsa.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
            ],
            type="wahlrecht_bund",
        )


def get_config():
    """Return config for discovery."""
    return ForsaScraper.get_config()
