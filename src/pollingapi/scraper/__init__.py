"""Core scraper components for polling data collection."""

from pollingapi.logging_config import get_logger
from pollingapi.scraper.base import BaseScraper
from pollingapi.scraper.config import ScraperConfig, ScraperRegistry
from pollingapi.scraper.context import RunContext
from pollingapi.scraper.schemas import ALLOWED_POLL_COLUMNS, PollPayload, filter_poll_payloads
from pollingapi.scraper.snapshots import (
    save_debug_snapshot,
    save_html_snapshot,
    save_normalized_snapshot,
    save_table_snapshot,
)

__all__ = [
    "BaseScraper",
    "ScraperConfig",
    "ScraperRegistry",
    "RunContext",
    "get_logger",
    "PollPayload",
    "ALLOWED_POLL_COLUMNS",
    "filter_poll_payloads",
    "save_html_snapshot",
    "save_table_snapshot",
    "save_normalized_snapshot",
    "save_debug_snapshot",
]
