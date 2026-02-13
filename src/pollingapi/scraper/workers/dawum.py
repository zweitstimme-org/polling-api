"""DAWUM API scraper worker."""

from pollingapi.scraper.config import ScraperConfig
from pollingapi.scraper.dawum import DawumScraper


class DawumWorker(DawumScraper):
    """DAWUM API worker that follows the worker pattern."""

    @classmethod
    def get_config(cls) -> ScraperConfig:
        """Get configuration for DAWUM scraper."""
        return ScraperConfig(
            worker_name="dawum",
            institute_id="various",
            provider="DAWUM",
            source="api",
            scope="federal",
            election_id="Bundestagswahl",
            method_id="99",
            urls=[{"url": "https://api.dawum.de/"}],
            type="dawum_api",
        )


def get_config():
    """Return config for discovery."""
    return DawumWorker.get_config()
