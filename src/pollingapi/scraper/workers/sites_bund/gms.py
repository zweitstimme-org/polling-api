"""GMS scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.wahlrecht import WahlrechtBundScraper


class GmsScraper(WahlrechtBundScraper):
    """Scraper for GMS polling data."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for GMS scraper."""
        return ScraperConfig(
            worker_name="gms",
            institute_id="gms",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="federal",
            election_id="Bundestagswahl",
            method_id="99",
            urls=[
                {
                    "url": "https://www.wahlrecht.de/umfragen/gms/projektion-2005.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/gms/projektion-2009.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/gms/projektion-2013.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/gms/projektion-2017.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
                {
                    "url": "https://www.wahlrecht.de/umfragen/gms.htm",
                    "drop_footer": 4,
                    "party_start_after": "Unnamed: 1",
                    "party_end_before": "Befragte",
                },
            ],
            type="wahlrecht_bund",
        )


def get_config():
    """Return config for discovery."""
    return GmsScraper.get_config()
